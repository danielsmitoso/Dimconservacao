"""Motor de calculo de dimensionamento de equipes de conservacao.

Logica geral (mesma usada nos estudos de SPVias/RioSP FS4.0):
    dias_disponiveis = meses_periodo x dias_uteis_mes
    dias_por_ciclo   = dias_disponiveis / ciclos_periodo
    demanda_diaria   = quantidade_total / dias_por_ciclo
    equipes          = demanda_diaria / produtividade_dia_por_equipe
"""
import math
from dataclasses import dataclass

DIAS_UTEIS_MES_PADRAO = 22


@dataclass
class ResultadoDimensionamento:
    cenario: str
    quantidade_total: float
    ciclos_periodo: float
    meses_periodo: float
    produtividade_dia: float
    demanda_diaria: float
    equipes_exatas: float
    equipes_arredondadas: int


def calcular_equipes(
    quantidade_total: float,
    produtividade_dia: float,
    ciclos_periodo: float,
    meses_periodo: float,
    dias_uteis_mes: float = DIAS_UTEIS_MES_PADRAO,
    cenario: str = "",
) -> ResultadoDimensionamento:
    """Calcula quantas equipes/equipamentos sao necessarios para atender
    `quantidade_total` (m2, km ou unidades) `ciclos_periodo` vezes dentro de
    `meses_periodo` meses, dada a produtividade diaria de uma equipe.
    """
    if quantidade_total <= 0 or ciclos_periodo <= 0 or produtividade_dia <= 0 or meses_periodo <= 0:
        return ResultadoDimensionamento(cenario, quantidade_total, ciclos_periodo, meses_periodo, produtividade_dia, 0.0, 0.0, 0)

    dias_disponiveis = meses_periodo * dias_uteis_mes
    dias_por_ciclo = dias_disponiveis / ciclos_periodo
    demanda_diaria = quantidade_total / dias_por_ciclo
    equipes_exatas = demanda_diaria / produtividade_dia
    equipes_arredondadas = math.ceil(round(equipes_exatas, 6))

    return ResultadoDimensionamento(
        cenario=cenario,
        quantidade_total=quantidade_total,
        ciclos_periodo=ciclos_periodo,
        meses_periodo=meses_periodo,
        produtividade_dia=produtividade_dia,
        demanda_diaria=demanda_diaria,
        equipes_exatas=equipes_exatas,
        equipes_arredondadas=equipes_arredondadas,
    )


def dimensionar_chuva_seca(
    quantidade_total: float,
    produtividade_dia: float,
    ciclos_chuva: float,
    meses_chuva: float,
    ciclos_seca: float,
    meses_seca: float,
    dias_uteis_mes: float = DIAS_UTEIS_MES_PADRAO,
) -> dict:
    """Roda o dimensionamento para os dois cenarios sazonais e retorna ambos
    lado a lado, junto com o pico (o que exige mais equipes)."""
    chuva = calcular_equipes(quantidade_total, produtividade_dia, ciclos_chuva, meses_chuva, dias_uteis_mes, "Chuva")
    seca = calcular_equipes(quantidade_total, produtividade_dia, ciclos_seca, meses_seca, dias_uteis_mes, "Seca")
    pico = chuva if chuva.equipes_arredondadas >= seca.equipes_arredondadas else seca
    return {"chuva": chuva, "seca": seca, "pico": pico}


def dividir_por_trecho(df_trechos, coluna_quantidade: str):
    """Dado um DataFrame com uma linha por trecho (colunas: trecho, extensao_km,
    e a coluna de quantidade informada), retorna o trecho com maior quantidade
    -- usado para saber onde alocar o equipamento mais produtivo primeiro."""
    if df_trechos.empty or coluna_quantidade not in df_trechos.columns:
        return None
    idx = df_trechos[coluna_quantidade].idxmax()
    return df_trechos.loc[idx]


