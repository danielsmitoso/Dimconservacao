"""DimConservacao - dimensionamento e analise de contratos de conservacao
rodoviaria (Motiva).

Rodar localmente:
    streamlit run app.py

Consulte o README.md para instrucoes completas (instalacao, uso, publicacao).

Principio de interface: tudo que aparece na tela (numeros E textos) e
recalculado a cada alteracao -- nenhum texto e "congelado" no momento em que
foi gerado. Os arquivos para download (PPTX e Excel) tambem sao montados no
clique, com o estado atual.
"""
import importlib
import io
import re
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from modules import dimensionamento as dim
from modules import erros
from modules import export_excel
from modules import export_pptx
from modules import inventario as inv
from modules import mecanizacao
from modules import parametros_padrao as pp
from modules import quasar

# O Streamlit mantém os módulos em memória entre execuções: se o código for
# atualizado com o app aberto, uma versão antiga continua rodando (erros do tipo
# "takes 2 arguments but 3 were given"). Recarregar aqui, na ordem das
# dependências, garante que a tela sempre use o código mais recente do disco.
for _m in (pp, quasar, inv, dim, mecanizacao, export_excel, export_pptx, erros):
    importlib.reload(_m)

st.set_page_config(page_title="DimConservação", page_icon="🌱", layout="wide")

LOGO_ROXA = Path(__file__).parent / "assets" / "logo_motiva_roxa.png"
if LOGO_ROXA.exists():
    st.logo(str(LOGO_ROXA))

# Identidade visual Motiva (roxo) -- aplicada de leve sobre os componentes padrão do Streamlit.
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


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------
def avisar_meses(meses_a, meses_b):
    """Alerta quando os dois períodos sazonais não fecham 12 meses (exceto o
    caso 12/12, usado por demanda distribuída no ano inteiro, ex: NC)."""
    total = int(meses_a) + int(meses_b)
    if total != 12 and not (int(meses_a) == 12 and int(meses_b) == 12):
        st.warning(f"Os dois períodos somam {total} meses — o esperado é 12 (ano completo). Confira os meses informados.")


@st.cache_data(show_spinner="Lendo o export Quasar...")
def ler_quasar(conteudo: bytes, versao: str = quasar.VERSAO) -> pd.DataFrame:
    return quasar.carregar_quasar(io.BytesIO(conteudo))


@st.cache_data(show_spinner=False)
def agregar_quasar(df_poligonos: pd.DataFrame, tamanho_km: float, extrapolar: bool, versao: str = quasar.VERSAO) -> pd.DataFrame:
    return quasar.agregar_por_trecho(df_poligonos, tamanho_km, extrapolar)


@st.cache_data(show_spinner=False)
def auditar_quasar(df_poligonos: pd.DataFrame, versao: str = quasar.VERSAO) -> dict:
    return quasar.auditar_quasar(df_poligonos)


def registrar(grupo, nome, unidade_qtd, unidade_resultado, quantidade, origem, produtividade, cc, mc, cs, ms, fonte):
    """Guarda os parâmetros de cada atividade calculada -- alimenta a memória
    de cálculo em Excel (refeita a cada rerun, portanto sempre atual)."""
    memoria_atividades.append({
        "grupo": grupo, "nome": nome, "unidade_qtd": unidade_qtd, "unidade_resultado": unidade_resultado,
        "quantidade": float(quantidade), "origem_quantidade": origem, "produtividade": float(produtividade),
        "ciclos_chuva": cc, "meses_chuva": mc, "ciclos_seca": cs, "meses_seca": ms, "fonte": fonte,
    })


def colunas_trecho(df: pd.DataFrame) -> pd.DataFrame:
    return df[[c for c in ("trecho", "rodovia", "km_inicial", "km_final") if c in df.columns]].copy()


def controles_divisao(chave: str, df_inv_: pd.DataFrame):
    """Parâmetros da proposta de divisão (compartilhados pela manual e pela mecanizada)."""
    c1, c2 = st.columns(2)
    ocup_max = c1.number_input(
        "Ocupação máxima por unidade (%)", min_value=100, max_value=130, value=100, step=1, key=f"ocup_{chave}",
        help="100% = a unidade nunca passa da capacidade do ciclo. Valores maiores (ex: 105%) aceitam pequena "
             "sobrecarga (hora extra/ajuste de ciclo) e podem eliminar uma unidade de sobra.",
    )
    tem_rodovias = "rodovia" in df_inv_.columns and df_inv_["rodovia"].nunique() > 1
    multi = True
    if tem_rodovias:
        multi = c2.checkbox(
            "Permitir que uma unidade atravesse de uma rodovia para outra", value=True, key=f"multi_{chave}",
            help="Marcado: máximo aproveitamento (o que sobra numa rodovia completa a unidade na seguinte). "
                 "Desmarcado: cada unidade fica numa rodovia só (sem deslocamento entre rodovias), com possível "
                 "perda de ocupação.",
        )
    return float(ocup_max), bool(multi)


