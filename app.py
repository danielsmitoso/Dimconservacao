"""Gestão de Demandas - painel de acompanhamento das demandas da equipe (Motiva).

Rodar localmente:
    streamlit run app.py

Consulte o README.md para instruções completas.

Princípio de interface (o mesmo do DimConservação): tudo que aparece na tela é
recalculado a cada alteração (data de posição, filtros). Os arquivos para
download são montados com o estado atual da tela.

Memória: cada planilha importada é gravada como uma "foto" no banco
(modules/banco.py); os painéis mostram a foto mais recente de cada demanda e a
aba Histórico mostra a evolução (modules/historico.py).
"""
import importlib
import json
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from modules import acesso
from modules import banco as bd
from modules import exemplo
from modules import export_excel
from modules import export_pptx
from modules import historico as hist
from modules import importador as imp
from modules import qualidade
from modules import regras

# Recarrega os módulos a cada execução para nunca rodar código antigo em memória.
for _m in (imp, regras, qualidade, hist, bd, acesso, exemplo, export_pptx, export_excel):
    importlib.reload(_m)

st.set_page_config(page_title="Gestão de Demandas", page_icon="📋", layout="wide")

LOGO_ROXA = Path(__file__).parent / "assets" / "logo_motiva_roxa.png"
if LOGO_ROXA.exists():
    st.logo(str(LOGO_ROXA))

