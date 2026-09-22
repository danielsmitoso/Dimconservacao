"""Memória de cálculo em Excel: permite ao usuário conferir, número por número,
como o app chegou ao dimensionamento.

Diferença para um "export de resultados": aqui os cálculos são FÓRMULAS do
Excel (dias disponíveis, dias por ciclo, demanda diária, necessário exato,
arredondamento) sobre as premissas em células azuis. O usuário pode mudar uma
premissa na planilha e ver o resultado recalcular, ou simplesmente conferir a
conta de qualquer atividade.

Abas: Resumo · Memória de cálculo · Análise de Contrato · Inventário ·
Divisão Roçada Manual · Divisão Mecanizada · Auditoria Quasar · Premissas.
"""
import io

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROXO = "5E22F3"
ROXO_ESCURO = "3D1A9E"
LAVANDA = "EDE8FB"
LAVANDA_CLARO = "F7F4FE"
AZUL_INPUT = "0000FF"
_BORDA = Border(*(Side(style="thin", color="D9D0F5") for _ in range(4)))

FMT_INT = "#,##0"
FMT_DEC = "#,##0.00"


def _titulo(ws, texto, subtitulo=None):
    ws.sheet_view.showGridLines = False
    ws["A1"] = texto
    ws["A1"].font = Font(bold=True, size=16, color=ROXO_ESCURO)
    if subtitulo:
        ws["A2"] = subtitulo
        ws["A2"].font = Font(italic=True, color="666666")


def _cabecalho(ws, linha, titulos, altura=32):
    ws.row_dimensions[linha].height = altura
    for j, t in enumerate(titulos, start=1):
        c = ws.cell(row=linha, column=j, value=t)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=ROXO)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = _BORDA


def _corpo(cel, zebra: bool, formato=None, azul=False, negrito=False):
    cel.border = _BORDA
    if zebra:
        cel.fill = PatternFill("solid", fgColor=LAVANDA_CLARO)
    if formato:
        cel.number_format = formato
    if azul or negrito:
        cel.font = Font(color=AZUL_INPUT if azul else "000000", bold=negrito)


def _larguras(ws, larguras: dict):
    for letra, w in larguras.items():
        ws.column_dimensions[letra].width = w


def _auto_largura(ws, minimo=10, maximo=46):
    for col in ws.columns:
        letra = get_column_letter(col[0].column)
        tam = max((len(str(c.value)) for c in col if c.value is not None and not str(c.value).startswith("=")), default=0)
        ws.column_dimensions[letra].width = max(minimo, min(maximo, tam + 3))


def _escrever_df(ws, df: pd.DataFrame, linha_inicial: int, formatos: dict | None = None, altura_cab=32):
    """Escreve um DataFrame como tabela formatada. Retorna a última linha usada."""
    formatos = formatos or {}
    _cabecalho(ws, linha_inicial, list(df.columns), altura_cab)
    for i, (_, r) in enumerate(df.iterrows(), start=linha_inicial + 1):
        for j, col in enumerate(df.columns, start=1):
            v = r[col]
            if isinstance(v, float) and pd.isna(v):
                v = None
            cel = ws.cell(row=i, column=j, value=v)
            fmt = formatos.get(col)
            if fmt is None and isinstance(v, float):
                fmt = FMT_DEC if abs(v) < 1000 else FMT_INT
            _corpo(cel, i % 2 == 0, fmt)
    return linha_inicial + len(df)