def capacidade_por_ciclo(
    produtividade_dia_unidade: float,
    ciclos_periodo: float,
    meses_periodo: float,
    dias_uteis_mes: float = DIAS_UTEIS_MES_PADRAO,
) -> float:
    """Quanto UMA unidade (equipe ou equipamento) consegue produzir dentro de
    um ciclo completo de atendimento: (dias do período ÷ ciclos) × produtividade
    diária. É o "tamanho" do balde que a divisão por trecho precisa encher."""
    if ciclos_periodo <= 0 or meses_periodo <= 0 or produtividade_dia_unidade <= 0:
        return 0.0
    return (meses_periodo * dias_uteis_mes / ciclos_periodo) * produtividade_dia_unidade


def propor_divisao_por_trecho(
    df_trechos,
    coluna_quantidade: str,
    produtividade_dia_unidade: float,
    ciclos_periodo: float,
    meses_periodo: float,
    dias_uteis_mes: float = DIAS_UTEIS_MES_PADRAO,
    ocupacao_maxima_pct: float = 100.0,
    permitir_multi_rodovia: bool = True,
) -> list[dict]:
    """Propõe como dividir a rodovia entre unidades (equipes ou equipamentos)
    com o MÁXIMO aproveitamento: cada unidade é preenchida até a capacidade do
    ciclo antes de abrir a próxima.

    Como funciona (enchimento contínuo):
      1. Os trechos são percorridos em ordem (rodovia, km) -- assim cada
         unidade fica com um caminho contínuo, sem "pular" pela rodovia.
      2. A unidade atual recebe trecho após trecho até atingir a capacidade
         (`capacidade_ciclo` × `ocupacao_maxima_pct`).
      3. Se o trecho seguinte não cabe inteiro, ele é CORTADO no km exato em
         que a capacidade acaba (a parte que sobra vai para a próxima unidade).
         Isso elimina o desperdício de "trecho grande demais para sobrar
         espaço" que uma divisão só por trecho inteiro deixa.
    Resultado: todas as unidades ficam 100% ocupadas, exceto (no máximo) a
    última -- que é a menor sobra matemática possível. O número de unidades
    é sempre o mínimo (= ceil(total ÷ capacidade)) e bate com o
    dimensionamento por atividade.

    `permitir_multi_rodovia=False` reinicia a unidade a cada troca de rodovia
    (evita deslocamento entre rodovias distintas ao custo de mais unidades).

    Retorna uma lista de grupos, um por unidade, com: unidade (nº), trechos
    (rótulos), pedacos (detalhe, com km), quantidade_total, extensao_km,
    rodovias, multi_rodovia, capacidade_ciclo e ocupacao_pct (sobre a
    capacidade de 100%).
    """
    capacidade_ciclo = capacidade_por_ciclo(
        produtividade_dia_unidade, ciclos_periodo, meses_periodo, dias_uteis_mes
    )
    if capacidade_ciclo <= 0 or df_trechos is None or len(df_trechos) == 0:
        return []
    limite = capacidade_ciclo * max(ocupacao_maxima_pct, 1.0) / 100.0
    eps = capacidade_ciclo * 1e-9

    tem_km = "km_inicial" in df_trechos.columns and "km_final" in df_trechos.columns
    tem_rodovia = "rodovia" in df_trechos.columns
    linhas = []
    for ordem, (_, r) in enumerate(df_trechos.iterrows()):
        qtd = float(r[coluna_quantidade]) if coluna_quantidade in r.index else 0.0
        if qtd <= 0:
            continue
        linhas.append({
            "trecho": str(r["trecho"]),
            "rodovia": str(r["rodovia"]) if tem_rodovia else "",
            "km_i": float(r["km_inicial"]) if tem_km else None,
            "km_f": float(r["km_final"]) if tem_km else None,
            "qtd": qtd,
            "ordem": ordem,
        })
    # ordem = (rodovia na ordem em que aparece, km) -- contínuo dentro da rodovia
    ordem_rodovia = {}
    for l in linhas:
        ordem_rodovia.setdefault(l["rodovia"], len(ordem_rodovia))
    linhas.sort(key=lambda l: (ordem_rodovia[l["rodovia"]], l["km_i"] if l["km_i"] is not None else 0, l["ordem"]))

    grupos = []
    atual = {"pedacos": [], "quantidade_total": 0.0}

    def fechar():
        nonlocal atual
        if atual["pedacos"]:
            grupos.append(atual)
        atual = {"pedacos": [], "quantidade_total": 0.0}

    rodovia_anterior = None
    for l in linhas:
        if not permitir_multi_rodovia and rodovia_anterior is not None and l["rodovia"] != rodovia_anterior:
            fechar()
        rodovia_anterior = l["rodovia"]

        restante, inicio = l["qtd"], 0.0   # inicio = fração do trecho já alocada (0..1)
        while restante > eps:
            espaco = limite - atual["quantidade_total"]
            if espaco <= eps:
                fechar()
                continue
            usar = min(restante, espaco)
            fim = inicio + usar / l["qtd"]
            inteiro = inicio <= 1e-12 and fim >= 1 - 1e-9
            if l["km_i"] is not None:
                km_a = l["km_i"] + inicio * (l["km_f"] - l["km_i"])
                km_b = l["km_i"] + fim * (l["km_f"] - l["km_i"])
            else:
                km_a = km_b = None
            if inteiro:
                rotulo = l["trecho"]
            elif km_a is not None:
                rotulo = f"{l['trecho']} [km {km_a:.1f}–{km_b:.1f}]"
            else:
                rotulo = f"{l['trecho']} [{inicio * 100:.0f}%–{fim * 100:.0f}%]"
            atual["pedacos"].append({
                "rotulo": rotulo, "trecho": l["trecho"], "rodovia": l["rodovia"],
                "km_inicial": km_a, "km_final": km_b, "quantidade": usar, "inteiro": inteiro,
            })
            atual["quantidade_total"] += usar
            restante -= usar
            inicio = fim
    fechar()

    for i, g in enumerate(grupos, start=1):
        g["unidade"] = i
        g["trechos"] = [p["rotulo"] for p in g["pedacos"]]
        g["rodovias"] = sorted({p["rodovia"] for p in g["pedacos"] if p["rodovia"]})
        g["multi_rodovia"] = len(g["rodovias"]) > 1
        g["extensao_km"] = sum(
            (p["km_final"] - p["km_inicial"]) for p in g["pedacos"] if p["km_inicial"] is not None
        )
        g["capacidade_ciclo"] = capacidade_ciclo
        g["ocupacao_pct"] = round(100 * g["quantidade_total"] / capacidade_ciclo, 1)
    return grupos


def resumir_divisao(grupos: list[dict], capacidade_ciclo: float | None = None) -> dict:
    """Indicadores da divisão proposta: nº de unidades, ocupação média/mínima,
    folga total (em unidades equivalentes) e -- se sobrar pouco na última
    unidade -- a ocupação máxima que permitiria fechar com uma unidade a
    menos (para o usuário decidir se vale a pena)."""
    if not grupos:
        return {"n": 0, "ocupacao_media": 0.0, "ocupacao_minima": 0.0, "folga_unidades": 0.0, "ocupacao_para_n_menos_1": None}
    capacidade_ciclo = capacidade_ciclo or grupos[0]["capacidade_ciclo"]
    total = sum(g["quantidade_total"] for g in grupos)
    n = len(grupos)
    ocupacoes = [g["ocupacao_pct"] for g in grupos]
    return {
        "n": n,
        "ocupacao_media": round(sum(ocupacoes) / n, 1),
        "ocupacao_minima": min(ocupacoes),
        "folga_unidades": round(n - total / capacidade_ciclo, 2),
        "ocupacao_para_n_menos_1": round(100 * total / ((n - 1) * capacidade_ciclo), 1) if n > 1 else None,
    }
