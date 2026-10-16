"""Roçada mecanizada: qual equipamento atende qual parte da área e quantas
unidades de cada um a frota precisa ter.

A área mecanizada de cada trecho é atribuída ao equipamento que a análise por
satélite (Quasar) indica para cada polígono. Quando o polígono indica mais de
um, são ALTERNATIVAS (qualquer um faria a área inteira) e a área vai para quem
aproveita melhor a frota (`alocar_alternativas`). Assim o número de unidades de
cada equipamento é aditivo (frota mista real) e pode ser comparado com a frota
disponível e levado à Análise de Contrato e ao relatório.
"""
import math

import pandas as pd

from modules import inventario as inv
from modules import parametros_padrao as pp
from modules import quasar


def produtividade_padrao(nome_equipamento: str) -> int:
    dados = pp.ROCADA_MECANIZADA.get(nome_equipamento)
    return dados["produtividade_dia_m2"] if dados else pp.PRODUTIVIDADE_EQUIPAMENTO_DESCONHECIDO


def areas_por_equipamento(df_inv: pd.DataFrame, equipamento_padrao: str | None = None):
    """Área mecanizada (m²) de cada trecho por equipamento.

    Devolve (DataFrame trechos × equipamentos, indicado_no_inventario). Se o
    inventário não traz equipamento (planilha sem `equipamento_predominante` e
    sem Quasar), toda a área mecanizada vai para `equipamento_padrao` e
    `indicado_no_inventario` é False -- o app avisa o usuário.
    """
    colunas = quasar.equipamentos_do_inventario(df_inv)
    if colunas:
        areas = pd.DataFrame({nome: df_inv[col] for nome, col in colunas.items()})
        indicado = True
    else:
        nome = equipamento_padrao or pp.EQUIPAMENTO_PADRAO_SEM_INDICACAO
        areas = pd.DataFrame({nome: inv.area_por_modalidade(df_inv, "mecanizada")})
        indicado = False
    areas = areas.loc[:, areas.sum() > 0]
    ordem = {n: i for i, n in enumerate(pp.ROCADA_MECANIZADA)}
    areas = areas[sorted(areas.columns, key=lambda n: ordem.get(n, 99))]
    return areas, indicado


def alocar_alternativas(areas: pd.DataFrame, produtividades: dict, capacidade_por_unidade: dict):
    """Decide quem executa as áreas com equipamentos ALTERNATIVOS
    (colunas 'A ou B'), para aproveitar ao máximo cada unidade da frota.

    As indicações do inventário são independentes: num polígono 'Trator 1.7m
    ou Spider' o trator poderia fazer 100% e o spider também -- não é uma
    divisão. Regra (decisão do usuário, 2026-10-16):
      1. A área exclusiva de cada equipamento define as unidades mínimas
         (arredondadas para cima); a fração não usada da última unidade é folga.
      2. A área com alternativas entra primeiro na folga das unidades que já
         vão existir (do equipamento de maior produtividade para o de menor).
      3. O que sobrar vai para a alternativa de maior produtividade (menos
         unidades novas); a folga criada já serve às áreas seguintes.

    `capacidade_por_unidade`: m² que uma unidade faz por ciclo no cenário de
    pico. Devolve (áreas só com equipamentos únicos, DataFrame explicando a
    alocação de cada combinação).
    """
    simples = [c for c in areas.columns if pp.SEPARADOR_ALTERNATIVAS not in c]
    combos = [c for c in areas.columns if pp.SEPARADOR_ALTERNATIVAS in c]
    todos = list(dict.fromkeys(simples + [p for c in combos for p in c.split(pp.SEPARADOR_ALTERNATIVAS)]))
    alocado = pd.DataFrame({n: areas[n] if n in areas.columns else 0.0 for n in todos}, index=areas.index).astype(float)
    if not combos:
        return alocado, pd.DataFrame()

    carga = {n: float(alocado[n].sum()) for n in todos}

    def folga(n):
        cap = capacidade_por_unidade.get(n, 0)
        if cap <= 0 or carga[n] <= 0:
            return 0.0
        return math.ceil(carga[n] / cap - 1e-9) * cap - carga[n]

    explicacao = []
    for combo in sorted(combos, key=lambda c: -areas[c].sum()):
        opcoes = sorted(combo.split(pp.SEPARADOR_ALTERNATIVAS), key=lambda n: -produtividades.get(n, 0))
        recebido = {n: 0.0 for n in opcoes}
        for idx, area in areas[combo].items():
            resto = float(area)
            for n in opcoes:  # 2. folga das unidades existentes
                if resto <= 0:
                    break
                usar = min(resto, folga(n))
                if usar > 0:
                    alocado.at[idx, n] += usar
                    carga[n] += usar
                    recebido[n] += usar
                    resto -= usar
            if resto > 0:  # 3. maior produtividade
                n = opcoes[0]
                alocado.at[idx, n] += resto
                carga[n] += resto
                recebido[n] += resto
        total = float(areas[combo].sum())
        explicacao.append({
            "Equipamentos alternativos": combo,
            "Área (m²)": round(total, 0),
            "Executado por": " · ".join(f"{n} {v:,.0f} m²" for n, v in recebido.items() if v > 0.5),
            "Critério": "folga de unidades já necessárias, depois o de maior produtividade",
        })
    alocado = alocado.loc[:, alocado.sum() > 0]
    ordem = {n: i for i, n in enumerate(pp.ROCADA_MECANIZADA)}
    return alocado[sorted(alocado.columns, key=lambda n: ordem.get(n, 99))], pd.DataFrame(explicacao)


def recomendacao_por_trecho(df_inv: pd.DataFrame, areas: pd.DataFrame) -> pd.DataFrame:
    """Para cada trecho com área mecanizada, indica o equipamento mais
    adequado (o que atende a maior parte da área), o mix de equipamentos
    quando o trecho é misto e a justificativa técnica."""
    linhas = []
    for idx in areas.index:
        linha_areas = areas.loc[idx]
        total = float(linha_areas.sum())
        if total <= 0:
            continue
        ordenado = linha_areas[linha_areas > 0].sort_values(ascending=False)
        principal = ordenado.index[0]
        pct_principal = 100 * float(ordenado.iloc[0]) / total
        mix = " · ".join(f"{n} {100 * v / total:.0f}%" for n, v in ordenado.items() if 100 * v / total >= 5)

        partes = []
        indicacao = pp.ROCADA_MECANIZADA.get(principal, {}).get("indicacao", "")
        if indicacao:
            partes.append(indicacao[0].upper() + indicacao[1:])
        if pct_principal < 60:
            partes.append("Trecho misto: nenhum equipamento sozinho atende a maior parte — planejar a combinação")
        largura = df_inv.loc[idx, "largura_media_m"] if "largura_media_m" in df_inv.columns else float("nan")
        inclinacao = df_inv.loc[idx, "inclinacao_media"] if "inclinacao_media" in df_inv.columns else float("nan")

        linhas.append({
            "Trecho": df_inv.loc[idx, "trecho"],
            "Rodovia": df_inv.loc[idx, "rodovia"] if "rodovia" in df_inv.columns else "",
            "Área mecanizada (m²)": round(total, 0),
            "Equipamento recomendado": principal,
            "% da área": round(pct_principal, 0),
            "Mix de equipamentos": mix,
            "Largura média (m)": None if pd.isna(largura) else round(float(largura), 1),
            "Inclinação média": None if pd.isna(inclinacao) else round(float(inclinacao), 1),
            "Justificativa técnica": ". ".join(partes),
        })
    return pd.DataFrame(linhas)
