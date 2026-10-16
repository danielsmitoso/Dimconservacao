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
import json
import math
import urllib.request

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


def meses_crescimento_alto(taxas: list[float]) -> list[int]:
    """Índices (0-11) dos meses com crescimento acima da média anual -- é o
    "período de chuva" do dimensionamento. No Sul, onde chove o ano todo, quem
    separa os períodos é o frio do inverno; por isso a divisão é pela taxa de
    crescimento e não só pela chuva."""
    media = sum(taxas) / 12
    altos = [i for i, t in enumerate(taxas) if t >= media]
    return altos if 0 < len(altos) < 12 else list(range(6))


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


def fator_calibracao(observacoes: list[dict], clima: dict, composicao: dict, solo: str, h0: float) -> float | None:
    """Ajusta o modelo ao campo. Cada observação: {"mes": 0-11, "dias": dias desde a
    última roçada, "altura_cm": altura medida hoje}. Fator = média(crescimento medido ÷
    crescimento do modelo nos mesmos dias) -- uma medição de novembro com 60 dias
    cobre também setembro e outubro (item 44 do backlog)."""
    base = taxa_mensal(clima, composicao, solo, 1.0)
    razoes = []
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
        razoes.append((altura - h0) / previsto)
    return sum(razoes) / len(razoes) if razoes else None


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
