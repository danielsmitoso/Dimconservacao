"""Planilha de exemplo FICTÍCIA no mesmo formato da planilha da equipe
(modelo atual rev.01; o modelo antigo também pode ser gerado, para teste).

Serve para conhecer o app sem dado real e como modelo de preenchimento.
As datas são relativas à data-base, para sempre haver ações atrasadas, da
semana e futuras.
"""
from __future__ import annotations

import copy
import io
from datetime import date, timedelta

import openpyxl
import openpyxl.utils
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

FUNDO_ENTREGA = PatternFill("solid", fgColor="FF6666FF")
FUNDO_CABECALHO = PatternFill("solid", fgColor="FF3D1A9E")
LINHA_CABECALHO = 7
N_SEMANAS = 6

# (frente, [(entrega, [ação | ("#subgrupo",) ...])]); ação = (nome, resp, status, peso, dias_ate_prazo, comentário)
EXEMPLO = [
    ("Fábrica de Placas", [
        ("Equipe", [
            ("Contratação de operador de plotter", "Ana", "Concluído", 2, -12, "Concluído"),
            ("Integração do novo supervisor", "Ana", "Em andamento", 3, 4, "Agenda de integração enviada"),
            ("Escala de férias do 1º semestre", "Ana", "À iniciar", 1, 20, ""),
        ]),
        ("Manutenção da fábrica", [
            ("Ar-condicionado da produção", "Facilities", "À iniciar", 3, 2, "Abertura de chamado Facilities"),
            ("Troca de lâmpadas do galpão", "Facilities", "Em andamento", 1, -3, "Aguardando retorno do fornecedor"),
            ("Revisão dos compressores", "Bruno", "À iniciar", 2, None, ""),
        ]),
        ("Plano de produção", [
            ("#Estoque",),
            ("Definir estoque padrão por tipo de placa", "Carla", "Em andamento", 3, -5, "Levantando histórico"),
            ("Catalogar placas prontas", "Diego", "Concluído", 2, -2, "Concluído"),
            ("#Execução",),
            ("Plano de impressão semanal", "Bruno", "À iniciar", 3, 6, ""),
            ("Planejamento de entregas às unidades", "Bruno, Carla", "Em andamento", 2, 15, "Rotas em revisão"),
            ("Placas sem informação da unidade", "", "", None, None, ""),
        ]),
    ]),
    ("Centralização", [
        ("Padronização dos formulários", [
            ("Desenho do fluxo de solicitação", "Diego", "Concluído", 2, -20, "Concluído"),
            ("Formulário Hub Sul", "Diego", "Concluído", 1, -9, "Concluído"),
            ("Formulário Hub Norte", "Diego", "Em andamento", 1, -1, "Em teste com a unidade"),
            ("Operação assistida", "Bruno", "À iniciar", 3, 30, ""),
        ]),
        ("Kick-off com as unidades", [
            ("Passo a passo para solicitantes", "Diego", "Concluído", 2, -4, "Concluído"),
            ("Treinamento das unidades", "Diego", "Em andamento", 3, 3, "2 de 5 unidades treinadas"),
            ("E-mail formalizando a transição", "Ana", "Em andamento", 2, -6, "Enviado para 3 hubs"),
        ]),
    ]),
    ("Novos Negócios", [
        ("Projeto Alfa - Orçamento", [
            ("Pacote de conservação", "Eva / Bruno", "Em andamento", 2, 10, "Premissas validadas"),
            ("Sinalização horizontal", "Eva", "À iniciar", 2, None, ""),
            ("Sinalização vertical", "", "À iniciar", 2, None, ""),
        ]),
    ]),
]


# Versão 2 = a mesma planilha uma semana depois (para o modo demonstração mostrar histórico)
MUDANCAS_V2 = {
    "Integração do novo supervisor": dict(status="Concluído", comentario="Concluído"),
    "Ar-condicionado da produção": dict(status="Em andamento", dias=9, comentario="Técnico agendado"),
    "Formulário Hub Norte": dict(status="Concluído", comentario="Concluído"),
    "Treinamento das unidades": dict(dias=10, comentario="3 de 5 unidades treinadas"),
    "Catalogar placas prontas": dict(nome="Catalogar as placas prontas"),
}
REMOVIDAS_V2 = {"Escala de férias do 1º semestre"}
NOVAS_V2 = {"Projeto Alfa - Orçamento": [("Manutenção de EPS", "Eva", "À iniciar", 1, 12, "")]}


