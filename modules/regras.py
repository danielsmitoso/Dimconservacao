"""Regras de gestão: sinal de cada ação, farol das entregas, avanço ponderado,
pontos de atenção, carga por responsável e pauta da reunião semanal.

Todas as regras dependem da DATA DE POSIÇÃO (hoje, por padrão) e ficam
concentradas aqui para que mudar um critério (ex.: quando a entrega fica
vermelha) seja uma alteração num lugar só.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd

# --- parâmetros das regras (editáveis) -----------------------------------
JANELA_DIAS = 7                     # "vence em breve" = prazo nos próximos N dias
AREAS_APOIO = {"facilities", "frotas", "unidade", "ti", "backoffice", "rh"}
PADRAO_AGUARDANDO = re.compile(
    r"aguard|chamado|requisi|[àa] receber|em an[áa]lise|retorno|pedido", re.IGNORECASE)
SEPARADORES_RESP = re.compile(r"\s*(?:,|/|;|\s+e\s+)\s*")
# Farol da entrega fica amarelo quando mais que esta fração das ações abertas está sem prazo
LIMITE_SEM_PRAZO = 0.5

# --- sinais --------------------------------------------------------------
CONCLUIDA, ATRASADA, VENCE, NO_PRAZO, SEM_PRAZO = "concluida", "atrasada", "vence", "no_prazo", "sem_prazo"
SINAIS = {
    ATRASADA: ("⚠️", "Atrasada"),
    VENCE: ("⏰", f"Vence em {JANELA_DIAS} dias"),
    NO_PRAZO: ("🟣", "No prazo"),
    SEM_PRAZO: ("⚪", "Sem prazo"),
    CONCLUIDA: ("✅", "Concluída"),
}
ORDEM_SINAIS = [ATRASADA, VENCE, NO_PRAZO, SEM_PRAZO, CONCLUIDA]

FAROL = {
    "concluida": ("✅", "Concluída"),
    "vermelho": ("🔴", "Crítica"),
    "amarelo": ("🟡", "Atenção"),
    "verde": ("🟢", "No prazo"),
}

ORDEM_STATUS = ["Concluído", "Em andamento", "À iniciar", "Sem status"]


def rotulo_sinal(sinal: str) -> str:
    icone, texto = SINAIS[sinal]
    return f"{icone} {texto}"


def separar_responsaveis(texto: str) -> list[str]:
    """'Lucas, Luiz e Carol' -> ['Lucas', 'Luiz', 'Carol']."""
    if not texto:
        return []
    return [p.strip() for p in SEPARADORES_RESP.split(texto) if p.strip()]


def _sinal(status: str, prazo, hoje: date) -> str:
    if status == "Concluído":
        return CONCLUIDA
    if prazo is None or pd.isna(prazo):
        return SEM_PRAZO
    if prazo < hoje:
        return ATRASADA
    if prazo <= hoje + timedelta(days=JANELA_DIAS):
        return VENCE
    return NO_PRAZO


def classificar(acoes: pd.DataFrame, hoje: date) -> pd.DataFrame:
    """Acrescenta sinal, dias de atraso, marcadores (aguardando, externo,
    vários responsáveis) e a lista de responsáveis individuais."""
    df = acoes.copy()
    if df.empty:
        for c in ("sinal", "rotulo_sinal", "aberta", "dias_atraso", "aguardando", "externo",
                  "responsaveis", "varios_resp"):
            df[c] = pd.Series(dtype=object)
        return df
    df["sinal"] = [_sinal(s, d, hoje) for s, d in zip(df["status"], df["data"])]
    df["rotulo_sinal"] = df["sinal"].map(rotulo_sinal)
    df["aberta"] = df["sinal"] != CONCLUIDA
    df["dias_atraso"] = [(hoje - d).days if s == ATRASADA else 0 for s, d in zip(df["sinal"], df["data"])]
    df["aguardando"] = df["aberta"] & df["comentario"].fillna("").map(lambda t: bool(PADRAO_AGUARDANDO.search(t)))
    df["responsaveis"] = df["responsavel"].fillna("").map(separar_responsaveis)
    df["varios_resp"] = df["responsaveis"].map(len) > 1
    df["externo"] = df["responsaveis"].map(lambda rs: bool(rs) and all(r.lower() in AREAS_APOIO for r in rs))
    return df


def avanco(df: pd.DataFrame) -> float:
    """Σ(peso × %) ÷ Σ peso -- mesma conta da planilha (ação sem peso não entra)."""
    com_peso = df[df["peso"].notna()]
    total = com_peso["peso"].sum()
    return float((com_peso["peso"] * com_peso["pct"]).sum() / total) if total else 0.0


def farol(df: pd.DataFrame) -> str:
    """Farol de um conjunto de ações (uma entrega)."""
    abertas = df[df["aberta"]]
    if abertas.empty:
        return "concluida"
    if (abertas["sinal"] == ATRASADA).any():
        return "vermelho"
    if (abertas["sinal"] == VENCE).any() or (abertas["sinal"] == SEM_PRAZO).mean() > LIMITE_SEM_PRAZO:
        return "amarelo"
    return "verde"


def rotulo_farol(chave: str) -> str:
    icone, texto = FAROL[chave]
    return f"{icone} {texto}"


def resumo_entregas(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for (frente, entrega), g in df.groupby(["frente", "entrega"], sort=False):
        datas = [d for d in g["data"] if d is not None and not pd.isna(d)]
        f = farol(g)
        linhas.append({
            "frente": frente, "entrega": entrega, "farol": f, "rotulo_farol": rotulo_farol(f),
            "acoes": len(g), "abertas": int(g["aberta"].sum()),
            "atrasadas": int((g["sinal"] == ATRASADA).sum()),
            "avanco": avanco(g), "prazo_final": max(datas) if datas else None,
        })
    return pd.DataFrame(linhas)


def resumo_frentes(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for frente, g in df.groupby("frente", sort=False):
        ent = resumo_entregas(g)
        linhas.append({
            "frente": frente, "entregas": len(ent), "acoes": len(g),
            "concluidas": int((g["sinal"] == CONCLUIDA).sum()),
            "atrasadas": int((g["sinal"] == ATRASADA).sum()),
            "vence": int((g["sinal"] == VENCE).sum()),
            "entregas_criticas": int((ent["farol"] == "vermelho").sum()),
            "avanco": avanco(g),
        })
    return pd.DataFrame(linhas)


def indicadores(df: pd.DataFrame) -> dict:
    n = len(df)
    conta = df["sinal"].value_counts() if n else pd.Series(dtype=int)
    return {
        "avanco": avanco(df) if n else 0.0,
        "acoes": n,
        "abertas": int(df["aberta"].sum()) if n else 0,
        "concluidas": int(conta.get(CONCLUIDA, 0)),
        "atrasadas": int(conta.get(ATRASADA, 0)),
        "vence": int(conta.get(VENCE, 0)),
        "sem_prazo": int(conta.get(SEM_PRAZO, 0)),
        "aguardando": int(df["aguardando"].sum()) if n else 0,
        "replanejadas": int((df["aberta"] & (df["vezes_prazo_alterado"] > 0)).sum())
        if n and "vezes_prazo_alterado" in df.columns else 0,
    }


def carga_responsaveis(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por pessoa. Ação com vários responsáveis conta para cada um."""
    if df.empty:
        return pd.DataFrame(columns=["responsavel", "externo", "acoes", "abertas", "atrasadas", "peso_aberto", "avanco"])
    exp = df.assign(pessoa=df["responsaveis"].map(lambda rs: rs or ["(sem responsável)"])).explode("pessoa")
    linhas = []
    for pessoa, g in exp.groupby("pessoa"):
        abertas = g[g["aberta"]]
        linhas.append({
            "responsavel": pessoa,
            "externo": pessoa.lower() in AREAS_APOIO,
            "acoes": len(g), "abertas": len(abertas),
            "atrasadas": int((g["sinal"] == ATRASADA).sum()),
            "peso_aberto": float(abertas["peso"].fillna(0).sum()),
            "avanco": avanco(g),
        })
    return pd.DataFrame(linhas).sort_values(["externo", "peso_aberto"], ascending=[True, False]).reset_index(drop=True)


