"""Modelo de crescimento da vegetação -> ciclos de roçada.

Ideia (definida com o usuário em 2026-10-14): o ciclo é a frequência necessária
para a vegetação nunca passar da altura máxima do contrato.

    intervalo máximo entre passagens (dias) = (Hmax - H0) / taxa (cm/dia)
    ciclos no período                       = dias corridos do período / intervalo

Taxa de crescimento (gramíneas tropicais C4, por graus-dia):

    taxa = soma_espécies( cobertura x k x max(0, Tmédia - Tb) ) x f_água x fator_calibração

f_água vem do balanço hídrico mensal (Thornthwaite-Mather), desde 2026-10-15.

Ver retroanalises/proposta_modelo_crescimento.md (fontes e premissas).
"""
import gzip
import json
import math
import urllib.request
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

DIAS_MES = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

ALTURA_MAXIMA_OPCOES_CM = [30, 50]   # 30 cm é a grande maioria dos contratos (usuário, 2026-10-14)
ALTURA_POS_CORTE_PADRAO_CM = 4.0     # operacional: a roçadeira deixa 3-5 cm (usuário, 2026-10-14)

# Tb = temperatura-base (°C): abaixo dela a planta não cresce.
# k  = cm de altura por grau-dia acima de Tb.
# Literatura vem de pastagem irrigada/adubada -> na faixa de domínio o
# crescimento real tende a ser menor: por isso existe o fator de calibração.
ESPECIES = {
    "Braquiária decumbens (Urochloa decumbens)": {
        "tb": 15.4, "k": 0.070,
        "fonte": "Tb: Silva et al. 2012 (RBZ 41:574); k: estimativa (a validar)"},
    "Braquiarão Marandu (Urochloa brizantha)": {
        "tb": 10.5, "k": 0.059,
        "fonte": "Tb: Silva et al. 2012; k: Embrapa Gado de Leite 2011"},
    "Xaraés (Urochloa brizantha)": {
        "tb": 12.4, "k": 0.070,
        "fonte": "Tb: Silva et al. 2012; k: estimativa (a validar)"},
    "Colonião / Mombaça / Tanzânia (Megathyrsus maximus)": {
        "tb": 13.8, "k": 0.119,
        "fonte": "Tb: Silva et al. 2012 (média Mombaça 14,2 / Tanzânia 13,4); k: Embrapa Gado de Leite 2011"},
    "Capim-gordura (Melinis minutiflora)": {
        "tb": 12.0, "k": 0.060,
        "fonte": "estimativa (a validar)"},
    "Grama-estrela / bermuda (Cynodon)": {
        "tb": 15.1, "k": 0.040,
        "fonte": "Tb: Silva et al. 2012 (Tifton 85); k: estimativa (a validar) -- porte baixo"},
    "Grama-batatais / são-carlos (Paspalum, Axonopus)": {
        "tb": 12.0, "k": 0.030,
        "fonte": "estimativa (a validar) -- gramados de porte baixo"},
    "Vegetação mista / não identificada": {
        "tb": 12.0, "k": 0.065,
        "fonte": "estimativa (a validar) -- média das gramíneas acima"},
}
ESPECIE_PADRAO = "Vegetação mista / não identificada"

# Água que o solo consegue guardar para a planta (CAD, mm) no balanço hídrico:
# argiloso guarda mais e segura o crescimento no começo da seca; arenoso seca
# rápido. Estimativa (a validar) -- faixa usual de CAD para gramíneas.
SOLOS = {"Arenoso": 40, "Médio": 70, "Argiloso": 100}
SOLO_PADRAO = "Médio"

FONTE_CLIMA = ("NASA POWER, climatologia 2001-2025 (temperatura a 2 m e chuva corrigida), "
               "ponto da capital do estado (SP: Campinas) -- consulta feita em 2026-10-14/15")