def _dados(versao: int):
    dados = copy.deepcopy(EXEMPLO)
    if versao == 1:
        return dados
    for _, entregas in dados:
        for j, (entrega, acoes) in enumerate(entregas):
            novas = []
            for a in acoes:
                if len(a) > 1 and a[0] in REMOVIDAS_V2:
                    continue
                if len(a) > 1 and a[0] in MUDANCAS_V2:
                    m = MUDANCAS_V2[a[0]]
                    nome, resp, status, peso, dias, coment = a
                    a = (m.get("nome", nome), resp, m.get("status", status), peso, m.get("dias", dias),
                         m.get("comentario", coment))
                novas.append(a)
            novas += NOVAS_V2.get(entrega, [])
            entregas[j] = (entrega, novas)
    return dados


# % digitado na planilha (o resto sai do status): ex. treinamento em 2 de 5 unidades = 40%
PCT_MANUAL = {1: {"Treinamento das unidades": 0.4}, 2: {"Treinamento das unidades": 0.6}}

ATUAL, ANTIGO = "atual", "antigo"
# Modelo atual (rev.01): B Avanço | C Título/Tarefa | D Tarefa | E Responsável | F Status | G Peso | H % | I Prazo | J+ semanas
# Modelo antigo:         B Avanço | C Tarefa | D Responsável | E Status | F Peso | G % | H Data | I+ semanas
COLUNAS = {
    ATUAL: dict(tipo=3, nome=4, resp=5, status=6, peso=7, pct=8, data=9, semanas=10,
                cab=["Avanço", "Título/Tarefa", "Tarefa", "Responsável", "Status", "Peso", "%", "Prazo/\nConclusão"]),
    ANTIGO: dict(tipo=None, nome=3, resp=4, status=5, peso=6, pct=7, data=8, semanas=9,
                 cab=["Avanço", "Tarefa", "Responsável", "Status", "Peso", "%", "Data Prevista/conclusão"]),
}


def _letra(col: int) -> str:
    return openpyxl.utils.get_column_letter(col)


def _cabecalho(ws, formato: str, base: date):
    k = COLUNAS[formato]
    semanas = [(base - timedelta(days=base.weekday()) + timedelta(weeks=i - 1)) for i in range(N_SEMANAS)]
    for j, t in enumerate(k["cab"] + [f"{s:%d/%m/%Y}" for s in semanas], start=2):
        c = ws.cell(LINHA_CABECALHO, j, t)
        c.font = Font(bold=True, color="FFFFFFFF")
        c.fill = FUNDO_CABECALHO
        c.alignment = Alignment(horizontal="center", wrap_text=True)