def pontos_atencao(df: pd.DataFrame) -> list[tuple[int, str]]:
    """Bullets automáticos, do mais grave (3) para o menos grave (1)."""
    pontos: list[tuple[int, str]] = []
    for (frente, entrega), g in df.groupby(["frente", "entrega"], sort=False):
        atr = g[g["sinal"] == ATRASADA].sort_values("data")
        if len(atr):
            exemplos = "; ".join(f"{a} ({d:%d/%m})" for a, d in zip(atr["acao"].head(3), atr["data"].head(3)))
            mais = f" e mais {len(atr) - 3}" if len(atr) > 3 else ""
            pontos.append((3, f"**{frente} › {entrega}**: {len(atr)} ação(ões) atrasada(s) — {exemplos}{mais}"))
        if len(g) > 1 and (g["pct"] == 0).all():
            pontos.append((2, f"**{frente} › {entrega}**: entrega ainda com 0% de avanço ({len(g)} ações)"))
    abertas = df[df["aberta"]]
    ext = abertas[abertas["externo"]]
    if len(ext):
        areas = ", ".join(sorted(set(ext["responsavel"])))
        pontos.append((2, f"{len(ext)} ação(ões) em aberto dependem de áreas de apoio ({areas}) — cobrar fora da equipe"))
    ag = abertas[abertas["aguardando"]]
    if len(ag):
        pontos.append((2, f"{len(ag)} ação(ões) paradas aguardando terceiros (chamado, retorno, requisição)"))
    if "vezes_prazo_alterado" in abertas.columns:
        adiadas = abertas[abertas["vezes_prazo_alterado"] >= 2]
        if len(adiadas):
            nomes = "; ".join(f"{a} ({n}x)" for a, n in zip(adiadas["acao"].head(3), adiadas["vezes_prazo_alterado"].head(3)))
            pontos.append((2, f"{len(adiadas)} ação(ões) com o prazo adiado 2 vezes ou mais — {nomes}"))
    sp = abertas[abertas["sinal"] == SEM_PRAZO]
    if len(sp):
        pontos.append((1, f"{len(sp)} ação(ões) em aberto sem data prevista — não dá para saber se estão atrasadas"))
    return sorted(pontos, key=lambda p: -p[0])


def pauta(df: pd.DataFrame, hoje: date) -> dict[str, pd.DataFrame]:
    """Blocos da reunião semanal.

    Na planilha atual a mesma coluna guarda prazo e conclusão: para ação
    concluída, a data é tratada como data de conclusão."""
    if "concluida_na_ultima" in df.columns:  # com histórico: o que virou Concluído na última importação
        concl = df[df["concluida_na_ultima"].astype(bool)]
    else:
        inicio = hoje - timedelta(days=JANELA_DIAS)
        concl = df[(df["sinal"] == CONCLUIDA) & df["data"].map(lambda d: d is not None and not pd.isna(d) and inicio <= d <= hoje)]
    abertas = df[df["aberta"]]
    return {
        "concluido": concl.sort_values("data"),
        "atrasado": df[df["sinal"] == ATRASADA].sort_values("data"),
        "semana": df[df["sinal"] == VENCE].sort_values("data"),
        "impedimentos": abertas[abertas["aguardando"] | abertas["externo"]],
    }