# Clima mensal de referência por UF (ponto da capital; em SP, Campinas, porque a
# capital, a 760 m, é o ponto mais frio do estado e os contratos ficam no
# interior -- decisão do usuário, 2026-10-15). Para trechos longe do ponto de
# referência, use a opção de coordenada (consulta a NASA POWER na hora).
CLIMA_UF = {
    "AC": {"nome": "Acre", "referencia": "Rio Branco", "lat": -9.97, "lon": -67.81,
           "temp_c": [25.3, 25.1, 25.1, 24.9, 24.3, 24.1, 24.5, 26.3, 27.8, 27.8, 26.6, 25.5],
           "chuva_mm": [258, 255, 242, 160, 79, 33, 25, 43, 76, 131, 197, 239]},
    "AL": {"nome": "Alagoas", "referencia": "Maceió", "lat": -9.67, "lon": -35.74,
           "temp_c": [27.0, 27.2, 27.4, 27.2, 26.3, 25.2, 24.4, 24.2, 24.7, 25.6, 26.5, 27.0],
           "chuva_mm": [72, 68, 87, 123, 176, 204, 164, 105, 60, 45, 25, 29]},
    "AP": {"nome": "Amapá", "referencia": "Macapá", "lat": 0.03, "lon": -51.07,
           "temp_c": [26.4, 25.7, 25.7, 25.7, 25.8, 25.6, 25.7, 26.2, 27.1, 28.4, 28.9, 27.7],
           "chuva_mm": [206, 296, 290, 312, 263, 202, 160, 77, 40, 38, 46, 139]},
    "AM": {"nome": "Amazonas", "referencia": "Manaus", "lat": -3.12, "lon": -60.02,
           "temp_c": [26.5, 26.2, 26.2, 26.1, 26.2, 26.0, 26.3, 27.6, 28.9, 29.2, 28.4, 27.1],
           "chuva_mm": [224, 236, 268, 262, 205, 119, 76, 50, 68, 103, 135, 213]},
    "BA": {"nome": "Bahia", "referencia": "Salvador", "lat": -12.97, "lon": -38.5,
           "temp_c": [27.0, 27.1, 27.3, 26.6, 25.4, 24.3, 23.5, 23.4, 24.2, 25.4, 26.3, 26.9],
           "chuva_mm": [83, 87, 100, 147, 166, 138, 128, 96, 71, 69, 72, 57]},
    "CE": {"nome": "Ceará", "referencia": "Fortaleza", "lat": -3.73, "lon": -38.53,
           "temp_c": [27.5, 27.4, 27.3, 27.2, 27.2, 26.7, 26.4, 26.6, 27.0, 27.4, 27.7, 27.9],
           "chuva_mm": [128, 155, 223, 249, 145, 90, 44, 9, 3, 5, 7, 24]},
    "DF": {"nome": "Distrito Federal", "referencia": "Brasília", "lat": -15.79, "lon": -47.88,
           "temp_c": [22.4, 22.3, 22.1, 21.5, 20.2, 19.7, 20.2, 22.3, 24.9, 25.2, 23.2, 22.6],
           "chuva_mm": [209, 180, 197, 107, 25, 5, 2, 11, 32, 113, 200, 221]},
    "ES": {"nome": "Espírito Santo", "referencia": "Vitória", "lat": -20.32, "lon": -40.34,
           "temp_c": [24.1, 24.3, 24.1, 23.0, 21.0, 20.1, 19.6, 19.9, 21.0, 22.3, 22.7, 23.6],
           "chuva_mm": [140, 99, 138, 99, 76, 51, 47, 47, 50, 99, 200, 198]},
    "GO": {"nome": "Goiás", "referencia": "Goiânia", "lat": -16.68, "lon": -49.25,
           "temp_c": [23.3, 23.2, 23.1, 22.4, 20.6, 20.2, 20.9, 23.5, 26.3, 26.1, 24.2, 23.6],
           "chuva_mm": [239, 206, 209, 109, 24, 6, 3, 8, 44, 122, 194, 234]},
    "MA": {"nome": "Maranhão", "referencia": "São Luís", "lat": -2.53, "lon": -44.3,
           "temp_c": [27.1, 26.6, 26.4, 26.4, 26.7, 26.6, 26.6, 27.5, 28.0, 28.2, 28.3, 28.0],
           "chuva_mm": [191, 247, 322, 357, 238, 148, 88, 23, 23, 15, 16, 47]},
    "MT": {"nome": "Mato Grosso", "referencia": "Cuiabá", "lat": -15.6, "lon": -56.1,
           "temp_c": [26.6, 26.4, 26.4, 25.8, 24.1, 24.0, 24.6, 27.2, 29.5, 29.5, 28.1, 27.1],
           "chuva_mm": [218, 223, 187, 102, 48, 9, 11, 15, 34, 115, 169, 183]},
    "MS": {"nome": "Mato Grosso do Sul", "referencia": "Campo Grande", "lat": -20.47, "lon": -54.62,
           "temp_c": [25.1, 25.1, 24.8, 23.4, 20.1, 19.3, 19.4, 21.6, 24.2, 25.4, 25.3, 25.5],
           "chuva_mm": [197, 143, 129, 83, 85, 46, 32, 38, 75, 128, 149, 175]},
    "MG": {"nome": "Minas Gerais", "referencia": "Belo Horizonte", "lat": -19.92, "lon": -43.94,
           "temp_c": [21.6, 21.4, 21.1, 20.1, 18.4, 17.6, 17.6, 18.9, 21.0, 22.3, 21.5, 21.5],
           "chuva_mm": [223, 132, 153, 53, 27, 11, 7, 18, 42, 88, 190, 266]},
    "PR": {"nome": "Paraná", "referencia": "Curitiba", "lat": -25.43, "lon": -49.27,
           "temp_c": [21.4, 21.4, 20.6, 18.7, 15.3, 14.0, 13.6, 14.8, 16.5, 18.3, 19.2, 20.9],
           "chuva_mm": [221, 192, 148, 102, 104, 106, 97, 77, 122, 148, 141, 173]},
    "PB": {"nome": "Paraíba", "referencia": "João Pessoa", "lat": -7.12, "lon": -34.86,
           "temp_c": [27.5, 27.6, 27.6, 27.2, 26.4, 25.3, 24.5, 24.5, 25.3, 26.4, 27.2, 27.6],
           "chuva_mm": [86, 96, 127, 169, 173, 233, 170, 95, 46, 25, 18, 30]},
    "PA": {"nome": "Pará", "referencia": "Belém", "lat": -1.46, "lon": -48.5,
           "temp_c": [26.2, 25.9, 25.9, 26.0, 26.3, 26.4, 26.4, 27.3, 28.5, 28.8, 28.8, 27.6],
           "chuva_mm": [311, 369, 411, 383, 275, 171, 119, 93, 75, 79, 94, 188]},
    "PE": {"nome": "Pernambuco", "referencia": "Recife", "lat": -8.05, "lon": -34.88,
           "temp_c": [27.1, 27.3, 27.4, 27.0, 26.2, 25.1, 24.3, 24.1, 24.7, 25.8, 26.6, 27.1],
           "chuva_mm": [85, 94, 124, 170, 203, 261, 206, 115, 58, 36, 24, 38]},
    "PI": {"nome": "Piauí", "referencia": "Teresina", "lat": -5.09, "lon": -42.8,
           "temp_c": [27.4, 26.3, 26.1, 25.9, 26.3, 26.9, 27.8, 29.2, 30.7, 31.3, 30.8, 29.6],
           "chuva_mm": [184, 227, 261, 239, 106, 24, 11, 7, 7, 21, 39, 77]},
    "RN": {"nome": "Rio Grande do Norte", "referencia": "Natal", "lat": -5.79, "lon": -35.21,
           "temp_c": [27.4, 27.7, 27.9, 27.8, 27.5, 26.7, 26.0, 25.8, 26.0, 26.5, 27.0, 27.3],
           "chuva_mm": [85, 95, 142, 180, 157, 209, 145, 63, 32, 19, 16, 26]},
    "RS": {"nome": "Rio Grande do Sul", "referencia": "Porto Alegre", "lat": -30.03, "lon": -51.23,
           "temp_c": [24.5, 24.6, 23.2, 20.5, 16.6, 14.5, 13.6, 15.1, 16.6, 19.1, 20.8, 23.0],
           "chuva_mm": [120, 103, 103, 98, 112, 113, 149, 116, 157, 155, 110, 110]},
    "RJ": {"nome": "Rio de Janeiro", "referencia": "Rio de Janeiro", "lat": -22.91, "lon": -43.17,
           "temp_c": [25.7, 25.8, 25.4, 24.3, 22.3, 21.5, 20.9, 21.2, 22.0, 22.9, 23.4, 24.7],
           "chuva_mm": [208, 152, 173, 100, 71, 49, 45, 42, 69, 108, 220, 232]},
    "RO": {"nome": "Rondônia", "referencia": "Porto Velho", "lat": -8.76, "lon": -63.9,
           "temp_c": [25.6, 25.6, 25.6, 25.6, 25.3, 25.4, 26.4, 28.3, 29.0, 28.2, 27.2, 26.1],
           "chuva_mm": [254, 241, 228, 172, 94, 32, 20, 39, 82, 147, 154, 246]},
    "RR": {"nome": "Roraima", "referencia": "Boa Vista", "lat": 2.82, "lon": -60.67,
           "temp_c": [29.4, 30.0, 30.4, 29.0, 26.9, 26.1, 25.9, 26.5, 27.3, 28.1, 28.6, 28.7],
           "chuva_mm": [28, 27, 39, 127, 278, 280, 253, 178, 84, 68, 56, 52]},
    "SC": {"nome": "Santa Catarina", "referencia": "Florianópolis", "lat": -27.6, "lon": -48.55,
           "temp_c": [24.4, 24.6, 23.7, 21.7, 18.5, 16.8, 15.9, 16.6, 17.8, 19.7, 21.2, 23.2],
           "chuva_mm": [189, 146, 141, 101, 114, 96, 96, 103, 152, 144, 134, 153]},
    "SE": {"nome": "Sergipe", "referencia": "Aracaju", "lat": -10.91, "lon": -37.07,
           "temp_c": [27.1, 27.4, 27.6, 27.5, 26.7, 25.8, 24.9, 24.7, 25.1, 25.9, 26.5, 26.9],
           "chuva_mm": [56, 58, 74, 116, 191, 158, 144, 89, 58, 47, 27, 24]},
    "SP": {"nome": "São Paulo", "referencia": "Campinas", "lat": -22.91, "lon": -47.06,
           "temp_c": [22.8, 22.9, 22.1, 20.6, 17.8, 17.0, 16.8, 18.4, 20.7, 22.2, 22.1, 22.8],
           "chuva_mm": [243, 169, 134, 74, 62, 46, 47, 30, 59, 105, 157, 186]},
    "TO": {"nome": "Tocantins", "referencia": "Palmas", "lat": -10.18, "lon": -48.33,
           "temp_c": [25.7, 25.4, 25.6, 25.6, 25.4, 24.7, 25.3, 27.3, 29.4, 29.1, 27.2, 26.3],
           "chuva_mm": [268, 225, 248, 158, 55, 7, 1, 3, 38, 109, 185, 214]},
}


