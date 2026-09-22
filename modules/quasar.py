"""Leitura, auditoria e agregação do mapeamento Quasar (satélite) de área
manual x mecanizada, exportado pela Motiva em planilha Excel.

O export Quasar traz um polígono por linha (segmento de ~0,5 km de um
canteiro/sentido específico), com `% mecanização` calculado por satélite.
Isso é muito mais granular que um "trecho" do inventário do app (que cobre
uma faixa larga de km), então aqui agregamos os polígonos por rodovia + faixa
de km para virar linhas de inventário com área total e % manual/mecanizada
média ponderada pela área de cada polígono.

Cuidado importante (ver retroanalises/perguntas_pendentes.md): dentro do
mesmo km físico de rodovia existem vários polígonos -- canteiro lateral (nos
dois sentidos) e canteiro central (um só, compartilhado) -- então a
EXTENSÃO real da rodovia não pode ser a soma bruta do comprimento de cada
polígono (contaria o mesmo km várias vezes); já a ÁREA VERDE soma normalmente
entre todos os polígonos, pois é área física real a ser roçada.

ATENÇÃO (auditoria de 2026-09-21): o comprimento de CADA polígono (DELTA KM,
tipicamente 0,5 km) NÃO é o passo entre posições de km. No export AB os
polígonos existem só a cada 1,0 km (km 1,0; 2,0; 3,0...), cada um cobrindo
0,5 km. Por isso a extensão é calculada pelo PASSO entre posições distintas
(mediana das diferenças), não pelo comprimento do polígono -- do contrário a
extensão do AB sai pela metade (157 km em vez de ~314 km). A contagem de km
com canteiro central (157/73/6/2 km) bate com a aba "Canteiro central" do
próprio export, o que confirma o critério.
"""
import re
import unicodedata

import numpy as np
import pandas as pd

from modules import parametros_padrao as pp

# Sobe a cada mudança no formato dos DataFrames gerados aqui: entra na chave do
# cache do app, evitando reaproveitar resultado calculado por uma versão antiga.
VERSAO = "2026-09-21b"

COLUNAS_ESPERADAS = ["id", "km_inicial", "km_final", "area_m2", "pct_mecanizacao"]

# O 1o token do ID Motiva (antes do primeiro "_") e sempre o codigo da
# rodovia -- confirmado nos 2 exports reais recebidos, embora o formato varie
# por regional:
#   - QUASAR AB: "VGSP-102_001,000_ES_CL3" -> "VG" colado direto no codigo
#     ("VGSP-102"), sem "_" entre eles.
#   - QUASAR Sorocabana: "SP-075_0,000_S_CL_2" -> sem prefixo "VG"; tambem
#     aparecem codigos compostos como "SPA-160/250" e "SPI-091/270".
# NAO usar um regex "solto" escaneando todos os tokens: tokens do MEIO do ID
# (ex: "CL11", "CC2" -- canteiro lateral/central) tambem casam com um padrao
# generico de "2 letras + digitos" e seriam confundidos com rodovias.
_PREFIXO_QUASAR = re.compile(r"^VG(?=[A-Z])")
_RODOVIA_SEM_HIFEN = re.compile(r"^([A-Z]{2,3})(\d{2,4})$")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


def _extrair_rodovia(id_str: str) -> str:
    """Extrai o código da rodovia a partir do 1º token do ID Motiva (antes do
    primeiro "_"), removendo o prefixo fixo "VG" do Quasar quando colado
    direto no código (ex: "VGSP-330" -> "SP-330") e inserindo hífen quando
    o regional não usa separador (ex: "SP102" -> "SP-102"). Códigos compostos
    (ex: "SPA-160/250") são mantidos como vieram."""
    primeiro = str(id_str).split("_")[0].strip()
    if not primeiro or primeiro.lower() == "nan":
        return ""
    primeiro = _PREFIXO_QUASAR.sub("", primeiro).upper()
    m = _RODOVIA_SEM_HIFEN.match(primeiro)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return primeiro