def _aba(wb, frente, entregas, base: date, formato: str, versao: int):
    k = COLUNAS[formato]
    ws = wb.create_sheet(frente)
    ws["C2"] = frente.upper()
    ws["C2"].font = Font(bold=True, size=16, color="FF3D1A9E")
    ws["C3"] = "LISTA DE TAREFAS PENDENTES"
    _cabecalho(ws, formato, base)
    status_dv = DataValidation(type="list", formula1='"À iniciar,Em andamento,Concluído"', allow_blank=True)
    peso_dv = DataValidation(type="list", formula1='"1,2,3"', allow_blank=True)
    tipo_dv = DataValidation(type="list", formula1='"Título,Tarefa"', allow_blank=True)
    for dv in (status_dv, peso_dv) + ((tipo_dv,) if k["tipo"] else ()):
        ws.add_data_validation(dv)

    r = LINHA_CABECALHO + 1
    for entrega, acoes in entregas:
        c = ws.cell(r, k["nome"], entrega)
        c.font, c.fill = Font(bold=True, color="FFFFFFFF"), FUNDO_ENTREGA
        if k["tipo"]:
            t = ws.cell(r, k["tipo"], "Título")
            t.font, t.fill = Font(bold=True, color="FFFFFFFF"), FUNDO_ENTREGA
            tipo_dv.add(f"{_letra(k['tipo'])}{r}")
        r += 1
        for a in acoes:
            if len(a) == 1:  # subgrupo: só existe no modelo antigo
                if not k["tipo"]:
                    ws.cell(r, k["nome"], a[0][1:]).font = Font(bold=True)
                    r += 1
                continue
            nome, resp, status, peso, dias, coment = a
            if k["tipo"]:
                ws.cell(r, k["tipo"], "Tarefa")
                tipo_dv.add(f"{_letra(k['tipo'])}{r}")
            ws.cell(r, k["nome"], nome)
            ws.cell(r, k["resp"], resp or None)
            ws.cell(r, k["status"], status or None)
            ws.cell(r, k["peso"], peso)
            pct = PCT_MANUAL.get(versao, {}).get(nome, {"Concluído": 1, "Em andamento": 0.5}.get(status, 0))
            ws.cell(r, k["pct"], pct).number_format = "0%"
            if dias is not None:
                ws.cell(r, k["data"], base + timedelta(days=dias)).number_format = "DD/MM/YYYY"
            if coment:
                ws.cell(r, k["semanas"] + N_SEMANAS - 2, coment)  # comentário na semana corrente
            status_dv.add(f"{_letra(k['status'])}{r}")
            peso_dv.add(f"{_letra(k['peso'])}{r}")
            r += 1
    larguras = {k["nome"]: 45, k["resp"]: 16, k["status"]: 14, k["peso"]: 7, k["pct"]: 7, k["data"]: 14}
    if k["tipo"]:
        larguras[k["tipo"]] = 13
    for col, w in larguras.items():
        ws.column_dimensions[_letra(col)].width = w


def gerar_planilha_exemplo(base: date | None = None, versao: int = 1, formato: str = ATUAL) -> bytes:
    """formato: "atual" (rev.01, com a coluna Título/Tarefa) ou "antigo" (tipo pela formatação)."""
    base = base or date.today()
    wb = openpyxl.Workbook()
    instr = wb.active
    instr.title = "Instruções"
    if formato == ATUAL:
        linhas = [
            "PLANILHA DE EXEMPLO (dados fictícios) — modelo da equipe (rev.01)",
            "",
            "• Uma aba por FRENTE. Linha 7: cabeçalho (Avanço, Título/Tarefa, Tarefa, Responsável, Status, Peso, %, "
            "Prazo/Conclusão e uma coluna por semana).",
            "• Coluna 'Título/Tarefa': 'Título' = ENTREGA (linha-mãe); 'Tarefa' = AÇÃO.",
            "• AÇÃO: um responsável por linha; Status (À iniciar / Em andamento / Concluído); Peso (1 a 3);",
            "  % (opcional: sem valor, vale 0% / 50% / 100% pelo status; Concluído é sempre 100%);",
            "  Prazo (ou data de conclusão, se concluída) e o comentário da semana na coluna da semana.",
            "• O app encontra as colunas pelo NOME do cabeçalho: dá para mudar a ordem, mas não o nome.",
        ]
    else:
        linhas = [
            "PLANILHA DE EXEMPLO (dados fictícios) — modelo ANTIGO (até 19/10/2026)",
            "",
            "• ENTREGA: negrito com fundo colorido. SUBGRUPO: negrito sem fundo. AÇÃO: demais linhas.",
        ]
    for i, t in enumerate(linhas, 1):
        instr.cell(i, 1, t)
    instr["A1"].font = Font(bold=True, size=13, color="FF5E22F3")
    instr.column_dimensions["A"].width = 120
    for frente, entregas in _dados(versao):
        _aba(wb, frente, entregas, base, formato, versao)
    modelo = wb.create_sheet("Modelo vazio")  # aba só com o modelo é ignorada
    k = COLUNAS[formato]
    _cabecalho(modelo, formato, base)
    modelo.cell(LINHA_CABECALHO + 1, k["nome"], "TAREFA PRINCIPAL").font = Font(bold=True)
    modelo.cell(LINHA_CABECALHO + 1, k["nome"]).fill = FUNDO_ENTREGA
    if k["tipo"]:
        modelo.cell(LINHA_CABECALHO + 1, k["tipo"], "Título")
    for r in range(LINHA_CABECALHO + 2, LINHA_CABECALHO + 6):
        modelo.cell(r, k["nome"], "AÇÕES")
        if k["tipo"]:
            modelo.cell(r, k["tipo"], "Tarefa")
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()