_DIA_DO_ANO_MEIO_MES = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]


def evapotranspiracao_potencial(temps: list[float], lat: float) -> list[float]:
    """ETP mensal (mm) por Thornthwaite (1948), corrigida pela duração do dia e
    do mês; acima de 26,5 °C usa a equação de Willmott/Camargo. Só precisa de
    temperatura e latitude -- funciona offline."""
    indice = sum((t / 5) ** 1.514 for t in temps if t > 0)
    if indice <= 0:
        return [0.0] * 12
    a = 6.75e-7 * indice ** 3 - 7.71e-5 * indice ** 2 + 1.792e-2 * indice + 0.49239
    etp = []
    for i, t in enumerate(temps):
        if t <= 0:
            padrao = 0.0
        elif t < 26.5:
            padrao = 16 * (10 * t / indice) ** a
        else:
            padrao = -415.85 + 32.24 * t - 0.43 * t * t
        declinacao = math.radians(23.45 * math.sin(math.radians(360 * (284 + _DIA_DO_ANO_MEIO_MES[i]) / 365)))
        x = -math.tan(math.radians(lat)) * math.tan(declinacao)
        horas_luz = 24 / math.pi * math.acos(max(-1.0, min(1.0, x)))
        etp.append(padrao * (horas_luz / 12) * (DIAS_MES[i] / 30))
    return etp


