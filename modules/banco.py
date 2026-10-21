"""Memória do app: grava cada importação da planilha num banco de dados.

Modelo ("fotos"):
- importacoes: uma linha por upload gravado (quem, quando, data de posição).
- demandas:    uma linha por demanda (identidade: frente › entrega › ação).
- situacoes:   a foto de cada demanda em cada importação (status, prazo...).

Tudo o que é "histórico" (quando concluiu, quantas vezes o prazo mudou, o que
mudou desde a última vez) é CALCULADO a partir das fotos, em historico.py --
nada derivado é gravado. Por isso desfazer uma importação é só marcá-la como
desfeita: as contas se refazem sozinhas sem ela.

Banco: Postgres do Supabase quando há `[banco] url` nos secrets; sem isso,
SQLite local (dados_locais/historico.db) -- útil para testar na máquina.
No Postgres as tabelas ficam no schema "gestao", que a API pública do
Supabase não expõe.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, MetaData, String, Table, Text,
                        create_engine, event, insert, inspect, select, text, update)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

SCHEMA_POSTGRES = "gestao"
SQLITE_LOCAL = Path(__file__).resolve().parent.parent / "dados_locais" / "historico.db"


def _metadata(schema: str | None) -> tuple[MetaData, Table, Table, Table]:
    md = MetaData(schema=schema)
    importacoes = Table(
        "importacoes", md,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("criado_em", DateTime(timezone=True), nullable=False),
        Column("data_posicao", Date, nullable=False),
        Column("arquivo", String(300)),
        Column("enviado_por", String(120), nullable=False),
        Column("resumo", Text),          # JSON com as contagens da prévia
        Column("desfeita", Boolean, nullable=False, default=False),
        Column("desfeita_por", String(120)),
    )
    demandas = Table(
        "demandas", md,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("chave", String(600), nullable=False, unique=True),
        Column("frente", String(200), nullable=False),
        Column("entrega", String(300), nullable=False),
        Column("subgrupo", String(300)),
        Column("acao", Text, nullable=False),
        Column("criada_na_importacao", Integer),
    )
    situacoes = Table(
        "situacoes", md,
        Column("importacao_id", Integer, ForeignKey(importacoes.c.id), primary_key=True),
        Column("demanda_id", Integer, ForeignKey(demandas.c.id), primary_key=True),
        Column("frente", String(200)),
        Column("entrega", String(300)),
        Column("subgrupo", String(300)),
        Column("acao", Text),
        Column("responsavel", String(300)),
        Column("status", String(60)),
        Column("peso", Float),
        Column("pct", Float),            # % da linha (digitado na planilha ou pelo status)
        Column("data", Date),
        Column("comentario", Text),
        Column("historico", Text),       # JSON [[semana, comentário], ...]
        Column("nota", Text),
        Column("aba", String(200)),
        Column("linha", Integer),
    )
    return md, importacoes, demandas, situacoes


class Banco:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.postgres = engine.dialect.name == "postgresql"
        self.md, self.importacoes, self.demandas, self.situacoes = _metadata(SCHEMA_POSTGRES if self.postgres else None)
        with engine.begin() as con:
            if self.postgres:
                con.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_POSTGRES}"))
        self.md.create_all(engine)
        self._migrar()

    def _migrar(self) -> None:
        """Acrescenta colunas criadas depois da primeira versão (o create_all não
        altera tabela que já existe). Seguro rodar sempre."""
        schema = SCHEMA_POSTGRES if self.postgres else None
        existentes = {c["name"] for c in inspect(self.engine).get_columns("situacoes", schema=schema)}
        tabela = f"{schema}.situacoes" if schema else "situacoes"
        with self.engine.begin() as con:
            if "pct" not in existentes:
                con.execute(text(f"ALTER TABLE {tabela} ADD COLUMN pct FLOAT"))

    @property
    def descricao(self) -> str:
        if self.postgres:
            return "banco online (Supabase)"
        if self.engine.url.database in (None, "", ":memory:"):
            return "banco de demonstração (temporário)"
        return "banco local nesta máquina"

    # ------------------------------------------------------------------ leitura
    def carregar(self) -> dict[str, pd.DataFrame]:
        """Lê as três tabelas (só importações não desfeitas e suas fotos)."""
        with self.engine.connect() as con:
            imp = pd.read_sql(select(self.importacoes).where(self.importacoes.c.desfeita.is_(False))
                              .order_by(self.importacoes.c.data_posicao, self.importacoes.c.id), con)
            dem = pd.read_sql(select(self.demandas), con)
            sit = pd.read_sql(select(self.situacoes).where(self.situacoes.c.importacao_id.in_(
                select(self.importacoes.c.id).where(self.importacoes.c.desfeita.is_(False)))), con)
        for df, col in ((imp, "data_posicao"), (sit, "data")):
            df[col] = pd.to_datetime(df[col]).dt.date
            df[col] = df[col].astype(object).where(df[col].notna(), None)
        sit["historico"] = sit["historico"].map(lambda t: [tuple(x) for x in json.loads(t)] if t else [])
        return {"importacoes": imp, "demandas": dem, "situacoes": sit}

    # ------------------------------------------------------------------ escrita
    def gravar_importacao(self, plano, data_posicao: date, arquivo: str, enviado_por: str) -> int:
        """Grava a planilha nova numa transação só (ou tudo, ou nada).

        plano: historico.Plano -- linhas da planilha com o id da demanda já
        existente (ou None, se nova) e as renomeações confirmadas."""
        agora = datetime.now(timezone.utc)
        with self.engine.begin() as con:
            imp_id = con.execute(insert(self.importacoes).values(
                criado_em=agora, data_posicao=data_posicao, arquivo=arquivo[:300], enviado_por=enviado_por[:120],
                resumo=json.dumps(plano.resumo(), ensure_ascii=False), desfeita=False,
            ).returning(self.importacoes.c.id)).scalar_one()

            linhas_sit = []
            for r in plano.linhas.itertuples():
                dem_id = r.demanda_id
                campos = dict(chave=r.chave, frente=r.frente, entrega=r.entrega, subgrupo=r.subgrupo, acao=r.acao)
                if pd.isna(dem_id):
                    existente = con.execute(select(self.demandas.c.id).where(self.demandas.c.chave == r.chave)).scalar()
                    if existente is None:  # outra pessoa pode ter criado a mesma demanda segundos antes
                        dem_id = con.execute(insert(self.demandas).values(**campos, criada_na_importacao=imp_id)
                                             .returning(self.demandas.c.id)).scalar_one()
                    else:
                        dem_id = existente
                else:
                    dem_id = int(dem_id)
                    # mantém o texto atual da demanda (renomeação, troca de subgrupo)
                    con.execute(update(self.demandas).where(self.demandas.c.id == dem_id).values(**campos))
                linhas_sit.append(dict(
                    importacao_id=imp_id, demanda_id=dem_id, frente=r.frente, entrega=r.entrega,
                    subgrupo=r.subgrupo, acao=r.acao, responsavel=r.responsavel, status=r.status,
                    peso=None if pd.isna(r.peso) else float(r.peso),
                    pct=None if pd.isna(r.pct) else float(r.pct), data=r.data, comentario=r.comentario,
                    historico=json.dumps(list(r.historico), ensure_ascii=False), nota=r.nota, aba=r.aba,
                    linha=int(r.linha)))
            if linhas_sit:
                con.execute(insert(self.situacoes), linhas_sit)
        return imp_id

    def desfazer_ultima(self, quem: str) -> int | None:
        """Marca a importação mais recente como desfeita (os dados continuam no
        banco, só deixam de contar). Devolve o id desfeito."""
        with self.engine.begin() as con:
            ultima = con.execute(select(self.importacoes.c.id).where(self.importacoes.c.desfeita.is_(False))
                                 .order_by(self.importacoes.c.data_posicao.desc(), self.importacoes.c.id.desc())
                                 .limit(1)).scalar()
            if ultima is None:
                return None
            con.execute(update(self.importacoes).where(self.importacoes.c.id == ultima)
                        .values(desfeita=True, desfeita_por=quem[:120]))
        return ultima


def normalizar_url(url: str) -> str:
    """Garante o driver psycopg2 (o do requirements.txt) no endereço do Postgres.

    O SQLAlchemy 2.1 passou a usar o driver "psycopg" (versão 3) quando o
    endereço é só "postgresql://" -- o que o Supabase fornece --, e o app
    quebrava com "No module named 'psycopg'"."""
    url = url.strip()
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg2://" + url[len(prefixo):]
    return url


def conectar(url: str | None) -> Banco:
    """url do Postgres (Supabase) ou None para o SQLite local.
    Use 'sqlite://' para um banco só em memória (modo demonstração)."""
    if url is None:
        SQLITE_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{SQLITE_LOCAL.as_posix()}"
    url = normalizar_url(url)
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)
        event.listen(engine, "connect", lambda con, _: con.execute("PRAGMA foreign_keys=ON"))
    else:
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800, pool_size=2, max_overflow=2)
    return Banco(engine)
