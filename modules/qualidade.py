"""Checagens de qualidade dos dados: o que impede um indicador confiável."""
from __future__ import annotations

import pandas as pd

from modules import regras


def _repetidas_entre_frentes(df: pd.DataFrame) -> pd.DataFrame:
    nome = df["acao"].map(lambda a: " ".join(str(a).lower().split()))
    frentes_por_nome = df.groupby(nome)["frente"].nunique()
    return df[nome.map(frentes_por_nome) > 1]


def checar(df: pd.DataFrame) -> list[dict]:
    """Lista de checagens com as ações afetadas. Recebe o df já classificado."""
    if df.empty:
        return []
    abertas = df[df["aberta"]]
    checagens = [
        ("Ação em aberto sem responsável", abertas[abertas["responsavel"].fillna("") == ""],
         "Sem dono, a ação não aparece na carga de ninguém."),
        ("Ação em aberto sem data prevista", abertas[abertas["sinal"] == regras.SEM_PRAZO],
         "Não entra no controle de atraso."),
        ("Sem status", df[df["status"] == "Sem status"],
         "Conta como 0% de avanço."),
        ("Status fora da lista", df[~df["status"].isin(regras.ORDEM_STATUS)],
         "Use À iniciar, Em andamento ou Concluído."),
        ("Sem peso", df[df["peso"].isna()],
         "Não entra no avanço ponderado (mesma regra da planilha)."),
        ("Mais de um responsável na mesma ação", df[df["varios_resp"]],
         "Conta na carga de cada pessoa; o ideal é um dono e os demais como apoio."),
        ("Área de apoio como responsável", abertas[abertas["externo"]],
         "Facilities, Frotas, Unidade... indicam dependência externa: vale ter um dono interno que cobra."),
        ("% não combina com o status", df[((df["status"] == "À iniciar") & (df["pct"] > 0))
                                         | ((df["status"] != "Concluído") & (df["pct"] >= 1))],
         "Ex.: \"À iniciar\" com % acima de 0, ou 100% sem estar \"Concluído\". O avanço usa o % digitado."),
        ("Mesma ação em mais de uma frente", _repetidas_entre_frentes(df),
         "Pode ser lançamento em duplicidade (a mesma tarefa contada duas vezes)."),
    ]
    return [{"checagem": nome, "qtd": len(itens), "dica": dica, "acoes": itens}
            for nome, itens, dica in checagens]


def pct_pendencias(df: pd.DataFrame) -> float:
    """Fração de ações com ao menos uma pendência de qualidade."""
    if df.empty:
        return 0.0
    ids = set()
    for c in checar(df):
        ids.update(c["acoes"]["id"])
    return len(ids) / len(df)