def fator_agua_mensal(clima: dict, solo: str = SOLO_PADRAO) -> list[float]:
    """Fração do crescimento que a água permite em cada mês (0-1), pelo balanço
    hídrico climatológico de Thornthwaite-Mather (1955): ETR ÷ ETP.

    O solo funciona como uma caixa d'água (CAD, mm): chuva acima da demanda enche
    a caixa; na seca a planta vai gastando o que sobrou. Por isso o 1º mês de chuva
    depois de uma seca longa ainda é limitado (a caixa está vazia) e o 1º mês seco
    ainda cresce (a caixa está cheia) -- o fator antigo (chuva ÷ 100 mm, com piso)
    não tinha essa memória e fazia, p. ex., outubro de Goiânia virar o mês de maior
    crescimento do ano (auditoria de 2026-10-15)."""
    cad = SOLOS.get(solo, SOLOS[SOLO_PADRAO])
    chuva = clima["chuva_mm"]
    etp = evapotranspiracao_potencial(clima["temp_c"], clima.get("lat", -15.0))
    armazenado, fatores = float(cad), [1.0] * 12
    for _ in range(4):  # repete o ano até o armazenamento estabilizar (regime permanente)
        for i in range(12):
            if etp[i] <= 0:
                fatores[i] = 1.0
                continue
            if chuva[i] >= etp[i]:
                armazenado = min(cad, armazenado + chuva[i] - etp[i])
                etr = etp[i]
            else:
                novo = armazenado * math.exp(-(etp[i] - chuva[i]) / cad)
                etr = chuva[i] + (armazenado - novo)
                armazenado = novo
            fatores[i] = min(1.0, etr / etp[i])
    return fatores


def taxa_mensal(clima: dict, composicao: dict, solo: str = SOLO_PADRAO, calibracao: float = 1.0) -> list[float]:
    """Crescimento em cm/dia para cada mês. `composicao` = {espécie: % cobertura};
    a mistura é a média ponderada pela cobertura (decisão do usuário, 2026-10-14)."""
    total = sum(v for v in composicao.values() if v > 0)
    if total <= 0:
        composicao, total = {ESPECIE_PADRAO: 100}, 100
    taxas = []
    for temp, agua in zip(clima["temp_c"], fator_agua_mensal(clima, solo)):
        termico = sum(
            (pct / total) * ESPECIES[esp]["k"] * max(0.0, temp - ESPECIES[esp]["tb"])
            for esp, pct in composicao.items() if pct > 0
        )
        taxas.append(termico * agua * calibracao)
    return taxas


def memoria_taxa(clima: dict, composicao: dict, solo: str, calibracao: float, mes: int) -> dict:
    """Passo a passo do crescimento (cm/dia) de um mês -- mesma conta de
    taxa_mensal(), aberta para exibir na tela e no Excel."""
    total = sum(v for v in composicao.values() if v > 0)
    if total <= 0:
        composicao, total = {ESPECIE_PADRAO: 100}, 100
    temp = clima["temp_c"][mes]
    especies = []
    for esp, pct in composicao.items():
        if pct <= 0:
            continue
        e = ESPECIES[esp]
        graus = max(0.0, temp - e["tb"])
        especies.append({"especie": esp, "peso": pct / total, "k": e["k"], "tb": e["tb"],
                         "graus_dia": graus, "contribuicao": (pct / total) * e["k"] * graus})
    termico = sum(x["contribuicao"] for x in especies)
    agua = fator_agua_mensal(clima, solo)[mes]
    return {"mes": mes, "temp": temp, "especies": especies, "termico": termico, "agua": agua,
            "calibracao": calibracao, "taxa": termico * agua * calibracao}


