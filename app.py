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
import math
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
from modules import crescimento

# O Streamlit mantém os módulos em memória entre execuções: se o código for
# atualizado com o app aberto, uma versão antiga continua rodando (erros do tipo
# "takes 2 arguments but 3 were given"). Recarregar aqui, na ordem das
# dependências, garante que a tela sempre use o código mais recente do disco.
for _m in (pp, quasar, inv, dim, mecanizacao, export_excel, export_pptx, erros, crescimento):
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
def agregar_quasar(df_poligonos: pd.DataFrame, tamanho_km: float, extrapolar: bool, largura_tripla: float | None,
                   versao: str = quasar.VERSAO) -> pd.DataFrame:
    return quasar.agregar_por_trecho(df_poligonos, tamanho_km, extrapolar, largura_tripla)


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


def sincronizar_padrao(chave: str, padrao):
    """Faz um campo editável acompanhar o valor calculado enquanto o usuário
    não o editar. O Streamlit ignora `value=` depois que a chave já existe, então
    sem isso o campo fica congelado no primeiro valor calculado (ex.: 0, antes do
    inventário). Regra: se o campo ainda está igual ao último padrão calculado,
    segue o novo; se o usuário mudou, a edição dele é preservada."""
    chave_padrao = f"_padrao_{chave}"
    anterior = st.session_state.get(chave_padrao)
    if chave not in st.session_state or st.session_state[chave] == anterior:
        st.session_state[chave] = padrao
    st.session_state[chave_padrao] = padrao


def campo_ciclo(rotulo: str, chave: str, **kwargs) -> int:
    """Campo de ciclos/meses das abas de roçada. O valor vive em
    st.session_state[chave]; o widget usa uma chave com versão, renovada quando a
    aba Vegetação e Clima aplica ciclos novos. Motivo: o Streamlit ignora (e chega a
    exibir errado) um valor gravado na sessão para um widget que ainda não estava na
    tela -- o campo aparecia "1" enquanto o cálculo usava 5."""
    versao = st.session_state.get("veg_versao", 0)
    valor = st.number_input(rotulo, value=int(st.session_state[chave]), key=f"{chave}_w{versao}", **kwargs)
    st.session_state[chave] = valor
    return valor


def ciclos_do_modelo(prefixo: str) -> bool:
    """True se os ciclos/meses da aba de roçada ainda são os aplicados pela aba
    Vegetação e Clima (o usuário não os editou depois)."""
    aplicado = st.session_state.get("veg_aplicado")
    return bool(aplicado) and all(
        st.session_state.get(f"{prefixo}_{k}") == v for k, v in aplicado["valores"].items()
    )


def legenda_ciclos(prefixo: str):
    if ciclos_do_modelo(prefixo):
        st.caption(f"🌿 Ciclos e meses vindos da aba Vegetação e Clima — {st.session_state['veg_aplicado']['texto']}.")
    else:
        st.caption("Ciclos digitados aqui ou padrão de referência. Para estimá-los pelo crescimento da vegetação "
                   "(espécies, clima e solo da região), use a aba 🌿 Vegetação e Clima.")


def atividade_ciclos_por_ano(nome_ativ: str, cfg: dict, quantidade: float):
    """Atividade feita N vezes por ano numa janela (ex.: Aceiro, 1 ciclo/ano na
    seca), no formato da aba Especialistas: 2 cenários de ciclos/ano para comparar
    e um adotado no dimensionamento. Devolve (cc, mc, cs, ms, meta) no formato
    chuva/seca do resto do app: o ciclo cai no período da janela e o outro fica
    com 0 ciclos ("Ano todo" usa 12 meses nos dois). Pedido do Omar, 2026-10-16."""
    col1, col2, col3 = st.columns(3)
    meta = col1.number_input("Meta/dia por equipe", min_value=0.01, value=float(cfg["meta_dia"]), key=f"fs_meta_{nome_ativ}")
    ca1 = col2.number_input("Ciclos/ano — cenário 1", min_value=1, value=int(cfg["ciclos_ano"]), key=f"fs_ca1_{nome_ativ}")
    ca2 = col3.number_input("Ciclos/ano — cenário 2", min_value=1, value=int(cfg["ciclos_ano_alt"]), key=f"fs_ca2_{nome_ativ}")
    janelas = list(pp.JANELAS_EXECUCAO)
    janela = col1.selectbox("Executado em", janelas, index=janelas.index(cfg["janela"]), key=f"fs_jan_{nome_ativ}",
                            help="Período do ano em que a atividade é feita. Contratos Artesp: aceiro e drenagem fora "
                                 "da plataforma, 1 ciclo/ano na seca.")
    sincronizar_padrao(f"fs_mj_{nome_ativ}", pp.JANELAS_EXECUCAO[janela])
    meses = col2.number_input("Meses da janela de execução", min_value=1, max_value=12, key=f"fs_mj_{nome_ativ}")
    adotado = col3.radio("Cenário adotado no dimensionamento", ["Cenário 1", "Cenário 2"], horizontal=True,
                         key=f"fs_cen_{nome_ativ}")
    st.caption(f"Fonte: {cfg['fonte']}")
    r1 = dim.calcular_equipes(quantidade, meta, ca1, meses)
    r2 = dim.calcular_equipes(quantidade, meta, ca2, meses)
    c1, c2 = st.columns(2)
    c1.metric(f"Equipes — Cenário 1 ({ca1} ciclo(s)/ano)", r1.equipes_arredondadas,
              help=f"Exato: {r1.equipes_exatas:.2f}. Todos os ciclos do ano feitos em {meses} meses ({janela.lower()}).")
    c2.metric(f"Equipes — Cenário 2 ({ca2} ciclo(s)/ano)", r2.equipes_arredondadas,
              help=f"Exato: {r2.equipes_exatas:.2f}. Todos os ciclos do ano feitos em {meses} meses ({janela.lower()}).")
    ciclos = ca1 if adotado == "Cenário 1" else ca2
    st.caption(
        f"Dimensionamento usa o **{adotado.lower()}: {ciclos} ciclo(s)/ano em {meses} meses** ({janela.lower()}) → "
        f"{quantidade:,.1f} {cfg['unidade']} × {ciclos} ÷ ({meses} × {dim.DIAS_UTEIS_MES_PADRAO} dias úteis × {meta:g}/dia). "
        "Fora da janela, nenhuma equipe é alocada para esta atividade."
    )
    if janela == "Chuva":
        return ciclos, meses, 0, max(1, 12 - meses), meta
    if janela == "Seca":
        return 0, max(1, 12 - meses), ciclos, meses, meta
    return ciclos, meses, ciclos, meses, meta


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
# Ciclos de roçada: valor guardado na sessão (padrão de referência na 1ª vez); a aba
# Vegetação e Clima pode substituí-lo -- ver campo_ciclo().
for _pre in ("man", "mec"):
    for _suf, _campo in (("cc", "ciclos_chuva"), ("mc", "meses_chuva"), ("cs", "ciclos_seca"), ("ms", "meses_seca")):
        st.session_state.setdefault(f"{_pre}_{_suf}", pp.CICLOS_PADRAO["rocada"][_campo])
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