def mostrar_divisao(df_base, coluna_qtd, produtividade_unidade, ciclos, meses, rotulo, coluna_nome, prefixo_item,
                    unidade_qtd, ocup_max, multi, extra_texto=""):
    """Calcula e exibe a divisão por trecho. `rotulo` é a palavra usada nas frases
    ("equipe", "unidade"). Retorna (grupos, DataFrame para exportar)."""
    grupos = dim.propor_divisao_por_trecho(
        df_base, coluna_qtd, produtividade_unidade, ciclos, meses,
        ocupacao_maxima_pct=ocup_max, permitir_multi_rodovia=multi,
    )
    if not grupos:
        st.info("Sem quantidade suficiente para propor divisão — confira o inventário e os ciclos informados.")
        return [], None
    resumo = dim.resumir_divisao(grupos)
    linhas = [{
        coluna_nome: f"{prefixo_item} {g['unidade']}",
        "Trechos": " + ".join(g["trechos"]),
        "Rodovia(s)": ", ".join(g["rodovias"]) if g["rodovias"] else "—",
        "Extensão (km)": round(g["extensao_km"], 1),
        f"Quantidade ({unidade_qtd})": round(g["quantidade_total"], 0),
        "Ocupação do ciclo (%)": g["ocupacao_pct"],
    } for g in grupos]
    df_div = pd.DataFrame(linhas)
    st.dataframe(
        df_div, width="stretch", hide_index=True,
        column_config={
            "Ocupação do ciclo (%)": st.column_config.ProgressColumn(
                "Ocupação do ciclo", min_value=0, max_value=max(100.0, ocup_max), format="%.0f%%"),
        },
    )

    n = resumo["n"]
    cheias = sum(1 for g in grupos if g["ocupacao_pct"] >= 99.5)
    if n == 1:
        st.success(f"**1 {rotulo}**, com {grupos[0]['ocupacao_pct']:.0f}% da capacidade do ciclo ocupada.")
    elif n == cheias:
        st.success(f"**{n} {rotulo}(s)**, todas com ocupação plena do ciclo.")
    else:
        ultima = grupos[-1]["ocupacao_pct"]
        st.success(
            f"**{n} {rotulo}(s)**: {cheias} com ocupação plena do ciclo e a última com {ultima:.0f}%. "
            f"Ocupação média: {resumo['ocupacao_media']:.0f}%. A sobra total equivale a {resumo['folga_unidades']:.2f} {rotulo}."
        )
        alvo = resumo["ocupacao_para_n_menos_1"]
        if alvo is not None and ocup_max < alvo <= 115:
            st.info(
                f"💡 Se for aceitável operar até **{alvo:.0f}%** da capacidade do ciclo, o mesmo trabalho "
                f"caberia em **{n - 1} {rotulo}(s)** (ajuste 'Ocupação máxima' acima para simular)."
            )
    atravessam = [str(g["unidade"]) for g in grupos if g["multi_rodovia"]]
    if atravessam:
        st.caption(
            f"{len(atravessam)} {rotulo}(s) atravessam mais de uma rodovia ({', '.join(atravessam)}) — "
            "considere o deslocamento entre elas."
        )
    if extra_texto:
        st.caption(extra_texto)
    return grupos, df_div.copy()


# ---------------------------------------------------------------------------
# Estado (a cada execução tudo é recalculado; só as escolhas do usuário persistem)
# ---------------------------------------------------------------------------
st.session_state["resultados_atividades"] = {}
st.session_state["resumo_rocada"] = {}
memoria_atividades: list[dict] = []
memoria_divisoes: dict[str, pd.DataFrame] = {}

st.title("🌱 DimConservação")
st.caption("Dimensionamento e análise de contratos de conservação rodoviária")

col_unidade, col_status = st.columns([2, 3])
with col_unidade:
    unidade_avaliada = st.text_input(
        "🏷️ Unidade / contrato avaliado", key="unidade_avaliada",
        placeholder="Ex.: AutoBAn — Lote Norte",
        help="Aparece no cabeçalho, no relatório PowerPoint e na memória de cálculo em Excel.",
    ).strip()
with col_status:
    st.markdown("&nbsp;")
    if unidade_avaliada:
        st.markdown(f"**Avaliando:** {unidade_avaliada}  ·  {date.today():%d/%m/%Y}")
    else:
        st.caption("Informe a unidade ao lado para que ela conste nos relatórios exportados.")
nome_unidade = unidade_avaliada or "Unidade não informada"

aba_inv, aba_manual, aba_mec, aba_fs, aba_esp, aba_analise, aba_export = st.tabs(
    ["📋 Inventário", "👷 Roçada Manual", "🚜 Roçada Mecanizada", "📦 Full Service",
     "🛠️ Especialistas", "📊 Análise de Contrato", "📤 Exportar Relatório"]
)