def meses_crescimento_alto(taxas: list[float], n_meses: int = 6) -> list[int]:
    """Índices (0-11) do "período de chuva" do dimensionamento: os `n_meses`
    CONSECUTIVOS (podendo virar o ano, ex.: out a mar) com o maior crescimento
    somado. Padrão 6 + 6, a divisão usada na prática (usuário, 2026-10-20); antes
    eram os meses acima da média anual, o que dava 7 + 5 em SP e de 5 a 9 meses
    conforme o estado. No Sul, onde chove o ano todo, quem separa os períodos é o
    frio do inverno; por isso a divisão é pela taxa de crescimento e não só pela
    chuva."""
    n_meses = max(1, min(11, int(n_meses)))
    inicio = max(range(12), key=lambda s: (sum(taxas[(s + k) % 12] for k in range(n_meses)), -s))
    return sorted((inicio + k) % 12 for k in range(n_meses))


def ciclos_periodo(taxas: list[float], meses: list[int], h_max: float, h0: float, criterio: str = "critico") -> dict:
    """Ciclos necessários num período (lista de meses).

    criterio "critico": usa o mês de maior crescimento do período -- garante que
    a equipe dimensionada não deixe trechos passarem da altura nem no pior mês.
    criterio "media": usa a média do período (dimensiona menos, mas o mês de pico
    pode estourar a altura)."""
    if not meses or h_max <= h0:
        return {"ciclos": 0.0, "intervalo_dias": None, "taxa": 0.0, "dias": 0.0}
    dias = sum(DIAS_MES[i] for i in meses)
    if criterio == "critico":
        taxa = max(taxas[i] for i in meses)
    else:
        taxa = sum(taxas[i] * DIAS_MES[i] for i in meses) / dias
    if taxa <= 0:
        return {"ciclos": 0.0, "intervalo_dias": None, "taxa": 0.0, "dias": dias}
    intervalo = (h_max - h0) / taxa
    return {"ciclos": dias / intervalo, "intervalo_dias": intervalo, "taxa": taxa, "dias": dias}


def crescimento_acumulado(taxas: list[float], mes: int, dias: float) -> float:
    """Crescimento (cm) previsto nos `dias` anteriores a uma medição feita no meio do
    mês `mes`, somando dia a dia a taxa de cada mês percorrido para trás."""
    total, m, resto = 0.0, mes, DIAS_MES[mes] / 2
    while dias > 0:
        passo = min(dias, resto)
        total += taxas[m] * passo
        dias -= passo
        m = (m - 1) % 12
        resto = DIAS_MES[m]
    return total


def memoria_calibracao(observacoes: list[dict], clima: dict | None, composicao: dict, solo: str, h0: float,
                       base: list[float] | None = None) -> list[dict]:
    """Uma linha por medição válida: crescimento medido (altura − pós-corte),
    crescimento que o modelo (sem calibração) prevê para os mesmos dias e a razão.
    `base` = crescimento médio de cada mês sem calibração (modelo v2); sem ela, usa o v1."""
    if base is None:
        base = taxa_mensal(clima, composicao, solo, 1.0)
    linhas = []
    for ob in observacoes:
        try:
            mes, dias, altura = int(ob["mes"]), float(ob["dias"]), float(ob["altura_cm"])
        except (KeyError, TypeError, ValueError):
            continue
        if dias <= 0 or altura <= h0:
            continue
        previsto = crescimento_acumulado(base, mes, dias)
        if previsto <= 0:
            continue
        linhas.append({"mes": mes, "dias": dias, "altura": altura, "medido": altura - h0,
                       "previsto": previsto, "razao": (altura - h0) / previsto})
    return linhas


def fator_calibracao(observacoes: list[dict], clima: dict | None, composicao: dict, solo: str, h0: float,
                     base: list[float] | None = None) -> float | None:
    """Ajusta o modelo ao campo. Cada observação: {"mes": 0-11, "dias": dias desde a
    última roçada, "altura_cm": altura medida hoje}. Fator = média(crescimento medido ÷
    crescimento do modelo nos mesmos dias) -- uma medição de novembro com 60 dias
    cobre também setembro e outubro (item 44 do backlog)."""
    linhas = memoria_calibracao(observacoes, clima, composicao, solo, h0, base)
    return sum(x["razao"] for x in linhas) / len(linhas) if linhas else None


def buscar_clima_coordenada(lat: float, lon: float, timeout: int = 30) -> dict:
    """Clima mensal (climatologia) de um ponto via NASA POWER -- gratuita, sem
    chave. Envia só latitude/longitude. Levanta exceção se a rede bloquear."""
    url = ("https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=T2M,PRECTOTCORR"
           f"&community=ag&longitude={lon:.4f}&latitude={lat:.4f}&format=json")
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        dados = json.load(resp)["properties"]["parameter"]
    chaves = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    return {
        "referencia": f"coordenada {lat:.4f}, {lon:.4f}", "lat": lat, "lon": lon,
        "fonte": "NASA POWER, climatologia 2001-2025 do ponto informado (consulta ao vivo)",
        "temp_c": [round(dados["T2M"][m], 1) for m in chaves],
        "chuva_mm": [round(dados["PRECTOTCORR"][m] * DIAS_MES[i]) for i, m in enumerate(chaves)],
    }