def _mapear_colunas(colunas) -> dict:
    """Encontra, entre as colunas da planilha, as que correspondem a cada
    campo esperado -- os exports Quasar de regionais diferentes usam nomes de
    coluna ligeiramente distintos (ex: 'ID' vs 'ID Motiva/Quasar')."""
    normalizadas = {c: _normalizar(c) for c in colunas}
    mapa = {}
    for original, norm in normalizadas.items():
        if norm.startswith("id") and "id" not in mapa:
            mapa["id"] = original
        elif norm == "km inicial":
            mapa["km_inicial"] = original
        elif norm == "km final":
            mapa["km_final"] = original
        elif norm == "area":
            mapa["area_m2"] = original
        elif norm == "% mecanizacao":
            mapa["pct_mecanizacao"] = original
        elif norm == "equipamento":
            mapa["equipamento"] = original
        elif norm.startswith("largura media"):
            mapa["largura_m"] = original
        elif norm == "inclinacao":
            mapa["inclinacao"] = original
        elif norm == "canteiro":
            mapa["canteiro"] = original
        elif norm == "sentido":
            mapa["sentido"] = original
    return mapa


def _achar_aba_de_dados(caminho_ou_arquivo) -> tuple[str, dict]:
    """Procura, entre as abas do arquivo, a que contem os polígonos (tem uma
    coluna '% mecanização') -- ignora abas auxiliares como 'Resumo' ou
    'Canteiro central'."""
    planilha = pd.ExcelFile(caminho_ou_arquivo)
    for aba in planilha.sheet_names:
        cabecalho = pd.read_excel(planilha, sheet_name=aba, nrows=0)
        mapa = _mapear_colunas(cabecalho.columns)
        if "pct_mecanizacao" in mapa and "km_inicial" in mapa and "area_m2" in mapa:
            return aba, mapa
    raise ValueError(
        "Não encontrei nenhuma aba com colunas de 'Km inicial' e '% mecanização' "
        "neste arquivo -- confirme se é um export Quasar válido."
    )


def _para_float_km(valor) -> float:
    if isinstance(valor, str):
        valor = valor.replace(",", ".")
    return float(valor)


def carregar_quasar(caminho_ou_arquivo) -> pd.DataFrame:
    """Lê o export Quasar e devolve um DataFrame normalizado, um polígono por
    linha: id, rodovia, km_inicial, km_final, area_m2, pct_mecanizacao,
    area_mecanizada_m2, equipamento, canteiro, sentido, largura_m, inclinacao."""
    aba, mapa = _achar_aba_de_dados(caminho_ou_arquivo)
    df_bruto = pd.read_excel(caminho_ou_arquivo, sheet_name=aba)

    df = pd.DataFrame()
    df["id"] = df_bruto[mapa["id"]].astype(str)
    df["rodovia"] = df["id"].apply(_extrair_rodovia)
    df["km_inicial"] = df_bruto[mapa["km_inicial"]].apply(_para_float_km)
    df["km_final"] = df_bruto[mapa["km_final"]].apply(_para_float_km)
    df["area_m2"] = pd.to_numeric(df_bruto[mapa["area_m2"]], errors="coerce").fillna(0)
    df["pct_mecanizacao"] = pd.to_numeric(df_bruto[mapa["pct_mecanizacao"]], errors="coerce").fillna(0)
    df["area_mecanizada_m2"] = df["area_m2"] * (df["pct_mecanizacao"] / 100)
    df["equipamento"] = df_bruto[mapa["equipamento"]].fillna("").astype(str) if "equipamento" in mapa else ""
    df["canteiro"] = df_bruto[mapa["canteiro"]].fillna("").astype(str) if "canteiro" in mapa else ""
    df["sentido"] = df_bruto[mapa["sentido"]].fillna("").astype(str) if "sentido" in mapa else ""
    df["largura_m"] = pd.to_numeric(df_bruto[mapa["largura_m"]], errors="coerce") if "largura_m" in mapa else np.nan
    df["inclinacao"] = pd.to_numeric(df_bruto[mapa["inclinacao"]], errors="coerce") if "inclinacao" in mapa else np.nan

    df = df.dropna(subset=["rodovia"])
    df = df[~df["rodovia"].str.lower().isin(["none", "nan", ""])]
    return df.reset_index(drop=True)