st.markdown(
    """
    <style>
    div[data-testid="stMetric"] {
        background: #F7F4FE;
        border: 1px solid #E4DAFB;
        border-radius: 10px;
        padding: 12px 16px 8px 16px;
    }
    div[data-testid="stMetric"] label {
        color: #5E22F3 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: #5E22F3 !important;
    }
    h1, h2, h3 {
        color: #3D1A9E;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

CORES_STATUS = {"Concluído": "#3D1A9E", "Em andamento": "#8B62F7", "À iniciar": "#C9B8FB", "Sem status": "#D9D9E0"}
ROXO = "#5E22F3"


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Lendo a planilha...")
def ler(conteudo: bytes) -> imp.Resultado:
    return imp.ler_planilha(conteudo)


@st.cache_resource(show_spinner="Conectando ao banco...")
def banco_do_time(url: str | None) -> bd.Banco:
    return bd.conectar(url)


@st.cache_data(ttl=30, show_spinner="Lendo o histórico...")
def carregar_historico(_banco: bd.Banco, chave: str, versao: int) -> dict:
    """Cache curto: o que outra pessoa gravar aparece em até 30 s (ou ao gravar aqui)."""
    return _banco.carregar()


def banco_demonstracao(hoje: date) -> bd.Banco:
    """Banco temporário, só desta sessão, com duas semanas do exemplo fictício."""
    if "banco_demo" not in st.session_state:
        b = bd.conectar("sqlite://")
        for versao, posicao in ((1, hoje - timedelta(days=7)), (2, hoje)):
            novo = imp.ler_planilha(exemplo.gerar_planilha_exemplo(hoje, versao)).acoes
            b.gravar_importacao(hist.planejar(novo, b.carregar()), posicao, f"exemplo_semana{versao}.xlsx",
                                "Demonstração")
        st.session_state["banco_demo"] = b
    return st.session_state["banco_demo"]


def md(texto: str) -> str:
    """Evita que '$' vire fórmula e '*' vire negrito sem querer no markdown."""
    return str(texto).replace("$", "\\$").replace("*", "\\*")


def fmt_data(d) -> str:
    return d.strftime("%d/%m") if d is not None and not pd.isna(d) else "—"


def tabela_acoes(df: pd.DataFrame, colunas=("acao", "responsavel", "status", "peso", "data", "rotulo_sinal", "comentario"),
                 altura=None):
    """Tabela padrão de ações (mesmos nomes e formatos em todas as abas)."""
    if df.empty:
        st.caption("Nenhuma ação.")
        return
    vista = df.copy()
    vista["acao"] = [f"{s} › {a}" if s else a for s, a in zip(vista["subgrupo"], vista["acao"])]
    vista["frente_entrega"] = vista["frente"] + " › " + vista["entrega"]
    config = {
        "acao": st.column_config.TextColumn("Ação", width="large"),
        "frente_entrega": st.column_config.TextColumn("Frente › Entrega", width="medium"),
        "responsavel": "Responsável",
        "status": "Status",
        "peso": st.column_config.NumberColumn("Peso", format="%d"),
        "data": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
        "prazo_original": st.column_config.DateColumn("Prazo original", format="DD/MM/YYYY"),
        "vezes_prazo_alterado": st.column_config.NumberColumn("Prazo adiado (vezes)", format="%d"),
        "incluida_em": st.column_config.DateColumn("Entrou em", format="DD/MM/YYYY"),
        "visto_por_ultimo_em": st.column_config.DateColumn("Última vez na planilha", format="DD/MM/YYYY"),
        "rotulo_sinal": "Sinal",
        "dias_atraso": st.column_config.NumberColumn("Dias de atraso", format="%d"),
        "comentario": st.column_config.TextColumn("Último comentário", width="large"),
        "aba": "Aba", "linha": st.column_config.NumberColumn("Linha", format="%d"),
    }
    st.dataframe(vista[list(colunas)], column_config=config, hide_index=True, width="stretch",
                 height=altura or "auto")


def lista_pauta(df: pd.DataFrame, montar):
    if df.empty:
        st.caption("Nada neste bloco.")
        return
    st.markdown("\n".join(f"- {montar(r)}" for r in df.itertuples()))


# ---------------------------------------------------------------------------
# Cabeçalho, acesso e banco
# ---------------------------------------------------------------------------
st.title("📋 Gestão de Demandas")
acesso.exigir_senha()

c1, c2, c3 = st.columns([2, 1, 2])
nome_area = c1.text_input("Área / equipe avaliada", value="NTec — Gestão 4.0")
hoje = c2.date_input("Data de posição", value=date.today(), format="DD/MM/YYYY",
                     help="Prazos são comparados com esta data, e uma importação é gravada com ela. Padrão: hoje.")
with c3:
    st.markdown("&nbsp;")
    st.markdown(f"**Avaliando:** {md(nome_area)}  ·  posição em {hoje:%d/%m/%Y}")

demo = st.toggle("Modo demonstração (dados fictícios, nada é gravado no banco do time)", key="modo_demo")
try:
    if demo:
        banco_app = banco_demonstracao(hoje)
        dados_hist = banco_app.carregar()
    else:
        url_banco = acesso.segredo("banco", "url")
        banco_app = banco_do_time(url_banco)
        dados_hist = carregar_historico(banco_app, str(banco_app.engine.url), st.session_state.get("versao_banco", 0))
except Exception as erro:  # noqa: BLE001
    st.error("Não foi possível conectar ao banco de dados. Se o app ficou mais de 7 dias sem uso, o Supabase "
             "pausa o projeto: entre em supabase.com, abra o projeto e clique em **Restore**. "
             "Depois recarregue esta página.")
    with st.expander("Detalhe técnico"):
        st.code(str(erro)[:800])
    st.stop()

if not demo and not banco_app.postgres:
    st.caption("💻 Rodando com o banco local desta máquina (sem banco online configurado).")

ultima = hist.ultima_importacao(dados_hist)
if "aviso_gravacao" in st.session_state:
    st.success(st.session_state.pop("aviso_gravacao"))

# ---------------------------------------------------------------------------
# Importação (prévia + gravar)
# ---------------------------------------------------------------------------
with st.expander("📥 Importar planilha atualizada", expanded=ultima is None):
    st.markdown(
        "Envie a planilha **no formato atual da equipe** (uma aba por frente, linha roxa em negrito = entrega, "
        "linhas abaixo = ações). O app compara com o que já está gravado e mostra uma **prévia**; nada é "
        "gravado até você clicar em **Gravar importação**.")
    nome_usuario = st.text_input("Seu nome (fica registrado em quem importou)", key="nome_usuario")
    n_upload = st.session_state.get("n_upload", 0)
    arquivo = st.file_uploader("Enviar planilha (.xlsx)", type=["xlsx"], key=f"upload_{n_upload}")
    if arquivo is not None:
        lida = ler(arquivo.getvalue())
        if lida.acoes.empty:
            st.error("Nenhuma ação encontrada. Confira se as abas têm a linha de cabeçalho com **Tarefa** na coluna C.")
        else:
            plano = hist.planejar(lida.acoes, dados_hist)
            if plano.renomeacoes:
                st.markdown(f"**🔀 Parecem a mesma demanda ({len(plano.renomeacoes)})** — mudou de entrega ou de nome. "
                            "Desmarque as que forem demandas diferentes:")
                recusar = set()
                for r in plano.renomeacoes:
                    icone = "↪️" if r.get("motivo") == "mudou de entrega" else "✏️"
                    if not st.checkbox(f"{icone} “{r['de']}” → “{r['para']}”", value=True,
                                       key=f"ren_{n_upload}_{r['demanda_id']}"):
                        recusar.add(r["demanda_id"])
                if recusar:
                    plano = hist.planejar(lida.acoes, dados_hist, recusar)
            plano.avisos = lida.avisos
            res = plano.resumo()
            modelos = sorted(set(lida.modelos.values()))
            st.caption(f"Planilha reconhecida: **{len(lida.acoes)} ações** em {len(lida.abas_lidas)} abas "
                       f"({', '.join(lida.abas_lidas)}) · modelo {' / '.join(modelos)}"
                       + (f" · abas sem tarefas, ignoradas: {', '.join(lida.abas_ignoradas + lida.abas_vazias)}"
                          if lida.abas_ignoradas or lida.abas_vazias else ""))
            # Trava de segurança: status quase todos fora da lista = colunas lidas no lugar errado
            fora = (~lida.acoes["status"].isin(regras.ORDEM_STATUS)).mean()
            leitura_suspeita = fora > 0.3
            if leitura_suspeita:
                st.error(f"⛔ {fora:.0%} das ações vieram com um status que não é À iniciar / Em andamento / "
                         "Concluído. Isso indica que o app não reconheceu as colunas desta planilha. "
                         "**Não grave** — confira se o cabeçalho tem as colunas Tarefa, Responsável, Status, "
                         "Peso, % e Prazo, ou fale com quem mantém o app.")
            m = st.columns(5)
            m[0].metric("🆕 Novas", res["novas"] + res["voltaram"])
            m[1].metric("✏️ Atualizadas", res["atualizadas"])
            m[2].metric("＝ Sem mudança", res["sem_mudanca"])
            m[3].metric("📤 Saíram da planilha", res["sairam"])
            m[4].metric("Ações na planilha", res["acoes"])
            atualizadas = plano.linhas[plano.linhas["tipo"] == "atualizada"]
            if len(atualizadas):
                with st.expander(f"O que mudou ({len(atualizadas)})"):
                    st.dataframe(atualizadas[["frente", "entrega", "acao", "mudancas"]], hide_index=True, width="stretch",
                                 column_config={"frente": "Frente", "entrega": "Entrega", "acao": "Ação",
                                                "mudancas": st.column_config.TextColumn("Mudanças", width="large")})
            novas = plano.linhas[plano.linhas["tipo"].isin(["nova", "voltou"])]
            if len(novas):
                with st.expander(f"Demandas novas ({len(novas)})"):
                    st.dataframe(novas[["frente", "entrega", "acao", "responsavel", "status"]], hide_index=True,
                                 width="stretch")
            if len(plano.removidas):
                with st.expander(f"Saíram da planilha ({len(plano.removidas)}) — continuam no histórico"):
                    st.dataframe(plano.removidas[["frente", "entrega", "acao", "status"]], hide_index=True, width="stretch")
            if lida.avisos:
                with st.expander(f"Avisos de estrutura da planilha ({len(lida.avisos)})"):
                    st.markdown("\n".join(f"- {md(a)}" for a in lida.avisos))
            if ultima is not None and hoje < ultima["data_posicao"]:
                st.warning(f"A data de posição ({hoje:%d/%m/%Y}) é anterior à da última importação "
                           f"({ultima['data_posicao']:%d/%m/%Y}). Confira a data no topo antes de gravar.")
            if res["atualizadas"] + res["novas"] + res["voltaram"] + res["sairam"] == 0 and ultima is not None:
                st.info("Nada mudou em relação à última importação.")
            gravar = st.button("💾 Gravar importação", type="primary",
                               disabled=not nome_usuario.strip() or leitura_suspeita,
                               help=None if nome_usuario.strip() else "Preencha seu nome acima.")
            if gravar:
                try:
                    banco_app.gravar_importacao(plano, hoje, arquivo.name, nome_usuario.strip())
                except Exception as erro:  # noqa: BLE001
                    st.error(f"Não foi possível gravar (nada foi alterado). Tente de novo. Detalhe: {str(erro)[:300]}")
                else:
                    st.session_state["versao_banco"] = st.session_state.get("versao_banco", 0) + 1
                    st.session_state["n_upload"] = n_upload + 1
                    st.session_state["aviso_gravacao"] = (
                        f"✅ Importação gravada por {nome_usuario.strip()}: {res['novas'] + res['voltaram']} novas, "
                        f"{res['atualizadas']} atualizadas, {res['sairam']} saíram da planilha.")
                    st.rerun()
    st.download_button("Baixar planilha de exemplo / modelo", data=exemplo.gerar_planilha_exemplo(hoje),
                       file_name="gestao_demandas_exemplo.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("🔒 Dica de LGPD: em temas de RH, prefira o cargo ao nome da pessoa "
               "(ex.: \"Desligamento – Assistente HubSP\").")

if ultima is None:
    st.info("Nenhuma importação gravada ainda. Envie a planilha acima e clique em **Gravar importação** — "
            "ou ligue o **modo demonstração** para conhecer o app.")
    st.stop()

n_imp = len(dados_hist["importacoes"])
st.markdown(f"📚 **{n_imp} importação(ões) gravada(s)** · última com posição em "
            f"{ultima['data_posicao']:%d/%m/%Y}, por {md(ultima['enviado_por'])} · {banco_app.descricao}")
avisos_ultima = json.loads(ultima["resumo"] or "{}").get("avisos", [])

# ---------------------------------------------------------------------------
# Filtros (valem para todas as abas e para os arquivos exportados)
# ---------------------------------------------------------------------------
atual = hist.estado_atual(dados_hist)
f1, f2, f3 = st.columns([2, 2, 1])
incluir_saidas = f3.toggle("Incluir as que saíram da planilha", value=False,
                           help="Demandas apagadas da planilha continuam gravadas com o último status conhecido.")
if not incluir_saidas:
    atual = atual[atual["ativa"]]
base = regras.classificar(atual, hoje)
frentes_sel = f1.multiselect("Frente", list(dict.fromkeys(base["frente"])), placeholder="Todas")
pessoas = sorted({p for rs in base["responsaveis"] for p in rs})
pessoas_sel = f2.multiselect("Responsável", pessoas, placeholder="Todos")
df = base
if frentes_sel:
    df = df[df["frente"].isin(frentes_sel)]
if pessoas_sel:
    df = df[df["responsaveis"].map(lambda rs: any(p in pessoas_sel for p in rs))]
if df.empty:
    st.warning("Nenhuma ação com os filtros escolhidos.")
    st.stop()

ind = regras.indicadores(df)

aba_geral, aba_frentes, aba_resp, aba_prazos, aba_pauta, aba_hist, aba_qual, aba_export = st.tabs([
    "📊 Visão geral", "🗂️ Frentes e entregas", "👥 Responsáveis", "📅 Prazos",
    "📝 Pauta semanal", "🕓 Histórico", "🔎 Qualidade dos dados", "📑 Exportar"])

# ---------------------------------------------------------------------------
# Visão geral
# ---------------------------------------------------------------------------
with aba_geral:
    m = st.columns(4)
    m[0].metric("Avanço geral", f"{ind['avanco']:.0%}", help="Σ(peso × %) ÷ Σ peso, com % pelo status (0/50/100%)")
    m[1].metric("Ações", ind["acoes"], f"{ind['abertas']} em aberto", delta_color="off", delta_arrow="off")
    m[2].metric("✅ Concluídas", ind["concluidas"], f"{ind['concluidas'] / ind['acoes']:.0%} do total", delta_color="off", delta_arrow="off")
    m[3].metric("⚠️ Atrasadas", ind["atrasadas"], "prazo vencido", delta_color="off", delta_arrow="off")
    m = st.columns(5)
    m[0].metric(f"⏰ Vencem em {regras.JANELA_DIAS} dias", ind["vence"],
                f"até {hoje + pd.Timedelta(days=regras.JANELA_DIAS):%d/%m}", delta_color="off", delta_arrow="off")
    m[1].metric("⚪ Sem prazo", ind["sem_prazo"], "fora do controle de atraso", delta_color="off", delta_arrow="off")
    m[2].metric("⏳ Aguardando terceiros", ind["aguardando"], "chamado, retorno, requisição", delta_color="off", delta_arrow="off")
    m[3].metric("🔁 Prazos replanejados", ind["replanejadas"], "em aberto, prazo mudou", delta_color="off",
                delta_arrow="off")
    m[4].metric("🔎 Ações com pendência de dado", f"{qualidade.pct_pendencias(df):.0%}", "ver aba Qualidade",
                delta_color="off", delta_arrow="off")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### Status das ações por frente")
        cont = df.groupby(["frente", "status"]).size().reset_index(name="ações")
        ordem_frentes = list(dict.fromkeys(df["frente"]))
        dominio = [s for s in regras.ORDEM_STATUS if s in set(cont["status"])] + \
                  sorted(set(cont["status"]) - set(regras.ORDEM_STATUS))
        cores = [CORES_STATUS.get(s, "#9A9AA8") for s in dominio]
        graf = alt.Chart(cont).mark_bar(cornerRadius=3, stroke="white", strokeWidth=2).encode(
            y=alt.Y("frente:N", sort=ordem_frentes, title=None),
            x=alt.X("ações:Q", title="Ações"),
            color=alt.Color("status:N", scale=alt.Scale(domain=dominio, range=cores),
                            legend=alt.Legend(orient="top", title=None)),
            order=alt.Order("ordem:Q"),
            tooltip=["frente", "status", "ações"],
        ).transform_calculate(ordem=f"indexof({dominio}, datum.status)").properties(height=max(160, 45 * len(ordem_frentes)))
        st.altair_chart(graf, width="stretch")
    with g2:
        st.markdown("#### Avanço ponderado por frente")
        fr = regras.resumo_frentes(df)
        base_av = alt.Chart(fr).encode(y=alt.Y("frente:N", sort=list(fr["frente"]), title=None))
        barras = base_av.mark_bar(cornerRadius=3, color=ROXO).encode(
            x=alt.X("avanco:Q", title="Avanço", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
            tooltip=[alt.Tooltip("frente", title="Frente"), alt.Tooltip("avanco:Q", title="Avanço", format=".0%"),
                     alt.Tooltip("acoes", title="Ações"), alt.Tooltip("atrasadas", title="Atrasadas")])
        rotulos = base_av.mark_text(align="left", dx=4, color="#1A1A2E").encode(
            x="avanco:Q", text=alt.Text("avanco:Q", format=".0%"))
        st.altair_chart((barras + rotulos).properties(height=max(160, 45 * len(fr))), width="stretch")

    st.markdown("### ⚠️ Pontos de atenção")
    pontos = regras.pontos_atencao(df)
    if pontos:
        st.markdown("\n".join(f"- {'🔴' if g == 3 else '🟡' if g == 2 else '⚪'} {t.replace('$', chr(92) + '$')}"
                              for g, t in pontos))
    else:
        st.success("Nada crítico com os filtros atuais.")

# ---------------------------------------------------------------------------
# Frentes e entregas
# ---------------------------------------------------------------------------
with aba_frentes:
    ent = regras.resumo_entregas(df)
    o1, o2 = st.columns([1, 2])
    ordem = o1.radio("Ordem das entregas", ["Como na planilha", "Mais críticas primeiro"], horizontal=True)
    farois = o2.multiselect("Mostrar farol", [regras.rotulo_farol(k) for k in regras.FAROL],
                            placeholder="Todos")
    st.caption("Farol: 🔴 alguma ação atrasada · 🟡 algo vence em 7 dias ou mais da metade sem prazo · "
               "🟢 tudo no prazo · ✅ todas concluídas")
    if ordem == "Mais críticas primeiro":
        peso_farol = {"vermelho": 0, "amarelo": 1, "verde": 2, "concluida": 3}
        ent = ent.assign(_o=ent["farol"].map(peso_farol)).sort_values(["frente", "_o", "atrasadas"],
                                                                       ascending=[True, True, False], kind="stable")
    if farois:
        ent = ent[ent["rotulo_farol"].isin(farois)]
    for frente in dict.fromkeys(ent["frente"]):
        acoes_frente = df[df["frente"] == frente]
        st.markdown(f"### {md(frente)}  ·  avanço {regras.avanco(acoes_frente):.0%}")
        for e in ent[ent["frente"] == frente].itertuples():
            rotulo = (f"{regras.FAROL[e.farol][0]} **{md(e.entrega)}** · {e.acoes} ações · {e.avanco:.0%} · "
                      f"prazo final {fmt_data(e.prazo_final)}" + (f" · ⚠️ {e.atrasadas} atrasada(s)" if e.atrasadas else ""))
            with st.expander(rotulo, expanded=False):
                st.progress(e.avanco)
                tabela_acoes(acoes_frente[acoes_frente["entrega"] == e.entrega])

# ---------------------------------------------------------------------------
# Responsáveis
# ---------------------------------------------------------------------------
with aba_resp:
    st.caption("Ação com mais de um responsável conta para cada um. Áreas de apoio (Facilities, Frotas, "
               "Unidade...) aparecem separadas como dependência externa.")
    carga = regras.carga_responsaveis(df)
    cfg = {
        "responsavel": "Responsável", "acoes": "Ações", "abertas": "Em aberto", "atrasadas": "Atrasadas",
        "peso_aberto": st.column_config.ProgressColumn("Peso em aberto", format="%d", min_value=0,
                                                       max_value=float(max(carga["peso_aberto"].max(), 1))),
        "avanco": st.column_config.ProgressColumn("Avanço", format="percent", min_value=0, max_value=1),
    }
    colunas = ["responsavel", "acoes", "abertas", "atrasadas", "peso_aberto", "avanco"]
    st.markdown("#### Equipe")
    st.dataframe(carga[~carga["externo"]][colunas], column_config=cfg, hide_index=True, width="stretch")
    if carga["externo"].any():
        st.markdown("#### Dependência externa (áreas de apoio)")
        st.dataframe(carga[carga["externo"]][colunas], column_config=cfg, hide_index=True, width="stretch")
    pessoa = st.selectbox("Ver ações em aberto de", ["—"] + list(carga["responsavel"]))
    if pessoa != "—":
        alvo = df[df["aberta"] & df["responsaveis"].map(lambda rs: pessoa in rs or (pessoa == "(sem responsável)" and not rs))]
        tabela_acoes(alvo.sort_values("data", key=lambda s: s.map(lambda d: d or date.max)),
                     colunas=("acao", "frente_entrega", "status", "peso", "data", "rotulo_sinal", "comentario"))

# ---------------------------------------------------------------------------
# Prazos
# ---------------------------------------------------------------------------
with aba_prazos:
    abertas = df[df["aberta"]].copy()
    com_data = abertas[abertas["data"].notna()].copy()
    if not com_data.empty:
        st.markdown("#### Ações em aberto por semana de prazo")
        inicio_semana = hoje - pd.Timedelta(days=hoje.weekday())
        com_data["semana"] = [("Atrasadas" if s == regras.ATRASADA else
                               f"{(d - pd.Timedelta(days=d.weekday())):%d/%m}") for s, d in zip(com_data["sinal"], com_data["data"])]
        com_data["ordem"] = [(-1 if s == regras.ATRASADA else (d - inicio_semana).days) for s, d in zip(com_data["sinal"], com_data["data"])]
        sem = com_data.groupby("semana").agg(ações=("id", "size"), ordem=("ordem", "min")).reset_index()
        sem["tipo"] = sem["semana"].map(lambda s: "Atrasadas" if s == "Atrasadas" else "No prazo")
        graf = alt.Chart(sem).mark_bar(cornerRadius=3).encode(
            x=alt.X("semana:N", sort=alt.EncodingSortField("ordem"), title="Semana do prazo (segunda-feira)"),
            y=alt.Y("ações:Q", title="Ações em aberto"),
            color=alt.Color("tipo:N", scale=alt.Scale(domain=["Atrasadas", "No prazo"], range=["#C4314B", ROXO]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["semana", "ações"]).properties(height=240)
        st.altair_chart(graf, width="stretch")
    blocos = [(regras.ATRASADA, "⚠️ Atrasadas"), (regras.VENCE, f"⏰ Vencem nos próximos {regras.JANELA_DIAS} dias"),
              (regras.NO_PRAZO, "🟣 Mais adiante"), (regras.SEM_PRAZO, "⚪ Sem prazo definido")]
    for sinal, titulo in blocos:
        parte = abertas[abertas["sinal"] == sinal]
        st.markdown(f"#### {titulo} ({len(parte)})")
        cols = ("data", "acao", "frente_entrega", "responsavel", "status", "comentario")
        if sinal == regras.ATRASADA:
            cols = ("data", "dias_atraso") + cols[1:]
        tabela_acoes(parte.sort_values("data") if sinal != regras.SEM_PRAZO else parte, colunas=cols)

# ---------------------------------------------------------------------------
# Pauta semanal
# ---------------------------------------------------------------------------
with aba_pauta:
    st.caption("Roteiro para a reunião semanal. Sai também no PowerPoint (aba Exportar). "
               "\"Concluído\" = ações que viraram Concluído na última importação gravada.")
    p = regras.pauta(df, hoje)
    st.markdown(f"### 1. ✅ Concluído desde a importação anterior ({len(p['concluido'])})")
    lista_pauta(p["concluido"], lambda r: f"{md(r.acao)} — *{md(r.responsavel)}, {fmt_data(r.data)}*")
    st.markdown(f"### 2. ⚠️ Atrasado — o que destrava? ({len(p['atrasado'])})")
    lista_pauta(p["atrasado"], lambda r: f"**{md(r.acao)}** ({md(r.responsavel) or 'sem responsável'}, "
                                         f"era {fmt_data(r.data)}, {r.dias_atraso} dias) — {md(r.comentario) or '_sem comentário_'}")
    st.markdown(f"### 3. ⏰ Compromissos da semana ({len(p['semana'])})")
    lista_pauta(p["semana"], lambda r: f"{md(r.acao)} — *{md(r.responsavel) or 'sem responsável'}, {fmt_data(r.data)}*")
    st.markdown(f"### 4. ⏳ Impedimentos e dependências ({len(p['impedimentos'])})")
    lista_pauta(p["impedimentos"], lambda r: f"{md(r.acao)} — *{md(r.responsavel)}*: {md(r.comentario) or '_sem comentário_'}")

# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------
with aba_hist:
    evo = hist.evolucao(dados_hist, frentes_sel or None)
    evs = hist.eventos(dados_hist)
    if frentes_sel:
        evs = evs[evs["demanda"].map(lambda d: d.split(" › ")[0] in frentes_sel)]
    st.caption("Cada importação gravada é uma foto da planilha. Os indicadores abaixo são recalculados na data "
               "de posição de cada foto." + (" O filtro de responsável não se aplica a esta aba." if pessoas_sel else ""))
    if len(evo) >= 2:
        h1, h2 = st.columns(2)
        eixo_x = alt.X("data_posicao:T", title="Data de posição", axis=alt.Axis(format="%d/%m"))
        with h1:
            st.markdown("#### Avanço geral por importação")
            base_evo = alt.Chart(evo).encode(x=eixo_x, y=alt.Y("avanco:Q", title="Avanço",
                                                                 scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                                             tooltip=[alt.Tooltip("data_posicao:T", title="Posição", format="%d/%m/%Y"),
                                                      alt.Tooltip("avanco:Q", title="Avanço", format=".0%"),
                                                      alt.Tooltip("enviado_por", title="Importado por")])
            st.altair_chart((base_evo.mark_line(color=ROXO, strokeWidth=2) +
                             base_evo.mark_point(color=ROXO, filled=True, size=70)).properties(height=240),
                            width="stretch")
        with h2:
            st.markdown("#### Ações atrasadas por importação")
            st.altair_chart(alt.Chart(evo).mark_bar(color="#C4314B", cornerRadius=3, size=22).encode(
                x=eixo_x, y=alt.Y("atrasadas:Q", title="Atrasadas", axis=alt.Axis(tickMinStep=1, format="d")),
                tooltip=[alt.Tooltip("data_posicao:T", title="Posição", format="%d/%m/%Y"),
                         alt.Tooltip("atrasadas:Q", title="Atrasadas"), alt.Tooltip("abertas:Q", title="Em aberto")],
            ).properties(height=240), width="stretch")
    else:
        st.info("Os gráficos de evolução aparecem a partir da segunda importação gravada.")

    st.markdown("#### O que mudou na última importação")
    ultimas_mud = evs[evs["ordem"] == evs["ordem"].max()] if len(evs) and n_imp > 1 else evs.iloc[0:0]
    if n_imp < 2:
        st.caption("Ainda só há uma importação — as mudanças aparecem a partir da segunda.")
    elif ultimas_mud.empty:
        st.caption("Nada mudou.")
    else:
        st.dataframe(ultimas_mud[["tipo", "demanda", "de", "para"]], hide_index=True, width="stretch",
                     column_config={"tipo": "Mudança", "demanda": st.column_config.TextColumn("Demanda", width="large"),
                                    "de": "De", "para": "Para"})

    replan = df[df["aberta"] & (df["vezes_prazo_alterado"] > 0)].sort_values("vezes_prazo_alterado", ascending=False)
    st.markdown(f"#### 🔁 Prazos replanejados ({len(replan)})")
    st.caption("Ações em aberto cujo prazo mudou entre importações. Adiar várias vezes costuma indicar algo travado.")
    tabela_acoes(replan, colunas=("acao", "frente_entrega", "responsavel", "prazo_original", "data",
                                  "vezes_prazo_alterado", "comentario"))

    st.markdown("#### 🔎 Linha do tempo de uma demanda")
    todas = hist.estado_atual(dados_hist)
    opcoes = {f"{r.frente} › {r.entrega} › {r.acao}" + ("" if r.ativa else " (saiu da planilha)"): r.id
              for r in todas.itertuples()}
    escolha = st.selectbox("Demanda", ["—"] + list(opcoes), key="linha_tempo")
    if escolha != "—":
        dem_id = opcoes[escolha]
        info = todas[todas["id"] == dem_id].iloc[0]
        st.markdown(f"Entrou em **{fmt_data(info['incluida_em'])}** · status atual **{info['status']}** · "
                    f"prazo {fmt_data(info['data'])}"
                    + (f" (original {fmt_data(info['prazo_original'])}, mudou {info['vezes_prazo_alterado']}x)"
                       if info["vezes_prazo_alterado"] else ""))
        linha = evs[evs["demanda_id"] == dem_id]
        if len(linha):
            st.dataframe(linha[["data_posicao", "enviado_por", "tipo", "de", "para"]], hide_index=True, width="stretch",
                         column_config={"data_posicao": st.column_config.DateColumn("Posição", format="DD/MM/YYYY"),
                                        "enviado_por": "Importado por", "tipo": "Mudança", "de": "De", "para": "Para"})
        if info["comentarios"]:
            st.markdown("**Comentários registrados**\n" +
                        "\n".join(f"- *{md(sem)}*: {md(txt)}" for sem, txt in info["comentarios"]))

    saidas = hist.estado_atual(dados_hist)
    saidas = saidas[~saidas["ativa"]]
    if frentes_sel:
        saidas = saidas[saidas["frente"].isin(frentes_sel)]
    st.markdown(f"#### 📤 Saíram da planilha ({len(saidas)})")
    st.caption("Continuam gravadas com o último status conhecido. Para vê-las nos painéis, ligue "
               "\"Incluir as que saíram da planilha\" nos filtros.")
    tabela_acoes(saidas, colunas=("acao", "frente_entrega", "responsavel", "status", "visto_por_ultimo_em"))

    st.markdown("#### 📚 Importações gravadas")
    imps = dados_hist["importacoes"].iloc[::-1].copy()
    resumos = imps["resumo"].map(lambda t: json.loads(t or "{}"))
    imps["resumo_txt"] = resumos.map(lambda r: f"{r.get('novas', 0) + r.get('voltaram', 0)} novas · "
                                               f"{r.get('atualizadas', 0)} atualizadas · {r.get('sairam', 0)} saíram")
    st.dataframe(imps[["data_posicao", "enviado_por", "criado_em", "arquivo", "resumo_txt"]], hide_index=True,
                 width="stretch", column_config={
                     "data_posicao": st.column_config.DateColumn("Posição", format="DD/MM/YYYY"),
                     "enviado_por": "Importado por",
                     "criado_em": st.column_config.DatetimeColumn("Gravado em (UTC)", format="DD/MM/YYYY HH:mm"),
                     "arquivo": "Arquivo", "resumo_txt": "Resumo"})
    with st.expander("↩️ Desfazer a última importação"):
        st.markdown(f"Desfaz a importação com posição em **{ultima['data_posicao']:%d/%m/%Y}**, gravada por "
                    f"**{md(ultima['enviado_por'])}**. Ela deixa de contar em todos os painéis (fica registrada "
                    "como desfeita no banco).")
        confirma = st.checkbox("Confirmo que quero desfazer", key="confirma_desfazer")
        quem = st.session_state.get("nome_usuario", "").strip()
        if st.button("Desfazer última importação", disabled=not (confirma and quem),
                     help=None if quem else "Preencha seu nome na área de importação."):
            banco_app.desfazer_ultima(quem)
            st.session_state["versao_banco"] = st.session_state.get("versao_banco", 0) + 1
            st.session_state["aviso_gravacao"] = f"↩️ Última importação desfeita por {quem}."
            st.rerun()

# ---------------------------------------------------------------------------
# Qualidade dos dados
# ---------------------------------------------------------------------------
with aba_qual:
    st.caption("O app aceita a planilha como está, mas aponta o que impede um indicador confiável. "
               "Aba e linha indicam onde corrigir no Excel.")
    q1, q2 = st.columns(2)
    q1.metric("Ações com alguma pendência", f"{qualidade.pct_pendencias(df):.0%}")
    q2.metric("Avisos de estrutura (última importação)", len(avisos_ultima))
    if avisos_ultima:
        with st.expander("Avisos de estrutura da planilha", expanded=True):
            st.markdown("\n".join(f"- {md(a)}" for a in avisos_ultima))
    for c in qualidade.checar(df):
        if c["qtd"] == 0:
            continue
        with st.expander(f"{c['checagem']} — {c['qtd']} ação(ões)"):
            st.caption(c["dica"])
            tabela_acoes(c["acoes"], colunas=("acao", "frente_entrega", "responsavel", "status", "data", "aba", "linha"))
    st.info("**Sugestões para a próxima versão da planilha:** separar *Data prevista* e *Data de conclusão*; "
            "incluir o status *Impedido*; um responsável principal por ação; data de início "
            "(permite comparar avanço esperado × real).")

# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------
with aba_export:
    filtro_txt = []
    if frentes_sel:
        filtro_txt.append("frentes: " + ", ".join(frentes_sel))
    if pessoas_sel:
        filtro_txt.append("responsáveis: " + ", ".join(pessoas_sel))
    st.markdown(f"**Área:** {md(nome_area)}  ·  posição em {hoje:%d/%m/%Y}  ·  "
                f"{'filtros: ' + '; '.join(filtro_txt) if filtro_txt else 'sem filtros'}")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**📑 Relatório executivo (PowerPoint)**")
        st.caption("Capa, painel geral, pontos de atenção, um slide por frente e a pauta da semana.")
        st.download_button("Baixar PowerPoint", data=export_pptx.gerar_relatorio(df, nome_area, hoje),
                           file_name=f"gestao_demandas_{hoje:%Y%m%d}.pptx",
                           mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    with e2:
        st.markdown("**🧮 Base consolidada (Excel)**")
        st.caption("Uma ação por linha com sinal e dias de atraso, resumo das entregas e pendências de dado.")
        st.download_button("Baixar Excel", data=export_excel.gerar_base(df, hoje),
                           file_name=f"gestao_demandas_base_{hoje:%Y%m%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