# =============================================================================
# Modelo v2 (2026-10-20): diário, com 14 anos de dados. Ver
# retroanalises/proposta_modelo_crescimento_v2.md. O v1 (mensal, acima) fica para
# comparação. O que muda: graus-dia com mínima e máxima do dia (Ometto, 1981);
# balanço hídrico DIÁRIO com evaporação de Hargreaves-Samani (FAO-56), que enxerga
# a seca do inverno (com Thornthwaite, SP ficava com 100% de água em julho); pico de
# 30 dias em vez do mês médio; ano típico ou exigente (P80); vários pontos de clima
# combinados pela área que cada um representa; períodos escolhidos pela demanda.
# Conta só o crescimento da vegetação: nenhuma margem operacional (usuário, 2026-10-20).
# =============================================================================
ARQUIVO_SERIE = Path(__file__).resolve().parent.parent / "dados_clima" / "nasa_power_diario_2011_2024.json.gz"
TB_SUPERIOR = 38.0        # °C: acima disso o crescimento das gramíneas C4 cai
JANELA_PICO_DIAS = 30     # janela da média móvel que define o pico de cada mês
PERCENTIL_EXIGENTE = 0.8  # "ano exigente": percentil 80 entre os anos
ANOS_AQUECIMENTO = 1      # o 1º ano da série só aquece o balanço hídrico (fica fora das médias)


@lru_cache(maxsize=1)
def _series_embutidas() -> dict:
    with gzip.open(ARQUIVO_SERIE, "rt", encoding="utf-8") as f:
        return json.load(f)


def serie_uf(uf: str) -> dict:
    """Série diária 2011-2024 do ponto de referência da UF (embutida no app, offline)."""
    dados = _series_embutidas()
    s, ref = dados["ufs"][uf], CLIMA_UF[uf]
    return {"referencia": f"{ref['nome']} ({uf}) — {ref['referencia']}", "lat": ref["lat"], "lon": ref["lon"],
            "inicio": dados["inicio"], "tmin": s["tmin"], "tmax": s["tmax"], "chuva": s["chuva"],
            "fonte": dados["fonte"]}


def buscar_serie_coordenada(lat: float, lon: float, timeout: int = 120) -> dict:
    """Série diária 2011-2024 de um ponto via NASA POWER (gratuita, sem chave; envia só
    latitude e longitude). Levanta exceção se a rede bloquear."""
    url = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M_MIN,T2M_MAX,PRECTOTCORR"
           f"&community=ag&longitude={lon:.4f}&latitude={lat:.4f}&start=20110101&end=20241231&format=json")
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        dados = json.load(resp)["properties"]["parameter"]
    dias = sorted(dados["T2M_MIN"])
    saida = {}
    for chave, nome in (("T2M_MIN", "tmin"), ("T2M_MAX", "tmax"), ("PRECTOTCORR", "chuva")):
        valores, anterior = [], 0.0
        for d in dias:
            v = dados[chave][d]
            if v is None or v <= -900:  # dia sem dado: repete o anterior
                v = anterior
            valores.append(round(v, 1))
            anterior = v
        saida[nome] = valores
    return {"referencia": f"coordenada {lat:.4f}, {lon:.4f}", "lat": lat, "lon": lon, "inicio": dias[0],
            "fonte": "NASA POWER, dados diários 2011-2024 do ponto informado (consulta ao vivo)", **saida}


def graus_dia_ometto(tmin: float, tmax: float, tb: float, tb_sup: float = TB_SUPERIOR) -> float:
    """Graus-dia de um dia pelo método de Ometto (1981), com a mínima e a máxima: conta
    as horas acima da temperatura-base mesmo em dia de madrugada fria.
    Tmín >= Tb: média − Tb; Tmín < Tb < Tmáx: (Tmáx − Tb)² ÷ (2 (Tmáx − Tmín)); Tmáx <= Tb: 0.
    Acima da base superior (38 °C), desconta a parte que passa dela."""
    if tmax <= tb:
        return 0.0
    if tmin >= tb:
        gd = (tmax + tmin) / 2 - tb
    else:
        gd = (tmax - tb) ** 2 / (2 * (tmax - tmin))
    if tmax > tb_sup:
        gd -= (tmax - tb_sup) ** 2 / (2 * max(tmax - tmin, 0.1))
    return max(0.0, gd)


def etp_hargreaves(tmin: float, tmax: float, lat: float, dia_do_ano: int) -> float:
    """Evaporação potencial do dia (mm) por Hargreaves-Samani (FAO-56, eq. 52): usa a
    máxima, a mínima e a radiação no topo da atmosfera (latitude e data)."""
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * dia_do_ano / 365)
    dec = 0.409 * math.sin(2 * math.pi * dia_do_ano / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(dec))))
    ra = 24 * 60 / math.pi * 0.0820 * dr * (ws * math.sin(phi) * math.sin(dec)
                                            + math.cos(phi) * math.cos(dec) * math.sin(ws))
    tmed = (tmin + tmax) / 2
    return max(0.0, 0.0023 * 0.408 * ra * (tmed + 17.8) * math.sqrt(max(tmax - tmin, 0.0)))


