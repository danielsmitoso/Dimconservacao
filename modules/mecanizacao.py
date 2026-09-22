"""Roçada mecanizada: qual equipamento atende qual parte da área e quantas
unidades de cada um a frota precisa ter.

Diferente da versão anterior (que calculava "se ESSE equipamento sozinho
fizesse tudo" e devolvia alternativas não somáveis), aqui a área mecanizada de
cada trecho é DISTRIBUÍDA entre os equipamentos que a análise por satélite
(Quasar) indica para cada polígono. Assim o número de unidades de cada
equipamento é aditivo (frota mista real) e pode ser comparado com a frota
disponível e levado à Análise de Contrato e ao relatório.
"""
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