# ---------------------------------------------------------------------------
# ABA: Inventário
# ---------------------------------------------------------------------------
auditoria = None
with aba_inv:
    st.subheader("Planilha de inventário")
    st.caption(
        "Não tem o mapeamento Quasar? Baixe a planilha modelo abaixo (colorida, com validação de dados, "
        "instruções e exemplo), preencha e envie de volta."
    )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        arquivo = st.file_uploader("Enviar planilha (.xlsx ou .csv)", type=["xlsx", "csv"])
    with col2:
        usar_exemplo = st.button("Usar inventário de exemplo (dados fictícios)")
    with col3:
        st.download_button(
            "⬇️ Baixar planilha modelo",
            data=inv.gerar_planilha_modelo(),
            file_name="DimConservacao_planilha_modelo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    gerar_quasar = False
    extrapolar = False
    with st.expander("🛰️ Importar mapeamento Quasar (área manual x mecanizada real, por satélite)"):
        st.caption(
            "Gera o inventário a partir do export Quasar (um polígono por canteiro/sentido), agrupando por "
            "rodovia + faixa de km. Preenche área verde, % manual/mecanizada e a área que cada equipamento "
            "atende. Depois de gerado, mudar o agrupamento atualiza o inventário sozinho."
        )
        arquivo_quasar = st.file_uploader("Enviar export Quasar (.xlsx)", type=["xlsx"], key="quasar_upload")
        tamanho_km = st.number_input("Agrupar em trechos de quantos km", min_value=0.5, value=5.0, step=0.5)
        if arquivo_quasar is not None:
            try:
                poligonos_previa = ler_quasar(arquivo_quasar.getvalue(), quasar.VERSAO)
                cobertura_min = min(quasar.fator_cobertura_por_rodovia(poligonos_previa).values()) * 100
            except Exception:
                cobertura_min = 100
            if cobertura_min < 99:
                extrapolar = st.checkbox(
                    f"Estimar 100% de cada km (multiplica as áreas por {100 / cobertura_min:.1f}x)",
                    value=False,
                    help="O mapeamento cobre só parte de cada km (ver Auditoria abaixo). Marque se o mapeamento "
                         "for amostral e a área verde precisar representar a rodovia inteira. Desmarcado = usa "
                         "só a área realmente mapeada.",
                )
            gerar_quasar = st.button("Gerar inventário a partir do Quasar")

    # Origem do inventário: a última ação do usuário vale; o resto se recalcula sozinho.
    if usar_exemplo:
        st.session_state["origem_inv"] = "exemplo"
    if gerar_quasar:
        st.session_state["origem_inv"] = "quasar"
    if arquivo is not None:
        id_arquivo = getattr(arquivo, "file_id", None) or f"{arquivo.name}-{arquivo.size}"
        if st.session_state.get("planilha_id") != id_arquivo:
            st.session_state["planilha_id"] = id_arquivo
            st.session_state["origem_inv"] = "planilha"
    origem = st.session_state.get("origem_inv")

    df_inv = None
    try:
        if origem == "exemplo":
            df_inv = inv.gerar_inventario_exemplo()
            st.info("Inventário de EXEMPLO (fictício) em uso — serve só para conhecer a ferramenta.")
        elif origem == "planilha" and arquivo is not None:
            df_bruto = inv.carregar_inventario(arquivo)
            faltando = inv.validar_colunas(df_bruto)
            if faltando:
                st.error(f"Faltam colunas obrigatórias na planilha: {', '.join(faltando)}")
            else:
                df_inv = inv.preparar_inventario(df_bruto)
                st.success(f"Inventário carregado da planilha: {len(df_inv)} trechos.")
        elif origem == "quasar" and arquivo_quasar is not None:
            poligonos = ler_quasar(arquivo_quasar.getvalue(), quasar.VERSAO)
            df_inv = inv.preparar_inventario(agregar_quasar(poligonos, float(tamanho_km), bool(extrapolar), quasar.VERSAO))
            auditoria = auditar_quasar(poligonos, quasar.VERSAO)
            st.success(
                f"Inventário gerado a partir do Quasar: {len(df_inv)} trechos de até {tamanho_km:g} km, "
                f"{len(poligonos):,} polígonos lidos."
                + (" Áreas estimadas para 100% de cada km." if extrapolar else "")
            )
    except Exception as e:
        _msg, _detalhe = erros.traduzir_erro(e, "ler o arquivo e montar o inventário")
        st.error(f"Não foi possível montar o inventário. {_msg}")
        with st.expander("Detalhe técnico (para suporte)"):
            st.code(_detalhe)

    if df_inv is not None:
        exibir = [c for c in df_inv.columns if not str(c).startswith("mec_m2__")]
        st.dataframe(df_inv[exibir], width="stretch", hide_index=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Trechos", len(df_inv))
        c2.metric("Extensão total (km)", f"{df_inv['extensao_km'].sum():,.1f}")
        c3.metric("Área verde total (m²)", f"{df_inv['area_verde_m2'].sum():,.0f}")
        if "pct_manual" not in df_inv.columns:
            st.caption(
                "Este inventário não tem `pct_manual`/`pct_mecanizada` — as abas Roçada Manual e "
                "Mecanizada vão considerar 100% da área verde em cada uma (cenários isolados, não "
                "somáveis). Importe o mapeamento Quasar ou use a planilha modelo para usar a divisão real."
            )
        else:
            area_manual_total = float(inv.area_por_modalidade(df_inv, "manual").sum())
            area_mec_total = float(inv.area_por_modalidade(df_inv, "mecanizada").sum())
            area_soma = area_manual_total + area_mec_total
            if area_soma > 0:
                st.markdown("**Divisão manual x mecanizada — total da concessionária**")
                cm1, cm2 = st.columns(2)
                cm1.metric("% Manual", f"{100 * area_manual_total / area_soma:.1f}%")
                cm2.metric("% Mecanizada", f"{100 * area_mec_total / area_soma:.1f}%")
    else:
        st.warning("Nenhum inventário carregado ainda.")

    # -------- Auditoria do Quasar ---------------------------------------------
    if auditoria is not None and df_inv is not None:
        st.divider()
        st.subheader("🔎 Auditoria do mapeamento Quasar")
        t = auditoria["totais"]
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Polígonos lidos", f"{t['poligonos']:,}")
        a2.metric("Rodovias", t["rodovias"])
        a3.metric("Extensão física (km)", f"{t['extensao_km']:,.1f}")
        a4.metric("Extensão no inventário (km)", f"{df_inv['extensao_km'].sum():,.1f}")
        dif = t["extensao_km"] - float(df_inv["extensao_km"].sum())
        if abs(dif) >= 0.5:
            st.caption(
                f"Diferença de {dif:,.1f} km entre a extensão física e a soma dos trechos: são lacunas "
                "(sem polígono) que caem entre duas faixas de agrupamento."
            )
        for nivel, texto in auditoria["alertas"]:
            (st.warning if nivel == "atencao" else st.info)(texto)
        st.dataframe(auditoria["por_rodovia"], width="stretch", hide_index=True)
        soma_bruta = auditoria["por_rodovia"]["Soma bruta dos polígonos (km)"].sum()
        st.caption(
            f"**Como a extensão é calculada:** por rodovia, do 1º ao último km mapeado somando o passo entre "
            f"posições — nunca somando os polígonos (canteiro lateral dos dois sentidos + canteiro central "
            f"contariam o mesmo km várias vezes: a soma bruta daria {soma_bruta:,.0f} km, "
            f"{soma_bruta / max(t['extensao_km'], 1):.1f}x a extensão real). A coluna 'Km com canteiro central' "
            "serve de conferência: costuma bater com a aba de canteiro central do próprio export."
        )

    # -------- Detalhe por equipamento -----------------------------------------
    if df_inv is not None:
        colunas_eq = quasar.equipamentos_do_inventario(df_inv)
        if colunas_eq:
            with st.expander("🚜 Área mecanizada por equipamento (indicação do Quasar)"):
                total_mec = sum(float(df_inv[c].sum()) for c in colunas_eq.values())
                linhas_eq = [{
                    "Equipamento": nome, "Área (m²)": round(float(df_inv[c].sum()), 0),
                    "% da área mecanizada": round(100 * float(df_inv[c].sum()) / total_mec, 1) if total_mec else 0,
                    "Trechos onde atua": int((df_inv[c] > 0).sum()),
                } for nome, c in colunas_eq.items()]
                st.dataframe(pd.DataFrame(linhas_eq).sort_values("Área (m²)", ascending=False), width="stretch", hide_index=True)
                st.caption("Polígonos com mais de um equipamento indicado dividem a área igualmente entre eles.")

# ---------------------------------------------------------------------------
# ABA: Roçada Manual
# ---------------------------------------------------------------------------
with aba_manual:
    st.subheader("Dimensionamento — Roçada Manual")
    if df_inv is None:
        st.warning("Carregue o inventário na aba anterior primeiro.")
    else:
        area_manual_trecho = inv.area_por_modalidade(df_inv, "manual")
        area_total = float(area_manual_trecho.sum())
        if "pct_manual" in df_inv.columns:
            st.metric("Área verde atendida por roçada manual (m²)", f"{area_total:,.0f}")
        else:
            st.metric("Área verde total do contrato (m²)", f"{area_total:,.0f}")

        prod_metas = pp.ROCADA_MANUAL["produtividade_dia_metas_m2"]
        opcao_metas = f"Metas de performance ({prod_metas:,.0f} m²/dia)"
        modalidade = st.radio("Modalidade contratual", [opcao_metas, "Personalizado"], horizontal=True)
        if modalidade == opcao_metas:
            produtividade = prod_metas
        else:
            produtividade = st.number_input(
                "Produtividade (m²/dia por colaborador)", min_value=1,
                value=pp.ROCADA_MANUAL["produtividade_dia_padrao_m2"],
            )
        st.caption(f"Produtividade usada: {produtividade:,.0f} m²/dia por roçador. Fonte do parâmetro padrão: {pp.ROCADA_MANUAL['fonte']}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Cenário chuva**")
            ciclos_chuva = st.number_input("Ciclos/ano (chuva)", min_value=1, value=pp.CICLOS_PADRAO["rocada"]["ciclos_chuva"], key="man_cc")
            meses_chuva = st.number_input("Meses do período de chuva", min_value=1, max_value=12, value=pp.CICLOS_PADRAO["rocada"]["meses_chuva"], key="man_mc")
        with c2:
            st.markdown("**Cenário seca**")
            ciclos_seca = st.number_input("Ciclos/ano (seca)", min_value=1, value=pp.CICLOS_PADRAO["rocada"]["ciclos_seca"], key="man_cs")
            meses_seca = st.number_input("Meses do período de seca", min_value=1, max_value=12, value=pp.CICLOS_PADRAO["rocada"]["meses_seca"], key="man_ms")

        avisar_meses(meses_chuva, meses_seca)
        resultado = dim.dimensionar_chuva_seca(area_total, produtividade, ciclos_chuva, meses_chuva, ciclos_seca, meses_seca)
        pico_m = resultado["pico"]

        c1, c2, c3 = st.columns(3)
        c1.metric("Colaboradores — Chuva", resultado["chuva"].equipes_arredondadas)
        c2.metric("Colaboradores — Seca", resultado["seca"].equipes_arredondadas)
        c3.metric("Pico (dimensionamento final)", pico_m.equipes_arredondadas, pico_m.cenario)

        st.session_state["resumo_rocada"]["Roçada Manual"] = {
            "equipes_arredondadas": pico_m.equipes_arredondadas, "cenario": pico_m.cenario, "unidade": "roçador(es)",
        }
        registrar("Roçada", "Roçada Manual", "m²", "roçador(es)", area_total,
                  "Inventário: área verde × % manual" if "pct_manual" in df_inv.columns else "Inventário: área verde total",
                  produtividade, ciclos_chuva, meses_chuva, ciclos_seca, meses_seca, pp.ROCADA_MANUAL["fonte"])

        df_trecho = colunas_trecho(df_inv)
        df_trecho["area_manual_m2"] = area_manual_trecho
        df_trecho["colaboradores_estimados"] = df_trecho["area_manual_m2"].apply(
            lambda a: dim.calcular_equipes(a, produtividade, pico_m.ciclos_periodo, pico_m.meses_periodo).equipes_arredondadas
        )

        with st.expander("Ver por trecho (colaboradores)"):
            st.dataframe(df_trecho, width="stretch", hide_index=True)

        st.markdown("### 👥 Proposta de divisão de equipes por trecho")
        cc1, cc2 = st.columns(2)
        total_equipe = cc1.number_input(
            "Total de colaboradores por equipe", min_value=1,
            value=pp.COMPOSICAO_EQUIPE_ROCADA_MANUAL["total_colaboradores"], key="comp_total_equipe",
        )
        rocadores_ativos = cc2.number_input(
            "Roçadores ativos por equipe (fazem roçada)", min_value=1, max_value=int(total_equipe),
            value=min(pp.COMPOSICAO_EQUIPE_ROCADA_MANUAL["rocadores_ativos"], int(total_equipe)), key="comp_rocadores_ativos",
        )
        st.caption(
            f"Cada equipe tem {int(total_equipe)} colaboradores, dos quais {int(rocadores_ativos)} roçam e "
            f"{int(total_equipe - rocadores_ativos)} fazem motorista/apoio. Fonte: {pp.COMPOSICAO_EQUIPE_ROCADA_MANUAL['fonte']}"
        )
        ocup_max_m, multi_m = controles_divisao("manual", df_inv)
        cap_equipe = dim.capacidade_por_ciclo(rocadores_ativos * produtividade, pico_m.ciclos_periodo, pico_m.meses_periodo)
        dias_ciclo_m = pico_m.meses_periodo * dim.DIAS_UTEIS_MES_PADRAO / pico_m.ciclos_periodo
        grupos_m, df_div_m = mostrar_divisao(
            df_trecho, "area_manual_m2", rocadores_ativos * produtividade,
            pico_m.ciclos_periodo, pico_m.meses_periodo, "equipe", "Equipe", "Equipe", "m²", ocup_max_m, multi_m,
            extra_texto=(
                f"Cenário de pico ({pico_m.cenario}): cada equipe roça {cap_equipe:,.0f} m² por ciclo "
                f"({int(rocadores_ativos)} roçadores × {produtividade:,.0f} m²/dia × {dias_ciclo_m:.1f} dias por ciclo). "
                "As equipes são preenchidas até a capacidade, na ordem dos km; um trecho é cortado no km em que a "
                "capacidade acaba — assim só a última equipe pode ter folga."
            ),
        )
        if df_div_m is not None:
            memoria_divisoes["Divisão Roçada Manual"] = df_div_m

# ---------------------------------------------------------------------------
# ABA: Roçada Mecanizada
# ---------------------------------------------------------------------------
with aba_mec:
    st.subheader("Dimensionamento — Roçada Mecanizada")
    if df_inv is None:
        st.warning("Carregue o inventário na aba Inventário primeiro.")
    else:
        area_mecanizada_trecho = inv.area_por_modalidade(df_inv, "mecanizada")
        area_total_mec = float(area_mecanizada_trecho.sum())
        if "pct_mecanizada" in df_inv.columns:
            st.metric("Área verde atendida por roçada mecanizada (m²)", f"{area_total_mec:,.0f}")
        else:
            st.metric("Área verde total do contrato (m²)", f"{area_total_mec:,.0f}")

        equip_padrao = None
        if not quasar.equipamentos_do_inventario(df_inv):
            st.warning(
                "O inventário não indica qual equipamento atende cada trecho (o export Quasar traz isso; na "
                "planilha modelo use a coluna `equipamento_predominante`). Enquanto isso, toda a área mecanizada "
                "é atribuída a um único equipamento — escolha qual:"
            )
            lista_eq = list(pp.ROCADA_MECANIZADA)
            equip_padrao = st.selectbox(
                "Equipamento para toda a área mecanizada", lista_eq, index=lista_eq.index(pp.EQUIPAMENTO_PADRAO_SEM_INDICACAO)
            )
        areas_eq, indicado = mecanizacao.areas_por_equipamento(df_inv, equip_padrao)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Cenário chuva**")
            ciclos_chuva_m = st.number_input("Ciclos/ano (chuva)", min_value=1, value=pp.CICLOS_PADRAO["rocada"]["ciclos_chuva"], key="mec_cc")
            meses_chuva_m = st.number_input("Meses do período de chuva", min_value=1, max_value=12, value=pp.CICLOS_PADRAO["rocada"]["meses_chuva"], key="mec_mc")
        with c2:
            st.markdown("**Cenário seca**")
            ciclos_seca_m = st.number_input("Ciclos/ano (seca)", min_value=1, value=pp.CICLOS_PADRAO["rocada"]["ciclos_seca"], key="mec_cs")
            meses_seca_m = st.number_input("Meses do período de seca", min_value=1, max_value=12, value=pp.CICLOS_PADRAO["rocada"]["meses_seca"], key="mec_ms")
        avisar_meses(meses_chuva_m, meses_seca_m)

        if areas_eq.empty:
            st.info("Não há área mecanizada no inventário — nada a dimensionar nesta aba.")
        else:
            # ---- Frota necessária (aditiva) ----------------------------------
            st.markdown("### Frota necessária por equipamento")
            st.caption(
                "Cada equipamento atende a área que a análise indica para ele (não é 'se um só fizesse tudo'), "
                "então os números somam. Ajuste produtividade e frota disponível conforme a realidade."
            )
            cab = st.columns([3, 2, 2, 2])
            for col, t_ in zip(cab, ["Equipamento", "Produtividade (m²/dia)", "Qtd. disponível na frota", "Área atendida (m²)"]):
                col.markdown(f"**{t_}**")
            equipamentos = {}
            for nome_eq in areas_eq.columns:
                l1, l2, l3, l4 = st.columns([3, 2, 2, 2])
                l1.markdown(f"**{nome_eq}**")
                prod = l2.number_input(f"Produtividade {nome_eq}", min_value=1, value=mecanizacao.produtividade_padrao(nome_eq),
                                       key=f"prod_{nome_eq}", label_visibility="collapsed")
                qtd_disp = l3.number_input(f"Frota {nome_eq}", min_value=0, value=0, key=f"qtd_{nome_eq}", label_visibility="collapsed")
                area_eq = float(areas_eq[nome_eq].sum())
                l4.markdown(f"{area_eq:,.0f}")
                equipamentos[nome_eq] = {"produtividade": prod, "qtd_disponivel": qtd_disp, "area": area_eq}
            st.caption("Produtividades marcadas como 'estimativa' em parametros_padrao.py — validar com dado de campo real antes de usar em contrato real.")

            linhas_frota, resultados_eq = [], {}
            for nome_eq, d in equipamentos.items():
                res = dim.dimensionar_chuva_seca(d["area"], d["produtividade"], ciclos_chuva_m, meses_chuva_m, ciclos_seca_m, meses_seca_m)
                resultados_eq[nome_eq] = res
                pico_eq = res["pico"].equipes_arredondadas
                if d["qtd_disponivel"] == 0:
                    situacao = "—"
                elif d["qtd_disponivel"] >= pico_eq:
                    situacao = f"✅ Sobra {d['qtd_disponivel'] - pico_eq}"
                else:
                    situacao = f"⚠️ Falta {pico_eq - d['qtd_disponivel']}"
                linhas_frota.append({
                    "Equipamento": nome_eq,
                    "Área atendida (m²)": round(d["area"], 0),
                    "% da área mecanizada": round(100 * d["area"] / area_total_mec, 1) if area_total_mec else 0,
                    "Produtividade (m²/dia)": d["produtividade"],
                    "Necessário — Chuva": res["chuva"].equipes_arredondadas,
                    "Necessário — Seca": res["seca"].equipes_arredondadas,
                    "Necessário — Pico": pico_eq,
                    "Utilização das unidades (%)": round(100 * res["pico"].equipes_exatas / pico_eq, 0) if pico_eq else 0,
                    "Frota disponível": d["qtd_disponivel"],
                    "Situação da frota": situacao,
                })
                st.session_state["resumo_rocada"][f"Roçada Mecanizada — {nome_eq}"] = {
                    "equipes_arredondadas": pico_eq, "cenario": res["pico"].cenario, "unidade": "unidade(s)",
                }
                registrar("Roçada", f"Roçada Mecanizada — {nome_eq}", "m²", "unidade(s)", d["area"],
                          "Inventário: área mecanizada atendida por este equipamento" if indicado
                          else "Inventário: toda a área mecanizada (equipamento único escolhido)",
                          d["produtividade"], ciclos_chuva_m, meses_chuva_m, ciclos_seca_m, meses_seca_m,
                          pp.ROCADA_MECANIZADA.get(nome_eq, {}).get("fonte", "estimativa") + " (produtividade a validar)")
            df_frota = pd.DataFrame(linhas_frota)
            st.dataframe(df_frota, width="stretch", hide_index=True)
            total_pico = int(df_frota["Necessário — Pico"].sum())
            detalhe_frota = ", ".join(f"{r['Necessário — Pico']} {r['Equipamento']}" for r in linhas_frota if r["Necessário — Pico"])
            st.success(f"Frota mecanizada necessária no cenário de pico: **{total_pico} equipamento(s)** ({detalhe_frota}).")
            subutilizados = [
                f"**{r['Equipamento']}** ({r['Área atendida (m²)']:,.0f} m², utilização de {r['Utilização das unidades (%)']:.0f}%)"
                for r in linhas_frota if r["Necessário — Pico"] and r["Utilização das unidades (%)"] < 40
            ]
            if subutilizados:
                st.warning(
                    "Equipamentos com pouca área para o que uma unidade rende: " + "; ".join(subutilizados) +
                    ". Vale avaliar atender essa área com outro equipamento da frota (ver 'Equipamento recomendado "
                    "por trecho') em vez de manter uma unidade dedicada."
                )
            memoria_divisoes["Frota Mecanizada"] = df_frota

            # ---- Recomendação por trecho --------------------------------------
            st.markdown("### 🎯 Equipamento recomendado por trecho")
            if indicado:
                st.caption(
                    "Para cada trecho, o equipamento que atende a maior parte da área mecanizada segundo a "
                    "indicação do inventário — no Quasar, considera largura, inclinação, obstáculos e bloqueios de cada polígono. "
                    "Trechos 'mistos' precisam de mais de um equipamento — veja o mix."
                )
            else:
                st.caption("Sem indicação por trecho no inventário: todos os trechos aparecem com o equipamento escolhido acima.")
            df_reco = mecanizacao.recomendacao_por_trecho(df_inv, areas_eq)
            filtro_eq = st.multiselect("Filtrar por equipamento recomendado", list(areas_eq.columns), key="filtro_reco")
            df_reco_v = df_reco[df_reco["Equipamento recomendado"].isin(filtro_eq)] if filtro_eq else df_reco
            if df_reco_v["Rodovia"].eq("").all():
                df_reco_v = df_reco_v.drop(columns=["Rodovia"])
            st.dataframe(
                df_reco_v, width="stretch", hide_index=True,
                column_config={"% da área": st.column_config.ProgressColumn("% da área", min_value=0, max_value=100, format="%.0f%%")},
            )
            misto = int((df_reco["% da área"] < 60).sum())
            if misto:
                st.caption(f"{misto} de {len(df_reco)} trechos são mistos (nenhum equipamento cobre 60% da área).")
            memoria_divisoes["Equipamento por trecho"] = df_reco

            # ---- Divisão por equipamento ---------------------------------------
            st.markdown("### 🚜 Proposta de divisão de trechos por equipamento")
            st.caption(
                "Para cada equipamento, qual sequência de trechos cada unidade atende, preenchendo o ciclo de "
                "uma unidade antes de abrir a seguinte."
            )
            ocup_max_e, multi_e = controles_divisao("mec", df_inv)
            df_div_todas = []
            for nome_eq, d in equipamentos.items():
                pico_eq = resultados_eq[nome_eq]["pico"]
                df_base_eq = colunas_trecho(df_inv)
                df_base_eq["qtd"] = areas_eq[nome_eq]
                with st.expander(f"{nome_eq} — {pico_eq.equipes_arredondadas} unidade(s) no cenário {pico_eq.cenario or '-'}"):
                    grupos_e, df_e = mostrar_divisao(
                        df_base_eq, "qtd", d["produtividade"], pico_eq.ciclos_periodo, pico_eq.meses_periodo,
                        "unidade", "Unidade", nome_eq, "m²", ocup_max_e, multi_e,
                    )
                    if df_e is not None:
                        df_e.insert(0, "Equipamento", nome_eq)
                        df_div_todas.append(df_e)
            if df_div_todas:
                memoria_divisoes["Divisão Mecanizada"] = pd.concat(df_div_todas, ignore_index=True)

# ---------------------------------------------------------------------------
# ABA: Full Service
# ---------------------------------------------------------------------------
with aba_fs:
    st.subheader("Dimensionamento — Atividades Full Service")
    if df_inv is None:
        st.warning("Carregue o inventário na aba Inventário primeiro.")
    else:
        st.caption("Baseado no escopo do FS 4.0 (RioSP): roçada + aceiro + drenagem + capina + refilamento + calçada + placas + remoção de lixo.")
        linhas_relatorio = []
        for nome_ativ, cfg in pp.FULL_SERVICE_ATIVIDADES.items():
            coluna = pp.COLUNA_INVENTARIO_POR_ATIVIDADE.get(nome_ativ)
            tem_coluna = bool(coluna and coluna in df_inv.columns)
            quantidade_padrao = float(df_inv[coluna].sum()) if tem_coluna else 0.0

            with st.expander(f"{nome_ativ}  —  {quantidade_padrao:,.1f} {cfg['unidade']} no inventário"):
                quantidade = st.number_input(
                    f"Quantidade ({cfg['unidade']})" + ("" if tem_coluna else " — não há coluna no inventário, informe manualmente"),
                    min_value=0.0, value=quantidade_padrao, key=f"fs_qtd_{nome_ativ}",
                )
                col1, col2, col3 = st.columns(3)
                meta = col1.number_input("Meta/dia por equipe", min_value=0.01, value=float(cfg["meta_dia"]), key=f"fs_meta_{nome_ativ}")
                cchuva = col2.number_input("Ciclos/ano (chuva)", min_value=1, value=cfg["ciclos_chuva"], key=f"fs_cc_{nome_ativ}")
                mchuva = col2.number_input("Meses (chuva)", min_value=1, max_value=12, value=cfg["meses_chuva"], key=f"fs_mc_{nome_ativ}")
                cseca = col3.number_input("Ciclos/ano (seca)", min_value=1, value=cfg["ciclos_seca"], key=f"fs_csc_{nome_ativ}")
                mseca = col3.number_input("Meses (seca)", min_value=1, max_value=12, value=cfg["meses_seca"], key=f"fs_ms_{nome_ativ}")
                st.caption(f"Fonte: {cfg['fonte']}")

                avisar_meses(mchuva, mseca)
                resultado = dim.dimensionar_chuva_seca(quantidade, meta, cchuva, mchuva, cseca, mseca)
                c1, c2, c3 = st.columns(3)
                c1.metric("Equipes — Chuva", resultado["chuva"].equipes_arredondadas)
                c2.metric("Equipes — Seca", resultado["seca"].equipes_arredondadas)
                c3.metric("Pico", resultado["pico"].equipes_arredondadas)

                linhas_relatorio.append([
                    nome_ativ, cfg["unidade"], f"{quantidade:,.1f}",
                    resultado["chuva"].equipes_arredondadas, resultado["seca"].equipes_arredondadas,
                    resultado["pico"].equipes_arredondadas,
                ])
                registrar("Full Service", nome_ativ, cfg["unidade"], "equipe(s)", quantidade,
                          f"Inventário: coluna {coluna}" if tem_coluna and quantidade == quantidade_padrao else "Informada manualmente",
                          meta, cchuva, mchuva, cseca, mseca, cfg["fonte"])
        st.session_state["resultados_atividades"]["Full Service"] = linhas_relatorio

# ---------------------------------------------------------------------------
# ABA: Especialistas
# ---------------------------------------------------------------------------
with aba_esp:
    st.subheader("Dimensionamento — Equipes Especialistas")
    st.caption("EPS/barreira, defensa metálica, NC, varrição e poda — geralmente fora do pacote Full Service.")
    linhas_relatorio = []
    for nome_ativ, cfg in pp.ESPECIALISTAS_ATIVIDADES.items():
        coluna = pp.COLUNA_INVENTARIO_POR_ATIVIDADE.get(nome_ativ)
        if coluna and df_inv is not None and coluna in df_inv.columns:
            quantidade_padrao = float(df_inv[coluna].sum())
        else:
            quantidade_padrao = 0.0

        with st.expander(f"{nome_ativ}"):
            quantidade = st.number_input(
                f"Quantidade ({cfg['unidade']}) — {'preenchido do inventário, ajuste se necessário' if coluna else 'não há coluna no inventário, informe manualmente'}",
                min_value=0.0, value=quantidade_padrao, key=f"esp_qtd_{nome_ativ}",
            )

            modo_reativo = False
            if nome_ativ in pp.ATIVIDADES_COM_MODO_REATIVO:
                modo = st.radio(
                    "Modo de cálculo", ["Preventivo (varredura cíclica)", "Reativo (taxa de acionamentos)"],
                    horizontal=True, key=f"esp_modo_{nome_ativ}",
                    help="Preventivo: inspeção/varredura completa por ciclo (como hoje). Reativo: dano é majoritariamente "
                         "causado por acidente/sinistro, não por varredura -- dimensiona pela taxa histórica de "
                         "acionamentos por km/ano, no mesmo padrão já usado pela NC.",
                )
                modo_reativo = modo.startswith("Reativo")

            if modo_reativo:
                extensao_km_ativ = quantidade / 1000
                c1, c2 = st.columns(2)
                taxa = c1.number_input(
                    "Taxa de acionamentos por km/ano", min_value=0.0, value=1.0, step=0.1, key=f"esp_taxa_{nome_ativ}",
                    help="Histórico de acionamentos (sinistro/dano) da unidade, por km de extensão, por ano.",
                )
                meta_reativo = c2.number_input(
                    "Acionamentos atendidos/dia por equipe", min_value=0.01,
                    value=float(cfg.get("meta_dia_reativo", 1.0)), key=f"esp_metar_{nome_ativ}",
                )
                volume_anual = taxa * extensao_km_ativ
                st.caption(
                    f"Extensão: {extensao_km_ativ:,.1f} km · Volume anual estimado: {volume_anual:,.1f} acionamento(s) "
                    f"(taxa × extensão). Fonte da meta/dia: {cfg.get('fonte_reativo', 'estimativa (a validar)')}"
                )
                resultado = dim.dimensionar_chuva_seca(volume_anual, meta_reativo, 1, 12, 1, 12)
                st.metric("Equipes necessárias (modo reativo)", resultado["pico"].equipes_arredondadas)

                linhas_relatorio.append([
                    f"{nome_ativ} (reativo)", "acionamento(s)/ano", f"{volume_anual:,.1f}",
                    resultado["chuva"].equipes_arredondadas, resultado["seca"].equipes_arredondadas,
                    resultado["pico"].equipes_arredondadas,
                ])
                registrar("Especialistas", f"{nome_ativ} (reativo)", "acionamento(s)/ano", "equipe(s)", volume_anual,
                          f"Taxa de {taxa:g} acionamento(s)/km/ano × {extensao_km_ativ:,.1f} km do inventário",
                          meta_reativo, 1, 12, 1, 12, cfg.get("fonte_reativo", "estimativa (a validar)"))
            else:
                col1, col2, col3 = st.columns(3)
                meta = col1.number_input("Meta/dia por equipe", min_value=0.01, value=float(cfg["meta_dia"]), key=f"esp_meta_{nome_ativ}")
                cchuva = col2.number_input("Ciclos/ano (cenário 1)", min_value=1, value=cfg["ciclos_chuva"], key=f"esp_cc_{nome_ativ}")
                mchuva = col2.number_input("Meses (cenário 1)", min_value=1, max_value=12, value=cfg["meses_chuva"], key=f"esp_mc_{nome_ativ}")
                cseca = col3.number_input("Ciclos/ano (cenário 2)", min_value=1, value=cfg["ciclos_seca"], key=f"esp_csc_{nome_ativ}")
                mseca = col3.number_input("Meses (cenário 2)", min_value=1, max_value=12, value=cfg["meses_seca"], key=f"esp_ms_{nome_ativ}")
                st.caption(f"Fonte: {cfg['fonte']}")

                avisar_meses(mchuva, mseca)
                resultado = dim.dimensionar_chuva_seca(quantidade, meta, cchuva, mchuva, cseca, mseca)
                c1, c2, c3 = st.columns(3)
                c1.metric("Equipes — Cenário 1", resultado["chuva"].equipes_arredondadas)
                c2.metric("Equipes — Cenário 2", resultado["seca"].equipes_arredondadas)
                c3.metric("Pico", resultado["pico"].equipes_arredondadas)

                linhas_relatorio.append([
                    nome_ativ, cfg["unidade"], f"{quantidade:,.1f}",
                    resultado["chuva"].equipes_arredondadas, resultado["seca"].equipes_arredondadas,
                    resultado["pico"].equipes_arredondadas,
                ])
                veio_do_inventario = bool(coluna) and df_inv is not None and quantidade == quantidade_padrao
                registrar("Especialistas", nome_ativ, cfg["unidade"], "equipe(s)", quantidade,
                          f"Inventário: coluna {coluna}" if veio_do_inventario else "Informada manualmente",
                          meta, cchuva, mchuva, cseca, mseca, cfg["fonte"])
    st.session_state["resultados_atividades"]["Especialistas"] = linhas_relatorio

# ---------------------------------------------------------------------------
# ABA: Análise de Contrato
# ---------------------------------------------------------------------------
with aba_analise:
    titulo_analise = "Análise de Contrato — Dimensionado × Contratado"
    st.subheader(f"{titulo_analise} ({unidade_avaliada})" if unidade_avaliada else titulo_analise)
    st.caption("Informe quantas equipes/unidades o contrato atual prevê para cada atividade, para comparar com o dimensionamento.")

    todas_atividades = []
    for nome_r, r in st.session_state["resumo_rocada"].items():
        todas_atividades.append((nome_r, r["equipes_arredondadas"], r.get("unidade", "equipe(s)")))
    for grupo, linhas in st.session_state["resultados_atividades"].items():
        for linha in linhas:
            todas_atividades.append((linha[0], linha[-1], "equipe(s)"))  # (nome, equipes_pico, unidade)

    linhas_analise = []
    if not todas_atividades:
        st.warning("Calcule o dimensionamento nas abas anteriores primeiro.")
    else:
        for nome_ativ, dimensionado, unidade in todas_atividades:
            col1, col2, col3 = st.columns([3, 1, 2])
            col1.markdown(f"**{nome_ativ}**")
            col1.caption(f"Dimensionado: {dimensionado} {unidade}")
            contratado = col2.number_input("Contratado", min_value=0, value=int(dimensionado), key=f"contr_{nome_ativ}")
            delta = contratado - dimensionado
            pct_desvio = 100 * abs(delta) / dimensionado if dimensionado else 0
            desvio = f" ({100 * delta / dimensionado:+.0f}%)" if dimensionado else ""
            if delta < 0:
                status = f"⚠️ Déficit de {abs(delta)} {unidade}{desvio}"
                # Faixa de severidade (limiares 5%/15% -- aprovados pelo usuário em
                # 2026-09-22 como ponto de partida, a recalibrar com feedback de uso).
                if pct_desvio <= 5:
                    col3.success(status)
                elif pct_desvio <= 15:
                    col3.warning(status)
                else:
                    col3.error(status)
            elif delta > 0:
                status = f"ℹ️ Excedente de {delta} {unidade}{desvio}"
                col3.info(status)
            else:
                status = "✅ Conforme"
                col3.success(status)
            linhas_analise.append([nome_ativ, dimensionado, contratado, status])
    st.session_state["analise_contrato"] = linhas_analise

# ---------------------------------------------------------------------------
# ABA: Exportar Relatório
# ---------------------------------------------------------------------------
premissas = [
    ("Fórmula base", "Necessário = arredondar para cima( Quantidade ÷ (Dias por ciclo × Produtividade diária) ), com "
                     "Dias por ciclo = (Meses do período × dias úteis por mês) ÷ Ciclos no período. Calculado para chuva e seca; "
                     "o dimensionamento final é o PICO (o cenário que exige mais)."),
    ("Dias úteis por mês", f"{dim.DIAS_UTEIS_MES_PADRAO} dias úteis por mês em todas as atividades."),
    ("Roçada manual", f"Produtividade por roçador (colaborador individual), não por equipe. Equipe padrão: "
                      f"{pp.COMPOSICAO_EQUIPE_ROCADA_MANUAL['total_colaboradores']} colaboradores, "
                      f"{pp.COMPOSICAO_EQUIPE_ROCADA_MANUAL['rocadores_ativos']} roçando (ajustável na aba)."),
    ("Roçada mecanizada", "A área mecanizada de cada trecho é distribuída entre os equipamentos indicados pelo Quasar "
                          "(polígonos com mais de um equipamento dividem a área igualmente). Produtividades por equipamento "
                          "são estimativas a validar com dado de campo."),
    ("Divisão por trecho", "Trechos percorridos por rodovia e km; cada unidade é preenchida até a capacidade do ciclo antes "
                           "de abrir a seguinte; um trecho é cortado no km em que a capacidade acaba. Só a última unidade pode ter folga."),
    ("Extensão (Quasar)", "Extensão física = do 1º ao último km mapeado de cada rodovia (passo entre posições), sem somar "
                          "polígonos de canteiro lateral/central nem sentidos. Ver aba Auditoria Quasar."),
    ("Parâmetros estimados", "Parâmetros com fonte 'estimativa (a validar)' não têm lastro em dado de campo — não usar para "
                             "decisão de contrato sem validação técnica."),
]

with aba_export:
    st.subheader("Exportar relatório e memória de cálculo")
    if unidade_avaliada:
        st.markdown(f"**Unidade avaliada:** {unidade_avaliada}")
    else:
        st.warning("Nenhuma unidade informada — os arquivos sairão como 'Unidade não informada'. Preencha o campo no topo da página.")

    n_ativ = len(memoria_atividades)
    tem_resultado = bool(n_ativ)
    if tem_resultado:
        st.info(
            f"Os arquivos vão refletir o estado atual da tela: **{n_ativ} atividades** dimensionadas, "
            f"{len(st.session_state['analise_contrato'])} linhas na Análise de Contrato"
            + (", auditoria do Quasar incluída" if auditoria is not None else "")
            + ". Se você mudar qualquer número, basta baixar de novo — nada fica desatualizado."
        )
    else:
        st.error("Não há nada calculado ainda. Carregue o inventário e preencha as abas de dimensionamento primeiro.")

    def _bytes_pptx():
        with tempfile.TemporaryDirectory() as tmp:
            caminho = str(Path(tmp) / "DimConservacao_Relatorio.pptx")
            export_pptx.gerar_relatorio(
                caminho_saida=caminho, nome_contrato=nome_unidade,
                resumo_rocada=st.session_state["resumo_rocada"],
                resultados_atividades=st.session_state["resultados_atividades"],
                analise_contrato=st.session_state.get("analise_contrato"),
            )
            return Path(caminho).read_bytes()

    def _bytes_excel():
        return export_excel.gerar_memoria_calculo({
            "unidade": nome_unidade, "data": f"{date.today():%d/%m/%Y}", "dias_uteis_mes": dim.DIAS_UTEIS_MES_PADRAO,
            "atividades": memoria_atividades, "analise": st.session_state.get("analise_contrato"),
            "inventario": df_inv, "divisoes": memoria_divisoes, "auditoria": auditoria, "premissas": premissas,
        })

    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", nome_unidade).strip("_") or "relatorio"
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("**📑 Relatório executivo (PowerPoint)**")
        st.caption("Resumo para apresentação: roçada, atividades e comparativo com o contrato.")
        st.download_button(
            "⬇️ Baixar relatório PPTX", data=_bytes_pptx, disabled=not tem_resultado,
            file_name=f"DimConservacao_{slug}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    with b2:
        st.markdown("**🧮 Memória de cálculo (Excel)**")
        st.caption(
            "Para conferir os números: premissas em azul, cálculo passo a passo em fórmulas do Excel, inventário, "
            "análise de contrato, divisão por trecho, auditoria do Quasar e premissas."
        )
        st.download_button(
            "⬇️ Baixar memória de cálculo (Excel)", data=_bytes_excel, disabled=not tem_resultado,
            file_name=f"DimConservacao_MemoriaCalculo_{slug}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