def _normalizar(composicao: dict) -> dict:
    total = sum(v for v in composicao.values() if v > 0)
    if total <= 0:
        return {ESPECIE_PADRAO: 1.0}
    return {e: v / total for e, v in composicao.items() if v > 0}


def _data_inicio(serie: dict) -> date:
    s = str(serie["inicio"])
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def crescimento_diario(serie: dict, composicao: dict, solo: str = SOLO_PADRAO) -> dict:
    """Crescimento (cm/dia, sem calibração) de cada dia da série:
    Σ espécies[ cobertura × k × graus-dia de Ometto ] × água disponível do dia.
    Água disponível = evaporação real ÷ potencial no balanço hídrico diário: o solo
    guarda até a sua capacidade; sem chuva, a planta gasta o que sobrou."""
    pesos = _normalizar(composicao)
    cad = SOLOS.get(solo, SOLOS[SOLO_PADRAO])
    inicio = _data_inicio(serie)
    datas, taxa, termico, agua = [], [], [], []
    gd = {e: [] for e in pesos}
    armazenado = float(cad)
    for i, (tmin, tmax, chuva) in enumerate(zip(serie["tmin"], serie["tmax"], serie["chuva"])):
        dia = inicio + timedelta(days=i)
        etp = etp_hargreaves(tmin, tmax, serie["lat"], dia.timetuple().tm_yday)
        if chuva >= etp:
            armazenado = min(cad, armazenado + chuva - etp)
            etr = etp
        else:
            novo = armazenado * math.exp(-(etp - chuva) / cad)
            etr = chuva + (armazenado - novo)
            armazenado = novo
        f_agua = min(1.0, etr / etp) if etp > 0 else 1.0
        t = 0.0
        for e, p in pesos.items():
            g = graus_dia_ometto(tmin, tmax, ESPECIES[e]["tb"])
            gd[e].append(g)
            t += p * ESPECIES[e]["k"] * g
        datas.append(dia)
        termico.append(t)
        agua.append(f_agua)
        taxa.append(t * f_agua)
    return {"datas": datas, "taxa": taxa, "termico": termico, "agua": agua, "gd": gd, "pesos": pesos}


def combinar(pontos: list[tuple[float, dict]]) -> dict:
    """Combina vários pontos de clima numa curva única, DIA A DIA, ponderada pela área
    (ou extensão) que cada ponto representa. É a demanda total da concessão quando as
    equipes atendem a concessão inteira: o pico combinado sai menor ou igual à média
    dos picos, porque regiões diferentes não chegam ao pico no mesmo dia. (Se cada
    região tem equipe própria, dimensione cada uma separada.)"""
    pontos = [(p, c) for p, c in pontos if p > 0]
    if len(pontos) == 1:
        return pontos[0][1]
    total = sum(p for p, _ in pontos)
    n = min(len(c["taxa"]) for _, c in pontos)
    w = [(p / total, c) for p, c in pontos]

    def soma(serie_de):
        return [sum(f * serie_de(c)[i] for f, c in w) for i in range(n)]

    especies = w[0][1]["pesos"]
    return {"datas": w[0][1]["datas"][:n], "taxa": soma(lambda c: c["taxa"]),
            "termico": soma(lambda c: c["termico"]), "agua": soma(lambda c: c["agua"]),
            "gd": {e: soma(lambda c, e=e: c["gd"][e]) for e in especies}, "pesos": especies}


def _media_movel_centrada(valores: list[float], janela: int) -> list[float]:
    acum = [0.0]
    for v in valores:
        acum.append(acum[-1] + v)
    meio, n, saida = janela // 2, len(valores), []
    for i in range(n):
        a, b = max(0, i - meio), min(n, i - meio + janela)
        saida.append((acum[b] - acum[a]) / (b - a))
    return saida


def _percentil(valores: list[float], q: float) -> float:
    v = sorted(valores)
    pos = q * (len(v) - 1)
    baixo = int(pos)
    alto = min(baixo + 1, len(v) - 1)
    return v[baixo] + (v[alto] - v[baixo]) * (pos - baixo)