def _tamanho_segmento_padrao(df_quasar: pd.DataFrame) -> float:
    """Comprimento típico de UM polígono (km) -- tipicamente 0,5 km. Serve para
    medir a cobertura do mapeamento; NÃO é o passo entre posições de km."""
    extensoes = (df_quasar["km_final"] - df_quasar["km_inicial"]).abs()
    extensoes = extensoes[extensoes > 0]
    return float(extensoes.median()) if not extensoes.empty else 0.5


def _passo_entre_posicoes(posicoes, tamanho_segmento: float) -> float:
    """Distância típica (mediana) entre posições de km consecutivas de uma
    rodovia. No AB é 1,0 km (polígonos de 0,5 km a cada 1 km); na Sorocabana é
    0,5 km (cobertura contínua). Com uma só posição, assume o tamanho do
    segmento."""
    posicoes = np.sort(np.unique(np.asarray(posicoes, dtype=float)))
    if len(posicoes) < 2:
        return tamanho_segmento
    return float(np.median(np.diff(posicoes)))


def _tokens_equipamento(texto: str) -> list[str]:
    return [pp.canonizar_equipamento(t) for t in str(texto).split(",") if t.strip()]


def _area_por_equipamento(df: pd.DataFrame) -> pd.DataFrame:
    """Distribui a área mecanizada de cada polígono entre os equipamentos
    indicados na coluna 'Equipamento' (divisão igual quando há mais de um,
    ex: 'Trator 1.7m, Spider'). Devolve uma coluna por equipamento (nome
    canônico), alinhada ao índice de `df`. Polígono mecanizado sem
    equipamento indicado cai em 'Sem equipamento indicado'."""
    partes: dict[str, dict] = {}
    for idx, linha in df[df["area_mecanizada_m2"] > 0].iterrows():
        area_mec = linha["area_mecanizada_m2"]
        tokens = _tokens_equipamento(linha["equipamento"]) or ["Sem equipamento indicado"]
        for t in tokens:
            partes.setdefault(t, {})[idx] = partes.get(t, {}).get(idx, 0.0) + area_mec / len(tokens)
    return pd.DataFrame({t: pd.Series(v) for t, v in partes.items()}, index=df.index).fillna(0.0)


def fator_cobertura_por_rodovia(df: pd.DataFrame) -> dict:
    """cobertura = (comprimento do polígono) / (passo entre posições), limitada
    a 100%. AB: 0,5 / 1,0 = 50%. Sorocabana: 0,5 / 0,5 = 100%."""
    seg = _tamanho_segmento_padrao(df)
    return {
        rod: min(1.0, seg / _passo_entre_posicoes(g["km_inicial"].unique(), seg))
        for rod, g in df.groupby("rodovia")
    }