def gerar_memoria_calculo(dados: dict) -> bytes:
    """Monta a planilha. `dados` (montado pelo app):
      unidade, data, dias_uteis_mes,
      atividades: lista de dicts (grupo, nome, unidade_qtd, unidade_resultado,
          quantidade, origem_quantidade, produtividade, ciclos_chuva,
          meses_chuva, ciclos_seca, meses_seca, fonte),
      analise: lista [atividade, dimensionado, contratado, status] (ou vazia),
      inventario: DataFrame,
      divisoes: {nome_da_aba: DataFrame},
      auditoria: dict de quasar.auditar_quasar (ou None),
      premissas: lista de (tema, texto).
    """
    wb = Workbook()
    ws_res = wb.active
    ws_res.title = "Resumo"
    ws_mem = wb.create_sheet("Memória de cálculo")
    ws_ana = wb.create_sheet("Análise de Contrato")
    ws_inv = wb.create_sheet("Inventário")

    dias_uteis = dados.get("dias_uteis_mes", 22)
    atividades = dados.get("atividades", [])

    # ------------------------------------------------------------------ Inventário
    inv = dados.get("inventario")
    _titulo(ws_inv, "Inventário utilizado no cálculo", f"Unidade: {dados.get('unidade', '')}")
    letras_inv = {}
    if inv is not None and len(inv):
        inv_exibir = inv.copy()
        _escrever_df(ws_inv, inv_exibir, 4)
        for j, c in enumerate(inv_exibir.columns, start=1):
            letras_inv[c] = get_column_letter(j)
        ws_inv.freeze_panes = "B5"
        _auto_largura(ws_inv)
        n_inv = len(inv_exibir)
        prim, ult = 5, 4 + n_inv
    else:
        prim = ult = None

    # ------------------------------------------------------------------ Memória de cálculo
    _titulo(
        ws_mem, "Memória de cálculo do dimensionamento",
        "Células em AZUL são premissas (podem ser alteradas); as demais são fórmulas. "
        "Necessário = ARREDONDAR PARA CIMA( Quantidade ÷ (Dias por ciclo × Produtividade) ).",
    )
    cab = ["Grupo", "Atividade", "Cenário", "Unid. da quantidade", "Quantidade", "Produtividade/dia (por unidade)",
           "Ciclos no período", "Meses do período", "Dias úteis/mês", "Dias disponíveis", "Dias por ciclo",
           "Demanda diária", "Necessário (exato)", "Necessário (arredondado)", "Resultado em", "Origem da quantidade",
           "Fonte do parâmetro"]
    _cabecalho(ws_mem, 4, cab, altura=46)
    linhas_resumo = []   # (atividade, linha_chuva, linha_seca)
    r = 5
    for a in atividades:
        pares = []
        for cenario, ciclos, meses in (("Chuva", a["ciclos_chuva"], a["meses_chuva"]), ("Seca", a["ciclos_seca"], a["meses_seca"])):
            z = r % 2 == 0
            valores = [a["grupo"], a["nome"], cenario, a["unidade_qtd"], a["quantidade"], a["produtividade"], ciclos, meses, dias_uteis]
            for j, v in enumerate(valores, start=1):
                cel = ws_mem.cell(row=r, column=j, value=v)
                _corpo(cel, z, FMT_DEC if j in (5, 6) else None, azul=j in (5, 6, 7, 8, 9))
            f = {
                10: f"=H{r}*I{r}",
                11: f"=IF(G{r}>0,J{r}/G{r},0)",
                12: f"=IF(K{r}>0,E{r}/K{r},0)",
                13: f"=IF(F{r}>0,L{r}/F{r},0)",
                14: f"=ROUNDUP(ROUND(M{r},6),0)",
            }
            for j, formula in f.items():
                cel = ws_mem.cell(row=r, column=j, value=formula)
                _corpo(cel, z, FMT_INT if j == 14 else FMT_DEC, negrito=(j == 14))
            for j, v in ((15, a["unidade_resultado"]), (16, a.get("origem_quantidade", "")), (17, a.get("fonte", ""))):
                _corpo(ws_mem.cell(row=r, column=j, value=v), z)
            pares.append(r)
            r += 1
        linhas_resumo.append((a, pares[0], pares[1]))
    ws_mem.freeze_panes = "D5"
    _larguras(ws_mem, {"A": 16, "B": 40, "C": 9, "D": 12, "E": 14, "F": 16, "G": 10, "H": 10, "I": 9, "J": 11,
                       "K": 11, "L": 13, "M": 12, "N": 14, "O": 14, "P": 42, "Q": 38})

    # ------------------------------------------------------------------ Resumo
    _titulo(ws_res, f"DimConservação — {dados.get('unidade', '')}",
            f"Memória de cálculo gerada em {dados.get('data', '')}. Conferência do inventário e resumo por atividade.")
    ws_res["A4"] = "Conferência do inventário"
    ws_res["A4"].font = Font(bold=True, size=12, color=ROXO_ESCURO)
    conferencia = [("Trechos", "COUNTA", "trecho", FMT_INT), ("Extensão total (km)", "SUM", "extensao_km", FMT_DEC),
                   ("Área verde total (m²)", "SUM", "area_verde_m2", FMT_INT)]
    linha = 5
    for rotulo, fn, col, fmt in conferencia:
        ws_res.cell(row=linha, column=1, value=rotulo).font = Font(bold=True)
        if prim and col in letras_inv:
            L = letras_inv[col]
            ws_res.cell(row=linha, column=2, value=f"={fn}('Inventário'!{L}{prim}:{L}{ult})").number_format = fmt
        linha += 1
    if prim and "pct_manual" in letras_inv:
        A, P = letras_inv["area_verde_m2"], letras_inv["pct_manual"]
        ws_res.cell(row=linha, column=1, value="Área manual (m²)").font = Font(bold=True)
        ws_res.cell(row=linha, column=2, value=f"=SUMPRODUCT('Inventário'!{A}{prim}:{A}{ult},'Inventário'!{P}{prim}:{P}{ult})/100").number_format = FMT_INT
        linha += 1
    if prim and "pct_mecanizada" in letras_inv:
        A, P = letras_inv["area_verde_m2"], letras_inv["pct_mecanizada"]
        ws_res.cell(row=linha, column=1, value="Área mecanizada (m²)").font = Font(bold=True)
        ws_res.cell(row=linha, column=2, value=f"=SUMPRODUCT('Inventário'!{A}{prim}:{A}{ult},'Inventário'!{P}{prim}:{P}{ult})/100").number_format = FMT_INT
        linha += 1

    topo = linha + 2
    ws_res.cell(row=topo - 1, column=1, value="Dimensionamento por atividade").font = Font(bold=True, size=12, color=ROXO_ESCURO)
    _cabecalho(ws_res, topo, ["Grupo", "Atividade", "Unid. da quantidade", "Quantidade", "Chuva", "Seca", "Pico", "Cenário de pico", "Resultado em"])
    linha_resumo_de = {}
    for i, (a, rc, rs) in enumerate(linhas_resumo, start=topo + 1):
        z = i % 2 == 0
        vals = [a["grupo"], a["nome"], a["unidade_qtd"], f"='Memória de cálculo'!E{rc}", f"='Memória de cálculo'!N{rc}",
                f"='Memória de cálculo'!N{rs}", f"=MAX(E{i},F{i})", f'=IF(E{i}>=F{i},"Chuva","Seca")', a["unidade_resultado"]]
        for j, v in enumerate(vals, start=1):
            cel = ws_res.cell(row=i, column=j, value=v)
            _corpo(cel, z, FMT_DEC if j == 4 else (FMT_INT if j in (5, 6, 7) else None), negrito=(j == 7))
        linha_resumo_de[a["nome"]] = i
    _larguras(ws_res, {"A": 26, "B": 44, "C": 14, "D": 16, "E": 10, "F": 10, "G": 10, "H": 14, "I": 16})

    # ------------------------------------------------------------------ Análise de Contrato
    _titulo(ws_ana, "Análise de Contrato — Dimensionado × Contratado",
            "Dimensionado vem do Resumo (fórmula). Altere a coluna Contratado (azul) para simular.")
    _cabecalho(ws_ana, 4, ["Atividade", "Dimensionado (pico)", "Contratado", "Diferença", "Status", "Desvio (%)"])
    analise = dados.get("analise") or []
    for i, (nome, dim_val, contr, _status) in enumerate(analise, start=5):
        z = i % 2 == 0
        ref = linha_resumo_de.get(nome)
        cel_a = ws_ana.cell(row=i, column=1, value=nome)
        cel_b = ws_ana.cell(row=i, column=2, value=f"=Resumo!G{ref}" if ref else dim_val)
        cel_c = ws_ana.cell(row=i, column=3, value=contr)
        cel_d = ws_ana.cell(row=i, column=4, value=f"=C{i}-B{i}")
        cel_e = ws_ana.cell(row=i, column=5, value=f'=IF(D{i}<0,"Déficit de "&-D{i},IF(D{i}>0,"Excedente de "&D{i},"Conforme"))')
        cel_f = ws_ana.cell(row=i, column=6, value=f'=IF(B{i}=0,"",D{i}/B{i})')
        for c, fmt, azul in ((cel_a, None, False), (cel_b, FMT_INT, False), (cel_c, FMT_INT, True), (cel_d, "+#,##0;-#,##0;0", False),
                             (cel_e, None, False), (cel_f, "+0%;-0%;0%", False)):
            _corpo(c, z, fmt, azul=azul)
    if analise:
        ult_a = 4 + len(analise)
        faixa = f"A5:F{ult_a}"
        ws_ana.conditional_formatting.add(faixa, FormulaRule(formula=["$D5<0"], fill=PatternFill("solid", bgColor="FAD4D4", fgColor="FAD4D4")))
        ws_ana.conditional_formatting.add(faixa, FormulaRule(formula=["$D5>0"], fill=PatternFill("solid", bgColor="FFF1C9", fgColor="FFF1C9")))
        ws_ana.conditional_formatting.add(faixa, FormulaRule(formula=["$D5=0"], fill=PatternFill("solid", bgColor="D7F0DC", fgColor="D7F0DC")))
    _larguras(ws_ana, {"A": 46, "B": 20, "C": 14, "D": 12, "E": 26, "F": 12})

    # ------------------------------------------------------------------ Divisões
    for nome_aba, df in (dados.get("divisoes") or {}).items():
        if df is None or len(df) == 0:
            continue
        ws = wb.create_sheet(nome_aba[:31])
        _titulo(ws, nome_aba, "Proposta de divisão por trecho (ocupação = quanto da capacidade de um ciclo é usada).")
        _escrever_df(ws, df, 4)
        ws.freeze_panes = "A5"
        _auto_largura(ws, maximo=60)

    # ------------------------------------------------------------------ Auditoria Quasar
    aud = dados.get("auditoria")
    if aud:
        ws = wb.create_sheet("Auditoria Quasar")
        _titulo(ws, "Auditoria do mapeamento Quasar", "Extensão física, cobertura do mapeamento e pontos de atenção.")
        t = aud["totais"]
        resumo = [("Polígonos lidos", t["poligonos"]), ("Rodovias", t["rodovias"]),
                  ("Extensão física total (km)", round(t["extensao_km"], 1)),
                  ("Área verde total (m²)", round(t["area_verde_m2"], 0)),
                  ("Área mecanizada total (m²)", round(t["area_mecanizada_m2"], 0))]
        for i, (k, v) in enumerate(resumo, start=4):
            ws.cell(row=i, column=1, value=k).font = Font(bold=True)
            ws.cell(row=i, column=2, value=v).number_format = FMT_INT if isinstance(v, int) or v > 1000 else FMT_DEC
        ult = _escrever_df(ws, aud["por_rodovia"], 10, altura_cab=48)
        ws.cell(row=ult + 2, column=1, value="Alertas").font = Font(bold=True, size=12, color=ROXO_ESCURO)
        for i, (nivel, txt) in enumerate(aud["alertas"], start=ult + 3):
            ws.cell(row=i, column=1, value="ATENÇÃO" if nivel == "atencao" else "Info").font = Font(bold=True, color="B25E00" if nivel == "atencao" else "555555")
            ws.cell(row=i, column=2, value=txt)
        _auto_largura(ws, maximo=24)
        ws.column_dimensions["A"].width = 26

    # ------------------------------------------------------------------ Premissas
    ws = wb.create_sheet("Premissas")
    _titulo(ws, "Premissas e critérios", "O que está por trás dos números — leia antes de usar em decisão de contrato.")
    _cabecalho(ws, 4, ["Tema", "Critério / premissa"])
    for i, (tema, txt) in enumerate(dados.get("premissas", []), start=5):
        _corpo(ws.cell(row=i, column=1, value=tema), i % 2 == 0, negrito=True)
        c = ws.cell(row=i, column=2, value=txt)
        _corpo(c, i % 2 == 0)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = max(30, 15 * (len(txt) // 110 + 1))
    _larguras(ws, {"A": 30, "B": 120})

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