def mostrar_quadro_resumo(local, linhas: list, rotulos_cenario: tuple):
    """Quadro-resumo no topo das abas Full Service/Especialistas (backlog item 58).
    `local` é um st.container() criado no topo da aba e preenchido depois do laço das
    atividades, para mostrar os valores já editados sem abrir cada expansor.
    Cada linha: dict com atividade, quantidade, unidade, origem, chuva, seca, pico, fonte."""
    if not linhas:
        return
    with local:
        estimadas = [l for l in linhas if "estimativa" in l["fonte"].lower()]
        zeradas = [l for l in linhas if l["quantidade"] <= 0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Equipes no pico (soma)", sum(l["pico"] for l in linhas))
        m2.metric("Atividades com parâmetro estimado", f"{len(estimadas)} de {len(linhas)}",
                  help="Meta/dia com fonte 'estimativa (a validar)': sem lastro em dado de campo.")
        m3.metric("Atividades com quantidade zero", len(zeradas))
        st.dataframe(
            pd.DataFrame([{
                "Atividade": l["atividade"],
                "Quantidade": f"{l['quantidade']:,.1f} {l['unidade']}",
                "Origem": l["origem"] if l["quantidade"] > 0 else "Sem dado",
                f"Equipes — {rotulos_cenario[0]}": l["chuva"],
                f"Equipes — {rotulos_cenario[1]}": l["seca"],
                "Pico": l["pico"],
                "Parâmetro": "⚠️ estimativa" if "estimativa" in l["fonte"].lower() else "referência",
            } for l in linhas]),
            hide_index=True, width="stretch",
        )
        st.caption("Resumo do que está preenchido abaixo. Abra a atividade para ajustar quantidade, meta e ciclos.")


def mostrar_totais_analise(local, linhas: list, totais: dict):
    """Consolidado no topo da Análise de Contrato (backlog item 59): contagem por status
    e total dimensionado × contratado por unidade (roçador, unidade de equipamento e
    equipe não se somam entre si)."""
    with local:
        n_deficit = sum(1 for l in linhas if l[3].startswith("⚠️"))
        n_conforme = sum(1 for l in linhas if l[3].startswith("✅"))
        n_excedente = sum(1 for l in linhas if l[3].startswith("ℹ️"))
        m1, m2, m3 = st.columns(3)
        m1.metric("⚠️ Em déficit", n_deficit)
        m2.metric("✅ Conformes", n_conforme)
        m3.metric("ℹ️ Excedentes", n_excedente)
        colunas = st.columns(max(len(totais), 1))
        for col, (unidade, (dimensionado, contratado)) in zip(colunas, totais.items()):
            delta = contratado - dimensionado
            col.metric(f"Total contratado ({unidade})", contratado, delta=f"{delta:+d}" if delta else None)
            col.caption(f"Dimensionado: {dimensionado} {unidade}")
        st.caption("Totais separados por unidade: roçadores, unidades de equipamento e equipes não se somam. "
                   "Um excedente numa atividade não compensa o déficit de outra.")
        st.divider()


aba_inv, aba_veg, aba_manual, aba_mec, aba_fs, aba_esp, aba_analise, aba_export = st.tabs(
    ["📋 Inventário", "🌿 Vegetação e Clima", "👷 Roçada Manual", "🚜 Roçada Mecanizada", "📦 Full Service",
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
        rt1, rt2 = st.columns([3, 2])
        usar_regra_tripla = rt1.checkbox(
            "Regra do Trator 4,70: canteiro largo sem bloqueio também pode ser feito pelo 4,70", value=True,
            key="regra_tripla",
            help="Para polígonos indicados como Trator 1.7m, com largura acima do limite e sem bloqueio físico "
                 "(coluna 'Bloqueio Físico' = Sim, ou observação citando drenagem, EPS, barreira ou defensa), o "
                 "Trator 4.7m entra como alternativa. Polígonos de Eixo-zero, braço articulado e Spider não mudam: "
                 "eles foram indicados por restrição de acesso. Largura = 'Largura média' do Quasar ou, onde não "
                 "vem, área ÷ comprimento do polígono (é a mesma conta).",
        )
        largura_tripla = rt2.number_input("Largura mínima do canteiro (m)", min_value=1.0,
                                          value=pp.LARGURA_MINIMA_TRATOR_47_M, step=0.5, key="largura_tripla",
                                          disabled=not usar_regra_tripla)
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
    df_bruto_inv = None  # planilha como veio do arquivo: a checagem procura texto em campo numérico
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
                df_bruto_inv = df_bruto
                st.success(f"Inventário carregado da planilha: {len(df_inv)} trechos.")
        elif origem == "quasar" and arquivo_quasar is not None:
            poligonos = ler_quasar(arquivo_quasar.getvalue(), quasar.VERSAO)
            largura_regra = float(largura_tripla) if usar_regra_tripla else None
            df_inv = inv.preparar_inventario(
                agregar_quasar(poligonos, float(tamanho_km), bool(extrapolar), largura_regra, quasar.VERSAO))
            auditoria = auditar_quasar(poligonos, quasar.VERSAO)
            st.success(
                f"Inventário gerado a partir do Quasar: {len(df_inv)} trechos de até {tamanho_km:g} km, "
                f"{len(poligonos):,} polígonos lidos."
                + (" Áreas estimadas para 100% de cada km." if extrapolar else "")
            )
            if largura_regra is not None:
                _, _mask_tripla = quasar.aplicar_regra_trator_47(poligonos, largura_regra)
                st.caption(
                    f"🚜 Regra do Trator 4,70: {int(_mask_tripla.sum()):,} polígono(s) de Trator 1.7m com canteiro acima de "
                    f"{largura_regra:g} m e sem bloqueio ({poligonos.loc[_mask_tripla, 'area_mecanizada_m2'].sum():,.0f} m² "
                    "mecanizados) passaram a aceitar também o Trator 4.7m."
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

        # Checagem de qualidade (backlog item 65): avisa, não bloqueia.
        checagem = inv.checar_inventario(df_inv, df_bruto_inv)
        if checagem.empty:
            st.success("🔎 Checagem do inventário: nenhum problema encontrado (números, km, áreas, % manual + "
                       "mecanizada e trechos repetidos ou sobrepostos).")
        else:
            n_atencao = int((checagem["Gravidade"] == inv.ATENCAO).sum())
            n_linhas = checagem["Linha"].nunique()
            (st.warning if n_atencao else st.info)(
                f"🔎 Checagem do inventário: {len(checagem)} ponto(s) em {n_linhas} linha(s), {n_atencao} de atenção. "
                "O cálculo segue com os valores como estão; corrija a planilha e envie de novo, se for o caso."
            )
            with st.expander("Ver os pontos da checagem", expanded=n_atencao > 0):
                st.dataframe(checagem, width="stretch", hide_index=True)
                st.caption("Linha = linha da planilha (o cabeçalho é a linha 1)." if df_bruto_inv is not None
                           else "Linha = posição do trecho na tabela acima.")
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
                st.caption("Polígonos com mais de um equipamento indicado são alternativas (qualquer um faria a área): "
                           "a aba Roçada Mecanizada decide quem executa, aproveitando a folga da frota.")

# ---------------------------------------------------------------------------
# ABA: Vegetação e Clima (modelo de crescimento -> ciclos de roçada)
# ---------------------------------------------------------------------------
with aba_veg:
    st.subheader("Vegetação e Clima — ciclos de roçada pelo crescimento da vegetação")
    st.caption(
        "O ciclo é a frequência necessária para a vegetação não passar da altura máxima do contrato: "
        "**intervalo entre passagens = (altura máxima − altura pós-corte) ÷ crescimento (cm/dia)**. "
        "O crescimento depende das espécies (temperatura-base e velocidade de cada uma), da temperatura de cada mês "
        "e da água disponível, calculada por balanço hídrico (chuva − evaporação, com a água que o solo guarda de um "
        "mês para o outro). Resultado: ciclos sugeridos para as abas de roçada."
    )

    st.markdown("#### 1. Contrato")
    v1, v2, v3 = st.columns(3)
    opcao_hmax = v1.selectbox("Altura máxima permitida (contrato)", ["30 cm", "50 cm", "Outra"],
                              key="veg_hmax_opcao", help="30 cm é a grande maioria dos contratos; alguns usam 50 cm.")
    if opcao_hmax == "Outra":
        h_max = v1.number_input("Altura máxima (cm)", min_value=5.0, value=30.0, step=5.0, key="veg_hmax_outra")
    else:
        h_max = float(opcao_hmax.split()[0])
    h0 = v2.number_input("Altura pós-corte (cm)", min_value=0.0, max_value=20.0,
                         value=crescimento.ALTURA_POS_CORTE_PADRAO_CM, step=0.5, key="veg_h0",
                         help="Não é contratual: é o que a roçadeira deixa (normalmente 3 a 5 cm).")
    solo = v3.selectbox("Solo predominante", list(crescimento.SOLOS), index=list(crescimento.SOLOS).index(crescimento.SOLO_PADRAO),
                        key="veg_solo", help="Quanto de água o solo guarda para a planta (balanço hídrico): arenoso 40 mm, médio 70 mm, "
                             "argiloso 100 mm (estimativa). Solo que guarda mais segura o crescimento no começo da seca.")
    if h_max <= h0:
        st.error("A altura máxima precisa ser maior que a altura pós-corte.")

    st.markdown("#### 2. Localidade e clima")
    nomes_uf = {f"{v['nome']} ({uf})": uf for uf, v in crescimento.CLIMA_UF.items()}
    rotulos_uf = list(nomes_uf)
    l1, l2 = st.columns([2, 3])
    rotulo_uf = l1.selectbox("Estado", rotulos_uf, index=rotulos_uf.index("São Paulo (SP)"), key="veg_uf")
    clima = crescimento.CLIMA_UF[nomes_uf[rotulo_uf]]
    with l2:
        usar_coord = st.checkbox("Conheço a coordenada do trecho (mais preciso que o padrão do estado)", key="veg_usar_coord")
        if usar_coord:
            k1, k2, k3 = st.columns([2, 2, 2])
            lat = k1.number_input("Latitude", min_value=-34.0, max_value=6.0, value=float(clima["lat"]), format="%.4f", key="veg_lat")
            lon = k2.number_input("Longitude", min_value=-74.0, max_value=-28.0, value=float(clima["lon"]), format="%.4f", key="veg_lon")
            k3.markdown("&nbsp;")
            if k3.button("Buscar clima deste ponto"):
                try:
                    st.session_state["veg_clima_coord"] = crescimento.buscar_clima_coordenada(lat, lon)
                except Exception as e:  # rede bloqueada, API fora do ar etc.
                    st.session_state.pop("veg_clima_coord", None)
                    st.error(f"Não foi possível consultar a NASA POWER ({type(e).__name__}). Usando o padrão do estado.")
            clima_coord = st.session_state.get("veg_clima_coord")
            if clima_coord and abs(clima_coord["lat"] - lat) < 1e-6 and abs(clima_coord["lon"] - lon) < 1e-6:
                clima = clima_coord
            else:
                st.caption("Informe o ponto e clique em **Buscar clima deste ponto** (consulta gratuita à NASA POWER; "
                           "envia só a coordenada). Até lá, vale o padrão do estado.")
    st.caption(f"Clima em uso: **{clima['referencia']}** · Fonte: {clima.get('fonte', crescimento.FONTE_CLIMA)}")

    st.markdown("#### 3. Vegetação predominante")
    st.caption(
        "Informe as espécies mais presentes e a % aproximada de cobertura. O crescimento é a **média ponderada** "
        "pela cobertura (o objetivo é não estourar a altura em trechos grandes, de 100–200 m; pontos isolados se "
        "corrigem na operação). Se não souber, deixe 'Vegetação mista / não identificada'."
    )
    df_comp = st.data_editor(
        pd.DataFrame([{"Espécie": crescimento.ESPECIE_PADRAO, "Cobertura (%)": 100.0}]),
        key="veg_composicao", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "Espécie": st.column_config.SelectboxColumn(options=list(crescimento.ESPECIES), required=True),
            "Cobertura (%)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=5.0, required=True),
        },
    )
    composicao = {}
    for _, linha in df_comp.dropna().iterrows():
        composicao[linha["Espécie"]] = composicao.get(linha["Espécie"], 0.0) + float(linha["Cobertura (%)"])
    soma_cob = sum(composicao.values())
    if composicao and abs(soma_cob - 100) > 0.5:
        st.info(f"As coberturas somam {soma_cob:.0f}% — o cálculo usa as proporções entre elas (normaliza para 100%).")
    with st.expander("Parâmetros das espécies (temperatura-base, velocidade e fonte)"):
        st.dataframe(pd.DataFrame([
            {"Espécie": n, "Temperatura-base (°C)": e["tb"], "cm por grau-dia": e["k"], "Fonte": e["fonte"]}
            for n, e in crescimento.ESPECIES.items()
        ]), width="stretch", hide_index=True)

    st.markdown("#### 4. Calibração com dado de campo (opcional)")
    calibracao = 1.0
    with st.expander("Tenho medições de altura em campo"):
        st.caption(
            "Para cada ponto medido: o mês da medição, quantos dias se passaram desde a última roçada e a altura "
            "medida. O app compara o crescimento real com o que o modelo prevê para esses mesmos dias (considerando "
            "meados do mês da medição e os meses anteriores percorridos) e ajusta todos os meses pelo mesmo fator. "
            "A literatura usada vem de pastagem adubada — na faixa de domínio o crescimento real costuma ser menor, "
            "por isso calibrar é o que torna o número confiável para contrato."
        )
        df_obs = st.data_editor(
            pd.DataFrame({"Mês": pd.Series(dtype="str"), "Dias desde a última roçada": pd.Series(dtype="float"),
                          "Altura medida (cm)": pd.Series(dtype="float")}),
            key="veg_obs", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "Mês": st.column_config.SelectboxColumn(options=crescimento.MESES, required=True),
                "Dias desde a última roçada": st.column_config.NumberColumn(min_value=1, step=1),
                "Altura medida (cm)": st.column_config.NumberColumn(min_value=0.0, step=1.0),
            },
        )
        observacoes = [
            {"mes": crescimento.MESES.index(r["Mês"]), "dias": r["Dias desde a última roçada"], "altura_cm": r["Altura medida (cm)"]}
            for _, r in df_obs.dropna().iterrows() if r["Mês"] in crescimento.MESES
        ]
        fator = crescimento.fator_calibracao(observacoes, clima, composicao, solo, h0) if observacoes else None
        if fator:
            mem_cal = crescimento.memoria_calibracao(observacoes, clima, composicao, solo, h0)
            st.dataframe(pd.DataFrame([{
                "Mês": crescimento.MESES[x["mes"]], "Dias desde a roçada": int(x["dias"]), "Altura medida (cm)": x["altura"],
                f"Crescimento medido (cm) = altura − {h0:g}": round(x["medido"], 1),
                "Previsto pelo modelo nos mesmos dias (cm)": round(x["previsto"], 1),
                "Razão medido ÷ previsto": round(x["razao"], 2),
            } for x in mem_cal]), hide_index=True, width="stretch")
            st.caption(
                f"**Fator de calibração = média das razões = {fator:.2f}.** O previsto soma, dia a dia para trás a partir "
                "do meio do mês da medição, o crescimento do modelo sem calibração (térmico × água) de cada mês percorrido. "
                f"O fator multiplica o crescimento em cm/dia de **todos os meses** (passo 4 da memória de cálculo do resultado): "
                f"{fator:.2f} < 1 = o campo cresce menos que a literatura; > 1 = cresce mais."
            )
            if st.checkbox(f"Aplicar fator de calibração {fator:.2f} (medições: {len(observacoes)})", value=True, key="veg_usar_fator"):
                calibracao = fator
        elif observacoes:
            st.warning("Nenhuma medição válida: a altura medida precisa ser maior que a altura pós-corte.")
        st.caption("📷 Em estudo: ler a altura a partir de uma foto com régua/estaca graduada no enquadramento.")

    st.markdown("#### 5. Resultado")
    taxas = crescimento.taxa_mensal(clima, composicao, solo, calibracao)
    sincronizar_padrao("veg_meses_alto", [crescimento.MESES[i] for i in crescimento.meses_crescimento_alto(taxas)])
    meses_alto_sel = st.multiselect(
        "Meses do período de chuva / crescimento alto (os demais formam o período de seca)", crescimento.MESES,
        key="veg_meses_alto",
        help="Sugerido: meses com crescimento acima da média do ano. No Sul, onde chove o ano todo, quem separa os "
             "períodos é o frio do inverno.",
    )
    idx_alto = sorted(crescimento.MESES.index(m) for m in meses_alto_sel)
    idx_baixo = [i for i in range(12) if i not in idx_alto]
    criterio_rotulo = st.radio(
        "Critério", ["Mês mais crítico do período (recomendado)", "Média do período"], horizontal=True, key="veg_criterio",
        help="Mês mais crítico: a equipe dá conta mesmo no mês em que o capim cresce mais rápido. Média: dimensiona "
             "menos, mas no mês de pico parte dos trechos pode passar da altura.",
    )
    criterio = "critico" if criterio_rotulo.startswith("Mês") else "media"

    df_mensal = pd.DataFrame({
        "Mês": crescimento.MESES, "Temperatura média (°C)": clima["temp_c"], "Chuva (mm)": clima["chuva_mm"],
        "Água disponível (%)": [round(f * 100) for f in crescimento.fator_agua_mensal(clima, solo)],
        "Crescimento (cm/dia)": [round(t, 2) for t in taxas],
        "Período": ["Chuva" if i in idx_alto else "Seca" for i in range(12)],
    })
    g1, g2 = st.columns([3, 2])
    g1.bar_chart(df_mensal, x="Mês", y="Crescimento (cm/dia)", color="#5E22F3", height=260, sort=False)
    g2.dataframe(df_mensal, hide_index=True, width="stretch", height=260)

    if not idx_alto or not idx_baixo:
        st.warning("Deixe pelo menos um mês em cada período (chuva e seca).")
    elif h_max > h0:
        res_alto = crescimento.ciclos_periodo(taxas, idx_alto, h_max, h0, criterio)
        res_baixo = crescimento.ciclos_periodo(taxas, idx_baixo, h_max, h0, criterio)
        r1, r2 = st.columns(2)
        for col, nome_p, res, n_meses in ((r1, "chuva", res_alto, len(idx_alto)), (r2, "seca", res_baixo, len(idx_baixo))):
            with col:
                st.markdown(f"**Período de {nome_p}** — {n_meses} meses")
                if res["intervalo_dias"]:
                    st.metric("Ciclos no período (arredondado para cima)", math.ceil(res["ciclos"]),
                              help=f"Valor exato: {res['ciclos']:.2f} ciclos.")
                    st.caption(
                        f"Crescimento {res['taxa']:.2f} cm/dia → leva **{res['intervalo_dias']:.0f} dias** para ir de "
                        f"{h0:g} a {h_max:g} cm. É o prazo máximo para a equipe percorrer o trecho inteiro e voltar ao mesmo ponto."
                    )
                    if criterio == "critico":
                        idx_p = idx_alto if nome_p == "chuva" else idx_baixo
                        st.caption(f"📌 Mês que define os ciclos da {nome_p}: **{crescimento.MESES[max(idx_p, key=lambda i: taxas[i])]}** "
                                   "(o de crescimento mais rápido no período).")
                else:
                    st.metric("Ciclos no período", "0")
                    st.caption("Sem crescimento relevante neste período (frio ou seco demais para as espécies informadas).")
        linhas_mem = []
        for nome_p, res, idx_p in (("Chuva", res_alto, idx_alto), ("Seca", res_baixo, idx_baixo)):
            def _l(passo, conta, resultado):
                linhas_mem.append({"Período": nome_p, "Passo": passo, "Resultado": resultado, "Conta": conta})
            if criterio == "critico":
                m = crescimento.memoria_taxa(clima, composicao, solo, calibracao, max(idx_p, key=lambda i: taxas[i]))
                nome_mes = crescimento.MESES[m["mes"]]
                _l("Mês usado", "mês de crescimento mais rápido do período (critério mês crítico)",
                   f"{nome_mes} — {m['temp']:.1f} °C")
                for e in m["especies"]:
                    _l(f"1. Crescimento térmico — {e['especie']}",
                       f"{e['peso'] * 100:.0f}% da cobertura × {e['k']:g} cm/grau-dia × ({m['temp']:.1f} − {e['tb']:g} °C base)",
                       f"{e['contribuicao']:.3f} cm/dia")
                _l("2. Crescimento sem falta de água", " + ".join(f"{e['contribuicao']:.3f}" for e in m["especies"]),
                   f"{m['termico']:.3f} cm/dia")
                _l("3. × água disponível (balanço hídrico)", f"{m['termico']:.3f} × {m['agua']:.2f}",
                   f"{m['termico'] * m['agua']:.3f} cm/dia")
                _l("4. × fator de calibração", f"{m['termico'] * m['agua']:.3f} × {calibracao:.2f}"
                   + ("" if fator and calibracao != 1.0 else " (sem medição de campo aplicada)"), f"{m['taxa']:.3f} cm/dia")
            else:
                _l("1 a 4. Crescimento de cada mês", "térmico × água × calibração (tabela mensal): " + "; ".join(
                    f"{crescimento.MESES[i]} {taxas[i]:.3f}" for i in idx_p), "cm/dia")
                _l("Média do período", f"Σ(cm/dia × dias do mês) ÷ {res['dias']:.0f} dias", f"{res['taxa']:.3f} cm/dia")
            if res["intervalo_dias"]:
                _l("5. Dias até a altura máxima", f"({h_max:g} − {h0:g}) cm ÷ {res['taxa']:.3f} cm/dia",
                   f"{res['intervalo_dias']:.1f} dias")
                _l("6. Ciclos no período", f"{res['dias']:.0f} dias corridos do período ÷ {res['intervalo_dias']:.1f} dias",
                   f"{res['ciclos']:.2f} → {max(1, math.ceil(res['ciclos']))} ciclos (arredondado para cima)")
        with st.expander("🧮 Memória de cálculo do crescimento e dos ciclos"):
            st.caption(
                "Crescimento (cm/dia) = Σ[ % da cobertura × cm por grau-dia × (temperatura − temperatura-base) ] "
                "× água disponível × fator de calibração. Dias até a altura máxima = (altura máx. − pós-corte) ÷ "
                "crescimento. Ciclos = dias do período ÷ dias até a altura máxima."
            )
            st.dataframe(pd.DataFrame(linhas_mem), hide_index=True, width="stretch")
            st.caption("Esta tabela vai para o Excel (aba 'Memória crescimento') quando os ciclos são aplicados nas abas de roçada.")
        ciclos_sug = {"cc": max(1, math.ceil(res_alto["ciclos"])), "mc": len(idx_alto),
                      "cs": max(1, math.ceil(res_baixo["ciclos"])), "ms": len(idx_baixo)}
        ref = pp.CICLOS_PADRAO["rocada"]
        st.caption(
            f"Para comparar — referência padrão das abas de roçada: {ref['ciclos_chuva']} ciclos em {ref['meses_chuva']} meses "
            f"de chuva e {ref['ciclos_seca']} em {ref['meses_seca']} meses de seca ({ref['fonte']})."
        )
        if st.button("✅ Usar estes ciclos nas abas Roçada Manual e Roçada Mecanizada", type="primary"):
            for pre in ("man", "mec"):
                for chave, valor in ciclos_sug.items():
                    st.session_state[f"{pre}_{chave}"] = valor
            st.session_state["veg_versao"] = st.session_state.get("veg_versao", 0) + 1
            st.session_state["veg_aplicado"] = {
                "valores": ciclos_sug,
                "texto": (f"Modelo de crescimento — clima {clima['referencia']} ({rotulo_uf}); altura máx. {h_max:g} cm; "
                          f"pós-corte {h0:g} cm; solo {solo.lower()}; critério: {criterio_rotulo}; "
                          f"calibração {calibracao:.2f}; espécies: "
                          + ", ".join(f"{e} {p:.0f}%" for e, p in composicao.items())),
                "memoria": linhas_mem,
            }
            st.success("Ciclos e meses aplicados nas abas de roçada (você ainda pode editar lá).")

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
            ciclos_chuva = campo_ciclo("Ciclos no período de chuva", "man_cc", min_value=1, help="Quantas passagens completas no trecho DENTRO deste período (não por ano): o cálculo divide os dias do período por este número.")
            meses_chuva = campo_ciclo("Meses do período de chuva", "man_mc", min_value=1, max_value=12)
        with c2:
            st.markdown("**Cenário seca**")
            ciclos_seca = campo_ciclo("Ciclos no período de seca", "man_cs", min_value=1, help="Quantas passagens completas no trecho DENTRO deste período (não por ano): o cálculo divide os dias do período por este número.")
            meses_seca = campo_ciclo("Meses do período de seca", "man_ms", min_value=1, max_value=12)

        avisar_meses(meses_chuva, meses_seca)
        legenda_ciclos("man")
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
        # Fração sem arredondar: arredondar trecho a trecho e somar inflaria o total
        # (ex.: 60 trechos × 0,3 roçador = 60 "roçadores", contra 18 no total).
        df_trecho["roçadores (fração)"] = df_trecho["area_manual_m2"].apply(
            lambda a: round(dim.calcular_equipes(a, produtividade, pico_m.ciclos_periodo, pico_m.meses_periodo).equipes_exatas, 2)
        )

        with st.expander("Ver por trecho (roçadores)"):
            st.dataframe(df_trecho, width="stretch", hide_index=True)
            st.caption(
                f"Quanto de um roçador cada trecho consome no cenário de pico, sem arredondar. A soma "
                f"({df_trecho['roçadores (fração)'].sum():,.2f}) arredondada para cima dá o total acima "
                f"({pico_m.equipes_arredondadas}). Não some valores arredondados por trecho: isso infla o total."
            )

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

        # Três leituras do mesmo dimensionamento (pergunta 35): roçadores (o pico acima),
        # equipes da divisão e colaboradores totais (roçadores + motorista/apoio).
        n_equipes_m = len(grupos_m)
        colaboradores_m = n_equipes_m * int(total_equipe)
        st.session_state["resumo_rocada"]["Roçada Manual"].update({
            "equipes_divisao": n_equipes_m, "colaboradores_totais": colaboradores_m,
        })
        st.markdown("#### 🧮 Roçada manual em três contagens")
        t1, t2, t3 = st.columns(3)
        t1.metric("Roçadores (pico)", pico_m.equipes_arredondadas)
        t2.metric("Equipes", n_equipes_m)
        t3.metric("Colaboradores totais", colaboradores_m)
        st.caption(
            f"Roçadores = quem roça, pelo cálculo de pico. Equipes = proposta de divisão acima. Colaboradores totais = "
            f"{n_equipes_m} equipe(s) × {int(total_equipe)} ({int(rocadores_ativos)} roçando + "
            f"{int(total_equipe - rocadores_ativos)} motorista/apoio). As três vão para a Análise de Contrato, para "
            "comparar com o que o contrato prevê."
            + (f" As equipes têm {n_equipes_m * int(rocadores_ativos)} vagas de roçador, contra "
               f"{pico_m.equipes_arredondadas} necessárias: a diferença é a folga da última equipe ou da divisão por trecho."
               if n_equipes_m * int(rocadores_ativos) > pico_m.equipes_arredondadas else "")
        )

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
        areas_ind, indicado = mecanizacao.areas_por_equipamento(df_inv, equip_padrao)
        nomes_eq = list(dict.fromkeys(
            p_ for c_ in areas_ind.columns for p_ in c_.split(pp.SEPARADOR_ALTERNATIVAS)
        ))
        ordem_cat = {n: i for i, n in enumerate(pp.ROCADA_MECANIZADA)}
        nomes_eq.sort(key=lambda n: ordem_cat.get(n, 99))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Cenário chuva**")
            ciclos_chuva_m = campo_ciclo("Ciclos no período de chuva", "mec_cc", min_value=1, help="Quantas passagens completas no trecho DENTRO deste período (não por ano): o cálculo divide os dias do período por este número.")
            meses_chuva_m = campo_ciclo("Meses do período de chuva", "mec_mc", min_value=1, max_value=12)
        with c2:
            st.markdown("**Cenário seca**")
            ciclos_seca_m = campo_ciclo("Ciclos no período de seca", "mec_cs", min_value=1, help="Quantas passagens completas no trecho DENTRO deste período (não por ano): o cálculo divide os dias do período por este número.")
            meses_seca_m = campo_ciclo("Meses do período de seca", "mec_ms", min_value=1, max_value=12)
        avisar_meses(meses_chuva_m, meses_seca_m)
        legenda_ciclos("mec")

        if areas_ind.empty:
            st.info("Não há área mecanizada no inventário — nada a dimensionar nesta aba.")
        else:
            # ---- Frota necessária (aditiva) ----------------------------------
            st.markdown("### Frota necessária por equipamento")
            st.caption(
                "Cada equipamento atende a área indicada para ele — ou a de outro, quando a tabela de substituição "
                "permite e isso aproveita a folga de uma unidade que já existe —, então os números somam. Ajuste "
                "produtividade e frota disponível conforme a realidade."
            )
            st.info(
                "💡 'Qtd. disponível na frota' começa em 0 para todos os equipamentos — a coluna 'Situação da "
                "frota' na tabela abaixo só mostra sobra/falta depois que você preencher a frota real de cada um.",
                icon="💡",
            )
            cab = st.columns([3, 2, 2, 2])
            for col, t_ in zip(cab, ["Equipamento", "Produtividade (m²/dia)", "Qtd. disponível na frota", "Área atendida (m²)"]):
                col.markdown(f"**{t_}**")
            entradas, celulas_area = {}, {}
            for nome_eq in nomes_eq:
                l1, l2, l3, l4 = st.columns([3, 2, 2, 2])
                l1.markdown(f"**{nome_eq}**")
                prod = l2.number_input(f"Produtividade {nome_eq}", min_value=1, value=mecanizacao.produtividade_padrao(nome_eq),
                                       key=f"prod_{nome_eq}", label_visibility="collapsed")
                qtd_disp = l3.number_input(f"Frota {nome_eq}", min_value=0, value=0, key=f"qtd_{nome_eq}", label_visibility="collapsed")
                entradas[nome_eq] = (prod, qtd_disp)
                celulas_area[nome_eq] = l4.empty()
            st.caption("Produtividades marcadas como 'estimativa' em parametros_padrao.py — validar com dado de campo real antes de usar em contrato real.")

            # Quem pode fazer área indicada para outro (restrição de tamanho e acesso).
            with st.expander("🔁 Tabela de substituição — quem pode fazer área indicada para outro equipamento"):
                st.caption(
                    "A restrição é sempre de **tamanho e acesso**: o equipamento menor entra onde o maior entra (o "
                    "Trator 1.7m faz área do 4.7m; o Eixo-zero, menor que o 1.7m, faz as duas) e o braço articulado faz "
                    "área de Spider se alcançar. O app só usa a substituição para **ocupar a folga de unidades que já "
                    "existem** e eliminar unidades parciais — nunca cria unidade nova por causa dela. Ajuste conforme "
                    "o contrato."
                )
                df_subst = st.data_editor(
                    pd.DataFrame({
                        "Equipamento": nomes_eq,
                        "Também faz área indicada para": [
                            [x for x in pp.SUBSTITUICOES_PADRAO.get(n, []) if x in nomes_eq and x != n] for n in nomes_eq
                        ],
                    }),
                    key="mec_substituicoes", hide_index=True, width="stretch", num_rows="fixed", disabled=["Equipamento"],
                    column_config={"Também faz área indicada para": st.column_config.MultiselectColumn(
                        "Também faz área indicada para", options=nomes_eq)},
                )
            substituicoes = {
                r["Equipamento"]: [x for x in (r["Também faz área indicada para"] or []) if x != r["Equipamento"]]
                for _, r in df_subst.iterrows()
            }

            # Áreas com alternativas e substituições, pela capacidade de uma
            # unidade no período mais exigente.
            if ciclos_chuva_m / meses_chuva_m >= ciclos_seca_m / meses_seca_m:
                ciclos_ref, meses_ref = ciclos_chuva_m, meses_chuva_m
            else:
                ciclos_ref, meses_ref = ciclos_seca_m, meses_seca_m
            areas_eq, df_aloc, df_trocas = mecanizacao.alocar_frota(
                areas_ind, {n: e[0] for n, e in entradas.items()},
                {n: dim.capacidade_por_ciclo(e[0], ciclos_ref, meses_ref) for n, e in entradas.items()},
                substituicoes,
            )
            equipamentos = {}
            for nome_eq, (prod, qtd_disp) in entradas.items():
                area_eq = float(areas_eq[nome_eq].sum()) if nome_eq in areas_eq.columns else 0.0
                indicada = float(areas_ind[nome_eq].sum()) if nome_eq in areas_ind.columns else 0.0
                if area_eq <= 0 and indicada > 0:
                    celulas_area[nome_eq].markdown("0", help=f"{indicada:,.0f} m² indicados para ele foram assumidos pela folga "
                                                          "de outro equipamento (ver ♻️ Remanejamentos) — não precisa de unidade.")
                else:
                    celulas_area[nome_eq].markdown(f"{area_eq:,.0f}")
                if area_eq > 0:
                    equipamentos[nome_eq] = {"produtividade": prod, "qtd_disponivel": qtd_disp, "area": area_eq}
            if not df_aloc.empty:
                with st.expander(f"🔀 Áreas em que mais de um equipamento pode trabalhar — {df_aloc['Área (m²)'].sum():,.0f} m²"):
                    st.caption(
                        "Quando o inventário indica mais de um equipamento para o mesmo polígono (ex.: 'Trator 1.7m, "
                        "Spider'), as indicações são **alternativas independentes**: o trator poderia fazer a área "
                        "inteira e o spider também. A área **não é dividida** entre eles. Ela vai: **(1)** para a folga "
                        "das unidades que já são necessárias pela área exclusiva de cada equipamento (a última unidade "
                        "quase nunca fica 100% ocupada) e **(2)** o que sobrar, para a alternativa de maior "
                        "produtividade, que exige menos unidades novas."
                    )
                    st.dataframe(df_aloc, width="stretch", hide_index=True)
                memoria_divisoes["Alocação alternativas"] = df_aloc
            if not df_trocas.empty:
                with st.expander(f"♻️ Remanejamentos que eliminam unidades parciais — {df_trocas['Área (m²)'].sum():,.0f} m²"):
                    st.caption(
                        "Área que saiu do equipamento indicado (ou escolhido) para a **folga** de outro que pode fazê-la "
                        "(alternativa do polígono ou substituição pela tabela acima). Cada remanejamento só acontece se "
                        "elimina uma unidade inteira do equipamento de origem — sem criar unidade nova no destino."
                    )
                    st.dataframe(df_trocas, width="stretch", hide_index=True)
                memoria_divisoes["Remanejamentos"] = df_trocas

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
            total_exato = sum(r["pico"].equipes_exatas for r in resultados_eq.values())
            if total_pico - total_exato >= 0.5:
                st.caption(
                    f"🧮 Somando a fração exata de cada equipamento dá **{total_exato:.1f} unidades**; o arredondamento "
                    f"para cima de cada tipo separadamente acrescenta {total_pico - total_exato:.1f}. Essa diferença é "
                    "a folga das últimas unidades de cada tipo, que sobra quando nenhum outro equipamento pode "
                    "assumir aquela área (ver a tabela de substituição)."
                )
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
        st.caption(
            "Baseado no escopo do FS 4.0 (RioSP): roçada + aceiro + drenagem + capina + refilamento + calçada + "
            "placas + remoção de lixo. A roçada é dimensionada nas abas Roçada Manual/Mecanizada — aqui ficam só "
            "as demais atividades do pacote."
        )
        quadro_fs = st.container()
        linhas_relatorio = []
        linhas_resumo = []
        sem_dado = []
        for nome_ativ, cfg in pp.FULL_SERVICE_ATIVIDADES.items():
            coluna = pp.COLUNA_INVENTARIO_POR_ATIVIDADE.get(nome_ativ)
            tem_coluna = bool(coluna and coluna in df_inv.columns)
            quantidade_padrao = float(df_inv[coluna].sum()) if tem_coluna else 0.0

            with st.expander(f"{nome_ativ}  —  {quantidade_padrao:,.1f} {cfg['unidade']} no inventário"):
                sincronizar_padrao(f"fs_qtd_{nome_ativ}", quantidade_padrao)
                quantidade = st.number_input(
                    f"Quantidade ({cfg['unidade']})" + ("" if tem_coluna else " — não há coluna no inventário, informe manualmente"),
                    min_value=0.0, key=f"fs_qtd_{nome_ativ}",
                )
                if cfg.get("modo") == "anual":
                    cchuva, mchuva, cseca, mseca, meta = atividade_ciclos_por_ano(nome_ativ, cfg, quantidade)
                    resultado = dim.dimensionar_chuva_seca(quantidade, meta, cchuva, mchuva, cseca, mseca)
                else:
                    col1, col2, col3 = st.columns(3)
                    meta = col1.number_input("Meta/dia por equipe", min_value=0.01, value=float(cfg["meta_dia"]), key=f"fs_meta_{nome_ativ}")
                    cchuva = col2.number_input("Ciclos no período de chuva", min_value=1, value=cfg["ciclos_chuva"], key=f"fs_cc_{nome_ativ}")
                    mchuva = col2.number_input("Meses (chuva)", min_value=1, max_value=12, value=cfg["meses_chuva"], key=f"fs_mc_{nome_ativ}")
                    cseca = col3.number_input("Ciclos no período de seca", min_value=1, value=cfg["ciclos_seca"], key=f"fs_csc_{nome_ativ}")
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
                origem = f"Inventário: coluna {coluna}" if tem_coluna and quantidade == quantidade_padrao else "Informada manualmente"
                registrar("Full Service", nome_ativ, cfg["unidade"], "equipe(s)", quantidade,
                          origem, meta, cchuva, mchuva, cseca, mseca, cfg["fonte"])
                linhas_resumo.append({
                    "atividade": nome_ativ, "quantidade": quantidade, "unidade": cfg["unidade"],
                    "origem": "Inventário" if origem.startswith("Inventário") else "Manual",
                    "chuva": resultado["chuva"].equipes_arredondadas, "seca": resultado["seca"].equipes_arredondadas,
                    "pico": resultado["pico"].equipes_arredondadas, "fonte": cfg["fonte"],
                })
                if quantidade <= 0:
                    sem_dado.append(nome_ativ)
        if sem_dado:
            st.info(
                f"💡 {len(sem_dado)} de {len(pp.FULL_SERVICE_ATIVIDADES)} atividades estão com quantidade zero "
                f"({', '.join(sem_dado)}) — ainda assim aparecem na Análise de Contrato e nos relatórios como "
                "'0 / Conforme'. Se o inventário veio só do Quasar (que não cobre essas atividades), abra o "
                "expansor de cada uma e informe a quantidade manualmente, se aplicável a este contrato.",
                icon="💡",
            )
        mostrar_quadro_resumo(quadro_fs, linhas_resumo, ("Chuva", "Seca"))
        st.session_state["resultados_atividades"]["Full Service"] = linhas_relatorio

# ---------------------------------------------------------------------------
# ABA: Especialistas
# ---------------------------------------------------------------------------
with aba_esp:
    st.subheader("Dimensionamento — Equipes Especialistas")
    st.caption("EPS/barreira, defensa metálica, NC, varrição e poda — geralmente fora do pacote Full Service.")
    quadro_esp = st.container()
    linhas_relatorio = []
    linhas_resumo = []
    sem_dado = []
    for nome_ativ, cfg in pp.ESPECIALISTAS_ATIVIDADES.items():
        coluna = pp.COLUNA_INVENTARIO_POR_ATIVIDADE.get(nome_ativ)
        if coluna and df_inv is not None and coluna in df_inv.columns:
            quantidade_padrao = float(df_inv[coluna].sum())
        else:
            quantidade_padrao = 0.0

        with st.expander(f"{nome_ativ}"):
            # Acompanha o inventário (inclusive troca de arquivo/origem) até o
            # usuário editar o campo -- ver sincronizar_padrao().
            sincronizar_padrao(f"esp_qtd_{nome_ativ}", quantidade_padrao)
            quantidade = st.number_input(
                f"Quantidade ({cfg['unidade']}) — {'preenchido do inventário, ajuste se necessário' if coluna else 'não há coluna no inventário, informe manualmente'}",
                min_value=0.0, key=f"esp_qtd_{nome_ativ}",
            )
            if cfg.get("ajuda_qtd"):
                st.caption(f"ℹ️ {cfg['ajuda_qtd']}")

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
                linhas_resumo.append({
                    "atividade": f"{nome_ativ} (reativo)", "quantidade": volume_anual, "unidade": "acionamento(s)/ano",
                    "origem": f"Taxa × {extensao_km_ativ:,.1f} km",
                    "chuva": resultado["chuva"].equipes_arredondadas, "seca": resultado["seca"].equipes_arredondadas,
                    "pico": resultado["pico"].equipes_arredondadas,
                    "fonte": cfg.get("fonte_reativo", "estimativa (a validar)"),
                })
                if coluna and quantidade <= 0:
                    sem_dado.append(nome_ativ)
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
                linhas_resumo.append({
                    "atividade": nome_ativ, "quantidade": quantidade, "unidade": cfg["unidade"],
                    "origem": "Inventário" if veio_do_inventario else "Manual",
                    "chuva": resultado["chuva"].equipes_arredondadas, "seca": resultado["seca"].equipes_arredondadas,
                    "pico": resultado["pico"].equipes_arredondadas, "fonte": cfg["fonte"],
                })
                if coluna and quantidade <= 0:
                    sem_dado.append(nome_ativ)
    if sem_dado:
        st.info(
            f"💡 {len(sem_dado)} atividade(s) têm coluna própria no inventário, mas estão com quantidade zero "
            f"({', '.join(sem_dado)}) — ainda assim aparecem na Análise de Contrato e nos relatórios como "
            "'0 / Conforme'. Se o inventário veio só do Quasar (que não cobre EPS/barreira e defensa), abra o "
            "expansor de cada uma e informe a quantidade manualmente, se aplicável a este contrato.",
            icon="💡",
        )
    mostrar_quadro_resumo(quadro_esp, linhas_resumo, ("Cenário 1", "Cenário 2"))
    st.session_state["resultados_atividades"]["Especialistas"] = linhas_relatorio

# ---------------------------------------------------------------------------
# ABA: Análise de Contrato
# ---------------------------------------------------------------------------
with aba_analise:
    titulo_analise = "Análise de Contrato — Dimensionado × Contratado"
    st.subheader(f"{titulo_analise} ({unidade_avaliada})" if unidade_avaliada else titulo_analise)
    st.caption("Informe quantas equipes/unidades o contrato atual prevê para cada atividade, para comparar com o dimensionamento.")
    quadro_analise = st.container()

    todas_atividades = []
    for nome_r, r in st.session_state["resumo_rocada"].items():
        todas_atividades.append((nome_r, r["equipes_arredondadas"], r.get("unidade", "equipe(s)")))
        if "equipes_divisao" in r:  # Roçada Manual: também equipes e colaboradores totais (pergunta 35)
            todas_atividades.append((f"{nome_r} — equipes", r["equipes_divisao"], "equipe(s) de roçada"))
            todas_atividades.append((f"{nome_r} — colaboradores totais", r["colaboradores_totais"], "colaborador(es)"))
    for grupo, linhas in st.session_state["resultados_atividades"].items():
        for linha in linhas:
            todas_atividades.append((linha[0], linha[-1], "equipe(s)"))  # (nome, equipes_pico, unidade)

    linhas_analise = []
    totais_analise = {}  # unidade -> [dimensionado, contratado]: roçadores, equipamentos e equipes não se somam
    if not todas_atividades:
        st.warning("Calcule o dimensionamento nas abas anteriores primeiro.")
    else:
        for nome_ativ, dimensionado, unidade in todas_atividades:
            col1, col2, col3 = st.columns([3, 1, 2])
            col1.markdown(f"**{nome_ativ}**")
            col1.caption(f"Dimensionado: {dimensionado} {unidade}")
            # Nasce igual ao dimensionado e o acompanha até o usuário editar
            # (antes ficava congelado no 1º valor -- ex.: 0 antes do inventário --
            # e gerava "déficit de 100%" falso).
            # Chave sem o sufixo do modo: o Contratado de EPS/defensa sobrevive à troca Preventivo/Reativo.
            chave_contr = f"contr_{nome_ativ.removesuffix(' (reativo)')}"
            sincronizar_padrao(chave_contr, int(dimensionado))
            contratado = col2.number_input("Contratado", min_value=0, key=chave_contr)
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
            totais_unidade = totais_analise.setdefault(unidade, [0, 0])
            totais_unidade[0] += dimensionado
            totais_unidade[1] += contratado
        mostrar_totais_analise(quadro_analise, linhas_analise, totais_analise)
    st.session_state["analise_contrato"] = linhas_analise
    st.session_state["totais_analise"] = totais_analise

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
    ("Roçada mecanizada", "A área mecanizada de cada trecho vai para o equipamento indicado pelo Quasar. Polígonos com mais "
                          "de um equipamento indicado são alternativas (qualquer um faria a área inteira, não há divisão): a área "
                          "preenche primeiro a folga das unidades já necessárias e o restante vai para a alternativa de maior "
                          "produtividade (ver aba 'Alocação alternativas'). Depois, área de um equipamento passa para a folga de "
                          "outro que pode fazê-la (tabela de substituição por tamanho e acesso) sempre que isso elimina uma "
                          "unidade inteira (aba 'Remanejamentos'). Regra do Trator 4,70 no Quasar: canteiro indicado para Trator "
                          "1.7m, mais largo que o limite e sem bloqueio, aceita também o 4.7m. Produtividades por equipamento "
                          "são estimativas a validar com dado de campo."),
    ("Divisão por trecho", "Trechos percorridos por rodovia e km; cada unidade é preenchida até a capacidade do ciclo antes "
                           "de abrir a seguinte; um trecho é cortado no km em que a capacidade acaba. Só a última unidade pode ter folga."),
    ("Extensão (Quasar)", "Extensão física = do 1º ao último km mapeado de cada rodovia (passo entre posições), sem somar "
                          "polígonos de canteiro lateral/central nem sentidos. Ver aba Auditoria Quasar."),
    ("Parâmetros estimados", "Parâmetros com fonte 'estimativa (a validar)' não têm lastro em dado de campo — não usar para "
                             "decisão de contrato sem validação técnica."),
]
if ciclos_do_modelo("man") or ciclos_do_modelo("mec"):
    premissas.append(("Ciclos de roçada", st.session_state["veg_aplicado"]["texto"] + ". Ciclos no período = dias do "
                      "período ÷ ((altura máx. − pós-corte) ÷ crescimento em cm/dia), arredondado para cima. Passo a passo "
                      "na aba 'Memória crescimento'."))
    if st.session_state["veg_aplicado"].get("memoria"):
        memoria_divisoes["Memória crescimento"] = pd.DataFrame(st.session_state["veg_aplicado"]["memoria"])

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

    # O Streamlit executa o `data=` dos botões de download numa thread separada,
    # SEM acesso ao st.session_state (st.session_state[...] dá KeyError e .get()
    # devolve None em silêncio). Por isso os dados são capturados aqui, durante
    # a execução normal do script, e as funções abaixo só usam essas variáveis.
    resumo_rocada_exp = st.session_state["resumo_rocada"]
    resultados_exp = st.session_state["resultados_atividades"]
    analise_exp = st.session_state.get("analise_contrato")
    totais_exp = st.session_state.get("totais_analise")

    def _bytes_pptx():
        with tempfile.TemporaryDirectory() as tmp:
            caminho = str(Path(tmp) / "DimConservacao_Relatorio.pptx")
            export_pptx.gerar_relatorio(
                caminho_saida=caminho, nome_contrato=nome_unidade,
                resumo_rocada=resumo_rocada_exp,
                resultados_atividades=resultados_exp,
                analise_contrato=analise_exp, totais_analise=totais_exp,
            )
            return Path(caminho).read_bytes()

    def _bytes_excel():
        return export_excel.gerar_memoria_calculo({
            "unidade": nome_unidade, "data": f"{date.today():%d/%m/%Y}", "dias_uteis_mes": dim.DIAS_UTEIS_MES_PADRAO,
            "atividades": memoria_atividades, "analise": analise_exp,
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