def agregar_por_trecho(
    df_quasar: pd.DataFrame, tamanho_km: float = 5.0, extrapolar_cobertura: bool = False
) -> pd.DataFrame:
    """Agrupa os polígonos Quasar por rodovia + faixa de km (tamanho_km cada),
    devolvendo linhas de inventário: trecho, rodovia, km_inicial, km_final,
    extensao_km, area_verde_m2, pct_mecanizada, pct_manual,
    equipamento_predominante, largura_media_m, inclinacao_media e uma coluna
    `mec_m2__<equipamento>` por equipamento (área mecanizada que cada um atende).

    Extensão: (última posição de km − primeira posição) + passo entre
    posições, limitada ao tamanho da faixa. Não soma polígonos (canteiro
    lateral/central e os dois sentidos contariam o mesmo km várias vezes).

    extrapolar_cobertura: quando o mapeamento só cobre parte de cada km (ex: AB,
    50%), multiplica as áreas por 1/cobertura para estimar a rodovia inteira.
    Desligado por padrão -- é uma premissa que o usuário precisa validar.
    """
    df = df_quasar.copy()
    tamanho_segmento = _tamanho_segmento_padrao(df)
    cobertura = fator_cobertura_por_rodovia(df)

    area_eq = _area_por_equipamento(df)
    df = df.join(area_eq)
    colunas_eq = list(area_eq.columns)

    if extrapolar_cobertura:
        fator = df["rodovia"].map(lambda r: 1.0 / cobertura.get(r, 1.0))
        for c in ["area_m2", "area_mecanizada_m2"] + colunas_eq:
            df[c] = df[c] * fator

    df["faixa_km"] = (df["km_inicial"] // tamanho_km) * tamanho_km
    passo_rod = {
        rod: _passo_entre_posicoes(g["km_inicial"].unique(), tamanho_segmento)
        for rod, g in df.groupby("rodovia")
    }

    linhas = []
    for (rodovia, faixa), grupo in df.groupby(["rodovia", "faixa_km"]):
        area_total = grupo["area_m2"].sum()
        if area_total <= 0:
            continue
        area_mecanizada = grupo["area_mecanizada_m2"].sum()
        pct_mecanizada = round(100 * area_mecanizada / area_total, 1)
        passo = passo_rod[rodovia]
        pos_min, pos_max = grupo["km_inicial"].min(), grupo["km_inicial"].max()
        extensao_km = round(min((pos_max - pos_min) + passo, tamanho_km), 2)

        linha = {
            "trecho": f"{rodovia} — km {pos_min:.1f} a {pos_min + extensao_km:.1f}",
            "rodovia": rodovia,
            "km_inicial": pos_min,
            "km_final": pos_min + extensao_km,
            "extensao_km": extensao_km,
            "area_verde_m2": area_total,
            "pct_mecanizada": pct_mecanizada,
            "pct_manual": round(100 - pct_mecanizada, 1),
        }
        if colunas_eq and area_mecanizada > 0:
            por_eq = grupo[colunas_eq].sum()
            linha["equipamento_predominante"] = por_eq.idxmax() if por_eq.max() > 0 else ""
        else:
            linha["equipamento_predominante"] = ""
        pesos = grupo["area_m2"]
        for campo, nome in (("largura_m", "largura_media_m"), ("inclinacao", "inclinacao_media")):
            validos = grupo[campo].notna() & (pesos > 0)
            linha[nome] = (
                round(float(np.average(grupo.loc[validos, campo], weights=pesos[validos])), 2)
                if validos.any() else np.nan
            )
        for c in colunas_eq:
            linha[pp.coluna_area_equipamento(c)] = float(grupo[c].sum())
        linhas.append(linha)

    resultado = pd.DataFrame(linhas)
    # Ordena por rodovia e km NUMERICO (ordenar pelo texto do trecho poria
    # "km 100" antes de "km 11").
    return resultado.sort_values(["rodovia", "km_inicial"]).reset_index(drop=True)


def equipamentos_do_inventario(df_inventario: pd.DataFrame) -> dict:
    """Lê as colunas mec_m2__* do inventário e devolve {nome do equipamento:
    coluna}. O nome vem do catálogo (pp.ROCADA_MECANIZADA) ou, se o
    equipamento não está no catálogo, do texto da coluna."""
    achados = {}
    nomes_catalogo = {pp.coluna_area_equipamento(n): n for n in pp.ROCADA_MECANIZADA}
    for c in df_inventario.columns:
        if str(c).startswith("mec_m2__"):
            nome = nomes_catalogo.get(c) or (
                "Sem equipamento indicado" if c == "mec_m2__sem_equipamento_indicado"
                else str(c)[len("mec_m2__"):].replace("_", " ").title()
            )
            achados[nome] = c
    return achados


def auditar_quasar(df_quasar: pd.DataFrame) -> dict:
    """Confere o export Quasar e devolve:
      - por_rodovia: DataFrame com extensão física, posições mapeadas, passo,
        cobertura do mapeamento, lacunas, km com canteiro central, área e %
        mecanizado, e quanto a soma bruta de polígonos inflaria a extensão;
      - alertas: lista de (nivel, texto) com o que merece atenção;
      - totais: dict com extensão e área totais.
    """
    seg = _tamanho_segmento_padrao(df_quasar)
    linhas, alertas = [], []
    for rod, g in df_quasar.groupby("rodovia"):
        posicoes = np.sort(g["km_inicial"].unique())
        passo = _passo_entre_posicoes(posicoes, seg)
        extensao = float((posicoes.max() - posicoes.min()) + passo)
        cobertura = min(1.0, seg / passo) * 100
        lacunas = int((np.diff(posicoes) > passo * 1.01).sum()) if len(posicoes) > 1 else 0
        km_lacuna = max(0.0, extensao - len(posicoes) * passo)
        cc = g.loc[g["canteiro"].str.upper() == "CC", "km_inicial"].nunique()
        area = float(g["area_m2"].sum())
        area_mec = float(g["area_mecanizada_m2"].sum())
        bruto = float((g["km_final"] - g["km_inicial"]).abs().sum())
        linhas.append({
            "Rodovia": rod,
            "Km inicial": float(posicoes.min()),
            "Km final": float(posicoes.max() + passo),
            "Extensão física (km)": round(extensao, 1),
            "Posições de km mapeadas": len(posicoes),
            "Passo entre posições (km)": round(passo, 2),
            "Cobertura do mapeamento (%)": round(cobertura, 0),
            "Km sem polígono (lacunas)": round(km_lacuna, 1),
            "Km com canteiro central": int(cc),
            "Polígonos": len(g),
            "Área verde (m²)": round(area, 0),
            "% mecanizada": round(100 * area_mec / area, 1) if area else 0.0,
            "Soma bruta dos polígonos (km)": round(bruto, 1),
            "Inflação da soma bruta (x)": round(bruto / extensao, 1) if extensao else 0.0,
        })
        if cobertura < 99:
            alertas.append((
                "atencao",
                f"{rod}: os polígonos cobrem só {cobertura:.0f}% de cada km (segmento de {seg:g} km a cada "
                f"{passo:g} km). A extensão foi calculada pelo passo ({extensao:.1f} km). O mapeamento é para "
                "ser contínuo (1 polígono a cada 500 m) — se a área verde total desta rodovia parecer baixa "
                "frente ao que se espera em campo, pode haver polígonos faltando; se já bate com o esperado, "
                "não é preciso extrapolar."
            ))
        if lacunas:
            alertas.append((
                "info",
                f"{rod}: {lacunas} lacuna(s) sem polígono no meio da rodovia (~{km_lacuna:.1f} km no total). "
                "A extensão física inclui esses trechos."
            ))
    por_rodovia = pd.DataFrame(linhas)

    if df_quasar["id"].duplicated().any():
        n = int(df_quasar["id"].duplicated().sum())
        alertas.append((
            "info", f"{n} ID(s) repetido(s) no arquivo (polígonos distintos com o mesmo ID). "
            "Ambos foram mantidos e somados; confira se não é linha duplicada de fato."
        ))
    n_sem_area = int((df_quasar["area_m2"] <= 0).sum())
    if n_sem_area:
        alertas.append(("info", f"{n_sem_area} polígono(s) com área zero/ausente (não afetam a área total)."))
    sem_equip = df_quasar[(df_quasar["area_mecanizada_m2"] > 0) & (df_quasar["equipamento"].str.strip() == "")]
    if len(sem_equip):
        alertas.append((
            "atencao", f"{len(sem_equip)} polígono(s) mecanizado(s) sem equipamento indicado "
            f"({sem_equip['area_mecanizada_m2'].sum():,.0f} m²) — aparecem como 'Sem equipamento indicado'."
        ))

    totais = {
        "extensao_km": float(por_rodovia["Extensão física (km)"].sum()) if len(por_rodovia) else 0.0,
        "area_verde_m2": float(df_quasar["area_m2"].sum()),
        "area_mecanizada_m2": float(df_quasar["area_mecanizada_m2"].sum()),
        "poligonos": len(df_quasar),
        "rodovias": len(por_rodovia),
        "tamanho_segmento_km": seg,
    }
    return {"por_rodovia": por_rodovia, "alertas": alertas, "totais": totais}
