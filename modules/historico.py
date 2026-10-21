"""Histórico: compara a planilha nova com o que já está gravado e calcula,
a partir das fotos de cada importação, o estado atual e a evolução.

Identidade de uma demanda = frente › entrega › ação (texto normalizado: sem
acento, minúsculo, espaços simples). Subgrupo não entra: mudar uma ação de
subgrupo não cria demanda nova. Quando a chave não bate, a prévia sugere a
correspondência e a pessoa confirma, nesta ordem:
  1. mesma ação em outra entrega da mesma frente (mudou de entrega, ou a
     entrega foi renomeada) -- só quando o par é único;
  2. mesma ação em outra frente (mudou de frente/aba) -- só quando único;
  3. ação renomeada na mesma frente: todas as palavras do nome antigo estão
     no novo (ex.: "Catalogar placas" -> "Estoque - Catalogar placas"), ou
     texto muito parecido (>= 85%).
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

from modules import importador as imp
from modules import regras

SIMILARIDADE_ACAO = 0.85         # nome da ação muito parecido = renomeada
NOTA_CONTIDA = 0.88              # nota dada quando o nome antigo está contido no novo
CAMPOS_COMPARADOS = [("status", "Status"), ("pct", "%"), ("data", "Prazo"), ("responsavel", "Responsável"),
                     ("peso", "Peso")]


# ---------------------------------------------------------------------------
# Chave da demanda
# ---------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def chaves(df: pd.DataFrame) -> list[str]:
    """frente|entrega|ação normalizados; repetições na mesma entrega ganham #2, #3..."""
    vistos: dict[str, int] = {}
    saida = []
    for f, e, a in zip(df["frente"], df["entrega"], df["acao"]):
        base = f"{normalizar(f)}|{normalizar(e)}|{normalizar(a)}"
        vistos[base] = vistos.get(base, 0) + 1
        saida.append(base if vistos[base] == 1 else f"{base}#{vistos[base]}")
    return saida


