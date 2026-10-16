"""Roçada mecanizada: qual equipamento atende qual parte da área e quantas
unidades de cada um a frota precisa ter.

A área mecanizada de cada trecho é atribuída ao equipamento que a análise por
satélite (Quasar) indica para cada polígono. Quando o polígono indica mais de
um, são ALTERNATIVAS (qualquer um faria a área inteira) e a área vai para quem
aproveita melhor a frota (`alocar_frota`). Assim o número de unidades de
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


def alocar_frota(areas: pd.DataFrame, produtividades: dict, capacidade_por_unidade: dict,
                 substituicoes: dict | None = None):
    """Decide qual equipamento executa cada área para aproveitar ao máximo cada
    unidade da frota.

    Duas fontes de flexibilidade:
    - **Alternativas** (colunas 'A ou B'): o inventário indica mais de um
      equipamento para o polígono -- qualquer um faria a área inteira, não é
      divisão (decisão do usuário, 2026-10-16).
    - **Substituição** (`substituicoes`: {executor: [indicados que ele pode
      fazer]}): restrição de tamanho e acesso -- ex.: o Trator 1.7m entra onde o
      4.7m entra; o braço articulado faz área de Spider se alcançar.

    Passos:
      1. Área de um equipamento só vai para ele. A de alternativas preenche a
         folga das unidades já necessárias (do mais produtivo para o menos) e o
         resto vai para a alternativa mais produtiva.
      2. Enquanto der: pega o tipo cuja última unidade tem menos área e tenta
         passar essa área para a FOLGA de outros tipos que podem fazê-la
         (alternativa ou substituto). Se couber inteira, aquela unidade deixa de
         existir. Nunca cria unidade nova; cada passo tira 1 unidade da frota.

    `capacidade_por_unidade`: m² que uma unidade faz por ciclo no cenário de
    pico. Devolve (áreas por equipamento executor, DataFrame das alternativas,
    DataFrame das substituições aplicadas).
    """
    sep = pp.SEPARADOR_ALTERNATIVAS
    subs = {k: set(v) for k, v in (substituicoes or {}).items()}
    tipos = list(dict.fromkeys(p for c in areas.columns for p in c.split(sep)))
    cap = {t: float(capacidade_por_unidade.get(t, 0)) for t in tipos}
    prod = {t: produtividades.get(t, 0) for t in tipos}
    eps = 1e-6

    # Peças: (trecho, origem) com a área por executor
    pecas = []
    for origem in areas.columns:
        indicados = origem.split(sep)
        substitutos = [t for t in tipos if t not in indicados and subs.get(t, set()) & set(indicados)]
        for idx, area in areas[origem].items():
            if area > eps:
                pecas.append({"idx": idx, "origem": origem, "indicados": indicados,
                              "aptos": indicados + substitutos, "area": float(area), "aloc": {}})
    carga = {t: 0.0 for t in tipos}

    def unidades(t, c=None):
        c = carga[t] if c is None else c
        return math.ceil(c / cap[t] - 1e-9) if cap[t] > 0 and c > eps else 0

    def folga(t, c=None):
        c = carga[t] if c is None else c
        return unidades(t, c) * cap[t] - c if cap[t] > 0 else 0.0

    def mover(peca, t, valor):
        peca["aloc"][t] = peca["aloc"].get(t, 0.0) + valor
        carga[t] += valor

    # 1. exclusivos, depois alternativas
    for peca in pecas:
        if len(peca["indicados"]) == 1:
            mover(peca, peca["indicados"][0], peca["area"])
    for peca in sorted((p for p in pecas if len(p["indicados"]) > 1), key=lambda p: -p["area"]):
        opcoes = sorted(peca["indicados"], key=lambda t: -prod[t])
        resto = peca["area"]
        for t in opcoes:
            usar = min(resto, folga(t))
            if usar > eps:
                mover(peca, t, usar)
                resto -= usar
        if resto > eps:
            mover(peca, opcoes[0], resto)

    # 2. elimina unidades parciais usando a folga de quem pode fazer a área
    trocas = []
    while True:
        feito = False
        candidatos = [t for t in tipos if carga[t] > eps and cap[t] > 0]
        for t in sorted(candidatos, key=lambda t: carga[t] - (unidades(t) - 1) * cap[t]):
            sobra_t = carga[t] - (unidades(t) - 1) * cap[t]  # área na última unidade
            carga_sim = dict(carga)
            plano, falta = [], sobra_t
            for peca in sorted(pecas, key=lambda p: -p["aloc"].get(t, 0.0)):
                if falta <= eps:
                    break
                tem = peca["aloc"].get(t, 0.0)
                for s in sorted((x for x in peca["aptos"] if x != t), key=lambda x: -folga(x, carga_sim[x])):
                    if tem <= eps or falta <= eps:
                        break
                    usar = min(tem, falta, folga(s, carga_sim[s]))
                    if usar > eps:
                        plano.append((peca, s, usar))
                        carga_sim[s] += usar
                        tem -= usar
                        falta -= usar
            if falta <= 1e-3:
                for peca, s, usar in plano:
                    peca["aloc"][t] -= usar
                    carga[t] -= usar
                    mover(peca, s, usar)
                    trocas.append({"Indicado": peca["origem"], "Saiu de": t, "Executado por": s, "area": usar,
                                   "tipo": "Alternativa" if s in peca["indicados"] else "Substituição"})
                carga[t] = max(0.0, carga[t])
                feito = True
                break
        if not feito:
            break

    alocado = pd.DataFrame(0.0, index=areas.index, columns=tipos)
    for peca in pecas:
        for t, v in peca["aloc"].items():
            alocado.at[peca["idx"], t] += v
    alocado = alocado.loc[:, alocado.sum() > eps]
    ordem = {n: i for i, n in enumerate(pp.ROCADA_MECANIZADA)}
    alocado = alocado[sorted(alocado.columns, key=lambda n: ordem.get(n, 99))]

    explicacao = []
    for origem in sorted((c for c in areas.columns if sep in c), key=lambda c: -areas[c].sum()):
        recebido = {}
        for peca in (p for p in pecas if p["origem"] == origem):
            for t, v in peca["aloc"].items():
                recebido[t] = recebido.get(t, 0.0) + v
        explicacao.append({
            "Equipamentos alternativos": origem,
            "Área (m²)": round(float(areas[origem].sum()), 0),
            "Executado por": " · ".join(f"{n} {v:,.0f} m²" for n, v in sorted(recebido.items(), key=lambda x: -x[1]) if v > 0.5),
        })
    df_trocas = pd.DataFrame(trocas)
    if not df_trocas.empty:
        df_trocas = (df_trocas.groupby(["Saiu de", "Executado por", "tipo", "Indicado"], as_index=False)["area"].sum()
                     .rename(columns={"area": "Área (m²)", "tipo": "Por quê", "Indicado": "Indicação do inventário"}))
        df_trocas["Área (m²)"] = df_trocas["Área (m²)"].round(0)
        df_trocas = df_trocas[df_trocas["Área (m²)"] > 0].sort_values("Área (m²)", ascending=False)
    return alocado, pd.DataFrame(explicacao), df_trocas


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