def resumo_mensal(cresc: dict, janela: int = JANELA_PICO_DIAS) -> dict:
    """Por mês (0-11), sem calibração:
    media / media_p80 -- crescimento médio do mês (cm/dia): média dos anos (ano típico)
                         e percentil 80 entre os anos (ano exigente);
    pico / pico_p80   -- maior média móvel de 30 dias dentro do mês, idem;
    termico, agua, gd -- médias do mês, para a memória de cálculo.
    É o pico de 30 dias que dimensiona: um veranico de 3 dias não muda a equipe, um mês
    inteiro de crescimento forte muda."""
    movel = _media_movel_centrada(cresc["taxa"], janela)
    ano0 = cresc["datas"][0].year + ANOS_AQUECIMENTO
    grupos: dict = {}
    for i, d in enumerate(cresc["datas"]):
        if d.year >= ano0:
            grupos.setdefault((d.year, d.month - 1), []).append(i)
    anos = sorted({a for a, _ in grupos})
    r = {k: [] for k in ("media", "media_p80", "pico", "pico_p80", "termico", "agua")}
    r["gd"] = {e: [] for e in cresc["gd"]}
    for m in range(12):
        gs = [grupos[(a, m)] for a in anos if (a, m) in grupos]
        medias = [sum(cresc["taxa"][i] for i in g) / len(g) for g in gs]
        picos = [max(movel[i] for i in g) for g in gs]
        dias_m = [i for g in gs for i in g]
        r["media"].append(sum(medias) / len(medias))
        r["media_p80"].append(_percentil(medias, PERCENTIL_EXIGENTE))
        r["pico"].append(sum(picos) / len(picos))
        r["pico_p80"].append(_percentil(picos, PERCENTIL_EXIGENTE))
        r["termico"].append(sum(cresc["termico"][i] for i in dias_m) / len(dias_m))
        r["agua"].append(sum(cresc["agua"][i] for i in dias_m) / len(dias_m))
        for e in r["gd"]:
            r["gd"][e].append(sum(cresc["gd"][e][i] for i in dias_m) / len(dias_m))
    r["anos"] = (anos[0], anos[-1])
    r["pesos"] = cresc["pesos"]
    return r


def clima_mensal(serie: dict) -> dict:
    """Médias mensais da série (mínima, máxima, chuva do mês), só para exibir."""
    inicio = _data_inicio(serie)
    soma = {m: {"tmin": 0.0, "tmax": 0.0, "n": 0, "chuva": 0.0} for m in range(12)}
    anos = set()
    for i, (tmin, tmax, chuva) in enumerate(zip(serie["tmin"], serie["tmax"], serie["chuva"])):
        d = inicio + timedelta(days=i)
        s = soma[d.month - 1]
        s["tmin"] += tmin
        s["tmax"] += tmax
        s["chuva"] += chuva
        s["n"] += 1
        anos.add(d.year)
    return {"tmin": [soma[m]["tmin"] / soma[m]["n"] for m in range(12)],
            "tmax": [soma[m]["tmax"] / soma[m]["n"] for m in range(12)],
            "chuva_mm": [soma[m]["chuva"] / len(anos) for m in range(12)]}


def custo_divisao(taxas: list[float], alto: list[int]) -> float:
    """Equipes × dias (relativo) de uma divisão em 2 períodos, cada um com equipe
    dimensionada pelo seu mês de maior demanda."""
    baixo = [i for i in range(12) if i not in alto]
    return sum(max(taxas[i] for i in idx) * sum(DIAS_MES[i] for i in idx) for idx in (alto, baixo) if idx)


def _blocos(n_meses: int) -> list[list[int]]:
    return [sorted((s + k) % 12 for k in range(n_meses)) for s in range(12)]


def _eh_periodo_alto(taxas: list[float], bloco: list[int]) -> bool:
    resto = [i for i in range(12) if i not in bloco]
    return max(taxas[i] for i in bloco) >= max(taxas[i] for i in resto)


def escolher_periodos(taxas: list[float], n_meses: int = 6) -> list[int]:
    """Meses (0-11) do período de chuva: os `n_meses` consecutivos que, com o resto do
    ano como seca, exigem MENOS equipe (cada período dimensionado pelo seu pico).
    Não são "os meses de maior crescimento somado": o solo demora a recarregar
    (outubro ainda é lento em SP) e segura água no fim das águas (abril ainda é
    rápido). Pela soma, abril ia para a seca e a seca saía quase igual à chuva."""
    n_meses = max(1, min(11, int(n_meses)))
    candidatos = [b for b in _blocos(n_meses) if _eh_periodo_alto(taxas, b)] or _blocos(n_meses)
    return min(candidatos, key=lambda b: (round(custo_divisao(taxas, b), 9), -sum(taxas[i] for i in b)))


def divisao_otima_livre(taxas: list[float]) -> list[int]:
    """Período de chuva da divisão em 2 blocos contíguos, de qualquer duração (2 a 10
    meses), que exige menos equipe. Só informativa: o contrato usa 6 + 6."""
    melhor = min((b for n in range(2, 11) for b in _blocos(n)), key=lambda b: (round(custo_divisao(taxas, b), 9), len(b)))
    return melhor if _eh_periodo_alto(taxas, melhor) else [i for i in range(12) if i not in melhor]


def rotulo_meses(idx: list[int]) -> str:
    """'Nov–Abr' para um bloco contíguo (que pode virar o ano)."""
    if not idx:
        return "—"
    inicio = [i for i in idx if (i - 1) % 12 not in idx]
    if len(inicio) != 1:
        return ", ".join(MESES[i] for i in sorted(idx))
    return f"{MESES[inicio[0]]}–{MESES[(inicio[0] + len(idx) - 1) % 12]}"