def _igual(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and not pd.isna(a) and not pd.isna(b):
        return abs(a - b) < 1e-9
    vazio_a = a is None or (isinstance(a, float) and pd.isna(a)) or a == ""
    vazio_b = b is None or (isinstance(b, float) and pd.isna(b)) or b == ""
    if vazio_a or vazio_b:
        return vazio_a and vazio_b
    return a == b


def _fmt(campo: str, v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return "—"
    if campo == "data":
        return v.strftime("%d/%m/%Y")
    if campo == "peso":
        return f"{v:g}"
    if campo == "pct":
        return f"{v:.0%}"
    return str(v)


# ---------------------------------------------------------------------------
# Estado atual e fotos
# ---------------------------------------------------------------------------
def _fotos(base: dict) -> pd.DataFrame:
    """Fotos válidas com a data de posição e a ordem da importação."""
    imps = base["importacoes"].reset_index(drop=True).assign(ordem=lambda d: range(len(d)))
    sit = base["situacoes"].merge(imps[["id", "data_posicao", "ordem", "enviado_por"]],
                                  left_on="importacao_id", right_on="id", how="inner").drop(columns="id")
    padrao = sit["status"].map(imp._pct)  # fotos antigas (antes de 21/10/2026) não guardavam o %
    sit["pct"] = (sit["pct"].where(sit["pct"].notna(), padrao) if "pct" in sit.columns else padrao).astype(float)
    return sit.sort_values(["demanda_id", "ordem"]).reset_index(drop=True)


def _como_acoes(sit: pd.DataFrame) -> pd.DataFrame:
    """Fotos no mesmo formato do importador (para reaproveitar regras.py)."""
    df = sit.rename(columns={"demanda_id": "id"}).copy()
    padrao = df["status"].map(imp._pct)
    df["pct"] = df["pct"].where(df["pct"].notna(), padrao) if "pct" in df.columns else padrao
    df["pct"] = df["pct"].astype(float)
    for c in ("subgrupo", "responsavel", "comentario", "nota"):
        df[c] = df[c].fillna("")
    return df[["id"] + imp.COLUNAS].reset_index(drop=True)


def estado_atual(base: dict) -> pd.DataFrame:
    """Uma linha por demanda (a foto mais recente), com os campos derivados:
    ativa, incluida_em, concluida_na_ultima, concluida_em, prazo_original,
    vezes_prazo_alterado e todos os comentários já registrados."""
    if base["importacoes"].empty:
        return pd.DataFrame(columns=["id"] + imp.COLUNAS)
    fotos = _fotos(base)
    ultima = int(fotos["ordem"].max()) if len(fotos) else -1
    extras = []
    for dem_id, g in fotos.groupby("demanda_id", sort=False):
        status = list(g["status"])
        concluida = [s == "Concluído" for s in status]
        concluida_em = None
        if concluida[-1] and not all(concluida):
            i = len(concluida) - 1
            while i > 0 and concluida[i - 1]:
                i -= 1
            concluida_em = g["data_posicao"].iloc[i]
        abertas = g[~pd.Series(concluida, index=g.index)]
        datas_abertas = [d for d in abertas["data"] if d is not None]
        mudancas = 0
        datas, ests = list(g["data"]), status
        for k in range(1, len(g)):
            if ests[k - 1] != "Concluído" and datas[k - 1] is not None and datas[k] is not None and datas[k] != datas[k - 1]:
                mudancas += 1
        comentarios = list(dict.fromkeys(c for h in g["historico"] for c in h))
        ultima_ordem = int(g["ordem"].iloc[-1])
        anterior_concl = len(g) > 1 and concluida[-2]
        extras.append({
            "demanda_id": dem_id,
            "ativa": ultima_ordem == ultima,
            "incluida_em": g["data_posicao"].iloc[0],
            "visto_por_ultimo_em": g["data_posicao"].iloc[-1],
            "concluida_em": concluida_em,
            "concluida_na_ultima": bool(concluida[-1] and ultima_ordem == ultima and len(g) > 1 and not anterior_concl),
            "prazo_original": datas_abertas[0] if datas_abertas else None,
            "vezes_prazo_alterado": mudancas,
            "comentarios": comentarios,
        })
    ultimas = fotos.groupby("demanda_id", sort=False).tail(1)
    atual = _como_acoes(ultimas).merge(pd.DataFrame(extras), left_on="id", right_on="demanda_id").drop(columns="demanda_id")
    return atual.sort_values(["aba", "linha"]).reset_index(drop=True)


def ultima_importacao(base: dict) -> dict | None:
    imps = base["importacoes"]
    return None if imps.empty else imps.iloc[-1].to_dict()


def evolucao(base: dict, frentes: list[str] | None = None) -> pd.DataFrame:
    """Indicadores de cada importação, calculados na data de posição dela."""
    fotos = _fotos(base)
    if frentes:
        fotos = fotos[fotos["frente"].isin(frentes)]
    linhas = []
    for (ordem, dpos, quem), g in fotos.groupby(["ordem", "data_posicao", "enviado_por"]):
        ind = regras.indicadores(regras.classificar(_como_acoes(g), dpos))
        linhas.append({"ordem": ordem, "data_posicao": dpos, "enviado_por": quem, **ind})
    return pd.DataFrame(linhas)


def eventos(base: dict) -> pd.DataFrame:
    """O que mudou de uma importação para a seguinte."""
    fotos = _fotos(base)
    imps = base["importacoes"].reset_index(drop=True)
    linhas = []
    estado: dict[int, dict] = {}   # última foto conhecida de cada demanda
    ativos_antes: set[int] = set()
    for ordem, imp_row in imps.iterrows():
        g = fotos[fotos["ordem"] == ordem]
        ativos = set(g["demanda_id"])
        comum = dict(ordem=ordem, data_posicao=imp_row["data_posicao"], enviado_por=imp_row["enviado_por"])
        for r in g.to_dict("records"):
            nome = f"{r['frente']} › {r['entrega']} › {r['acao']}"
            anterior = estado.get(r["demanda_id"])
            if anterior is None:
                if ordem > 0:
                    linhas.append({**comum, "demanda_id": r["demanda_id"], "demanda": nome, "tipo": "Nova demanda",
                                   "de": "", "para": r["status"]})
            else:
                if r["demanda_id"] not in ativos_antes:
                    linhas.append({**comum, "demanda_id": r["demanda_id"], "demanda": nome,
                                   "tipo": "Voltou para a planilha", "de": "", "para": r["status"]})
                if normalizar(anterior["acao"]) != normalizar(r["acao"]) or                         normalizar(anterior["entrega"]) != normalizar(r["entrega"]):
                    linhas.append({**comum, "demanda_id": r["demanda_id"], "demanda": nome, "tipo": "Renomeada",
                                   "de": f"{anterior['entrega']} › {anterior['acao']}", "para": f"{r['entrega']} › {r['acao']}"})
                for campo, rotulo in CAMPOS_COMPARADOS:
                    if campo == "pct" and anterior["status"] != r["status"]:
                        continue
                    if not _igual(anterior[campo], r[campo]):
                        linhas.append({**comum, "demanda_id": r["demanda_id"], "demanda": nome, "tipo": rotulo,
                                       "de": _fmt(campo, anterior[campo]), "para": _fmt(campo, r[campo])})
            estado[r["demanda_id"]] = r
        for dem_id in ativos_antes - ativos:
            r = estado[dem_id]
            linhas.append({**comum, "demanda_id": dem_id, "demanda": f"{r['frente']} › {r['entrega']} › {r['acao']}",
                           "tipo": "Saiu da planilha", "de": r["status"], "para": ""})
        ativos_antes = ativos
    return pd.DataFrame(linhas, columns=["ordem", "data_posicao", "enviado_por", "demanda_id", "demanda", "tipo", "de", "para"])


# ---------------------------------------------------------------------------
# Prévia da importação
# ---------------------------------------------------------------------------
@dataclass
class Plano:
    linhas: pd.DataFrame                      # planilha nova + chave, demanda_id, tipo, mudancas
    removidas: pd.DataFrame                   # demandas ativas que não vieram na planilha nova
    renomeacoes: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)   # avisos de estrutura da planilha (importador)

    def contagem(self, tipo: str) -> int:
        return int((self.linhas["tipo"] == tipo).sum())

    def resumo(self) -> dict:
        return {"acoes": len(self.linhas), "novas": self.contagem("nova"), "atualizadas": self.contagem("atualizada"),
                "sem_mudanca": self.contagem("sem_mudanca"), "voltaram": self.contagem("voltou"),
                "sairam": len(self.removidas), "renomeadas": len(self.renomeacoes), "avisos": self.avisos}


def planejar(novo: pd.DataFrame, base: dict, recusar: set[int] = frozenset()) -> Plano:
    """Casa cada linha da planilha nova com uma demanda gravada.

    recusar: ids de demandas cuja sugestão de renomeação a pessoa NÃO aceitou."""
    linhas = novo.copy().reset_index(drop=True)
    linhas["chave"] = chaves(linhas)
    atual = estado_atual(base)
    # Só demandas com alguma foto válida: uma demanda criada por importação desfeita
    # conta como nova (ao gravar, o banco reaproveita o mesmo registro pela chave).
    dem = base["demandas"]
    dem = dem[dem["id"].isin(atual["id"])] if len(dem) and len(atual) else dem.iloc[0:0]
    por_chave = dict(zip(dem["chave"], dem["id"]))
    linhas["demanda_id"] = linhas["chave"].map(por_chave).astype("Int64")

    ativos = atual[atual["ativa"]] if len(atual) else atual
    casados = set(linhas["demanda_id"].dropna().astype(int))
    sobrando = ativos[~ativos["id"].isin(casados)] if len(ativos) else ativos

    # Sugestões para linhas novas sem par x demandas ativas que sumiram (mesma frente)
    renomeacoes = []
    usados: set[int] = set()

    def sugerir(i, c, nota, motivo):
        usados.add(int(c.id))
        r = linhas.loc[i]
        renomeacoes.append({"demanda_id": int(c.id), "linha": int(i), "similaridade": nota, "motivo": motivo,
                            "de": f"{c.entrega} › {c.acao}", "para": f"{r['entrega']} › {r['acao']}"})
        if int(c.id) not in recusar:
            linhas.loc[i, "demanda_id"] = int(c.id)

    def candidatos(frente):
        if not len(sobrando):
            return []
        return [c for c in sobrando.itertuples() if c.frente == frente and int(c.id) not in usados]

    sem_par = list(linhas.index[linhas["demanda_id"].isna()])

    def acao_nova(k):
        return normalizar(linhas.loc[k, "acao"])

    def unico(i, cands, mesma_frente: bool):
        """Casa só se o par for único dos dois lados (evita 'Pacote B' de duas entregas)."""
        iguais = [k for k in sem_par if acao_nova(k) == acao_nova(i)
                  and (not mesma_frente or linhas.loc[k, "frente"] == linhas.loc[i, "frente"])]
        return cands[0] if len(cands) == 1 and len(iguais) == 1 else None

    def ja_sugerida(i):
        return any(r["linha"] == int(i) for r in renomeacoes)

    # 1) mesma ação na mesma frente, outra entrega
    for i in sem_par:
        cands = [c for c in candidatos(linhas.loc[i, "frente"]) if normalizar(c.acao) == acao_nova(i)]
        c = unico(i, cands, True)
        if c is not None:
            sugerir(i, c, 1.0, "mudou de entrega")
    # 2) mesma ação em outra frente
    for i in sem_par:
        if ja_sugerida(i):
            continue
        cands = [c for c in (sobrando.itertuples() if len(sobrando) else [])
                 if int(c.id) not in usados and c.frente != linhas.loc[i, "frente"] and normalizar(c.acao) == acao_nova(i)]
        c = unico(i, cands, False)
        if c is not None:
            sugerir(i, c, 1.0, "mudou de frente")
    # 3) renomeada (mesma frente)
    for i in sem_par:
        if ja_sugerida(i):
            continue
        r = linhas.loc[i]
        palavras_novas = set(re.findall(r"\w+", normalizar(r["acao"])))
        melhor, nota = None, 0.0
        for c in candidatos(r["frente"]):
            antigas = set(re.findall(r"\w+", normalizar(c.acao)))
            s_acao = difflib.SequenceMatcher(None, normalizar(r["acao"]), normalizar(c.acao)).ratio()
            nota_c = s_acao if s_acao >= SIMILARIDADE_ACAO else 0.0
            if len(antigas) >= 2 and antigas <= palavras_novas:
                nota_c = max(nota_c, NOTA_CONTIDA)
            if nota_c > nota:
                melhor, nota = c, nota_c
        if melhor is not None:
            sugerir(i, melhor, nota, "renomeada")

    atual_por_id = atual.set_index("id") if len(atual) else None
    tipos, mudancas = [], []
    for r in linhas.itertuples():
        if pd.isna(r.demanda_id):
            tipos.append("nova")
            mudancas.append("")
            continue
        ant = atual_por_id.loc[int(r.demanda_id)]
        difs = [f"{rot}: {_fmt(c, ant[c])} → {_fmt(c, getattr(r, c))}"
                for c, rot in CAMPOS_COMPARADOS if not _igual(ant[c], getattr(r, c))
                and not (c == "pct" and ant["status"] != r.status)]  # % muda junto com o status
        if normalizar(ant["acao"]) != normalizar(r.acao):
            difs.insert(0, f"Renomeada (era \"{ant['acao']}\")")
        if normalizar(ant["entrega"]) != normalizar(r.entrega):
            difs.insert(0, f"Entrega: {ant['entrega']} → {r.entrega}")
        if r.comentario and r.comentario != ant["comentario"]:
            difs.append("Comentário novo")
        tipos.append("voltou" if not ant["ativa"] else "atualizada" if difs else "sem_mudanca")
        mudancas.append("; ".join(difs))
    linhas["tipo"] = tipos
    linhas["mudancas"] = mudancas

    casados = set(linhas["demanda_id"].dropna().astype(int))
    removidas = ativos[~ativos["id"].isin(casados)] if len(ativos) else ativos
    return Plano(linhas=linhas, removidas=removidas, renomeacoes=renomeacoes)
