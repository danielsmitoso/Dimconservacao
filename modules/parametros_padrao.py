"""Valores-padrao (editaveis na interface) para produtividade, ciclos e metas.

IMPORTANTE: nem todo valor aqui tem lastro em dado de campo real. Cada item
tem uma tag `fonte`:
  - "referencia" = veio de estudo/contrato real anterior (SPVias, RioSP FS4.0,
    AutoBAn) e esta documentado.
  - "estimativa" = numero de mercado generico, SEM validacao de campo. Precisa
    ser confirmado com o time tecnico (ex: Marcos) antes de usar com dados
    reais de contrato -- ver retroanalises/perguntas_pendentes.md.
"""

# --- Rocada manual -----------------------------------------------------
ROCADA_MANUAL = {
    "produtividade_dia_padrao_m2": 2000,   # colaborador, administracao padrao
    "produtividade_dia_metas_m2": 3500,    # colaborador, contrato c/ metas de performance
    "fonte": "referencia (SPVias slide de produtividade, aditivo de modalidade)",
}

# Composicao tipica de uma equipe de rocada manual: nem todo mundo na equipe
# faz rocada (tem motorista e apoio para outras atividades) -- usado para
# converter "colaboradores necessarios" em "quantas equipes" e propor a
# divisao de trechos por equipe.
COMPOSICAO_EQUIPE_ROCADA_MANUAL = {
    "total_colaboradores": 9,
    "rocadores_ativos": 6,
    "fonte": "referencia (composicao informada pelo usuario em 2026-09-18)",
}

# --- Rocada mecanizada, por tipo de equipamento -------------------------
# Os nomes seguem a coluna "Equipamento" do export Quasar (que indica, por
# poligono, qual equipamento a analise por satelite considera adequado).
# Produtividade = m2/dia por unidade do equipamento (ESTIMATIVA a validar com
# dado de campo -- ver retroanalises/perguntas_pendentes.md item 1).
# `indicacao` resume, em linguagem de campo, onde cada equipamento rende mais:
# e usada para explicar a recomendacao por trecho.
ROCADA_MECANIZADA = {
    "Trator 4.7m": {
        "produtividade_dia_m2": 40000, "fonte": "estimativa",
        "indicacao": "grandes áreas abertas e planas (canteiro central largo, sem obstáculos): maior rendimento por dia",
    },
    "Trator 1.7m": {
        "produtividade_dia_m2": 20000, "fonte": "estimativa",
        "indicacao": "canteiros mais estreitos, onde o Trator 4.7m não entra: equipamento 'coringa' da frota",
    },
    "Trator com braço articulado": {
        "produtividade_dia_m2": 9000, "fonte": "estimativa",
        "indicacao": "taludes inclinados, áreas atrás de defensa/dispositivos e locais de difícil alcance: rende menos, mas acessa o que o trator convencional não alcança",
    },
    "Eixo-zero": {
        "produtividade_dia_m2": 30000, "fonte": "estimativa",
        "indicacao": "áreas planas com muitos obstáculos e curvas (placas, postes, bueiros): manobra fechada sem perder rendimento",
    },
    "Spider": {
        "produtividade_dia_m2": 5000, "fonte": "estimativa",
        "indicacao": "encostas muito íngremes ou bloqueadas fisicamente (ex: atrás de defensa): operação remota, baixo rendimento, mas único que atende esses pontos com segurança",
    },
    "Robô": {
        "produtividade_dia_m2": 12000, "fonte": "estimativa",
        "indicacao": "áreas inclinadas ou de difícil acesso, operado remotamente sem colocar operador em risco; não vem do Quasar",
    },
}

# Nome usado quando o inventario tem area mecanizada mas nenhum equipamento
# indicado (ex: planilha preenchida a mao, sem a coluna de equipamento).
EQUIPAMENTO_PADRAO_SEM_INDICACAO = "Trator 1.7m"
PRODUTIVIDADE_EQUIPAMENTO_DESCONHECIDO = 15000


def canonizar_equipamento(texto: str) -> str:
    """Normaliza o nome de um equipamento vindo de planilha (caixa, acento,
    'Giro Zero' x 'Eixo-zero') para o nome do catalogo acima. Nomes que nao
    estao no catalogo sao devolvidos como vieram (com a 1a letra maiuscula)."""
    import unicodedata
    bruto = str(texto).strip()
    chave = unicodedata.normalize("NFKD", bruto).encode("ascii", "ignore").decode("ascii").lower()
    chave = chave.replace("giro zero", "eixo-zero").replace("eixo zero", "eixo-zero")
    for nome in ROCADA_MECANIZADA:
        nome_chave = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
        if chave == nome_chave:
            return nome
    return bruto[:1].upper() + bruto[1:] if bruto else bruto


# Poligono/trecho em que mais de um equipamento pode trabalhar (ex: Quasar
# "Trator 1.7m, Spider"): o nome combinado usa este separador. As indicacoes
# sao ALTERNATIVAS independentes (cada um poderia fazer a area), nao uma divisao
# da area entre eles -- quem faz e decidido na alocacao da frota
# (mecanizacao.alocar_frota). Decisao do usuario, 2026-10-16.
SEPARADOR_ALTERNATIVAS = " ou "


# Quem pode fazer area indicada para outro equipamento (executor -> indicados
# que ele atende). Regra do usuario (2026-10-16): a restricao e sempre de
# TAMANHO e ACESSO -- o menor entra onde o maior entra (Trator 1.7m faz area de
# Trator 4.7m; Eixo-zero, menor que o 1.7m, faz as duas), e o braco articulado
# faz area de Spider se alcancar. Editavel na aba Rocada Mecanizada.
SUBSTITUICOES_PADRAO = {
    "Trator 1.7m": ["Trator 4.7m"],
    "Eixo-zero": ["Trator 1.7m", "Trator 4.7m"],
    "Trator com braço articulado": ["Spider"],
}

# Regra de reclassificacao do Quasar (pergunta 32, 2026-10-16): canteiro com
# largura acima deste valor e sem bloqueio fisico (drenagem, EPS/defensa)
# tambem pode ser feito pelo Trator 4.7m ("tripla").
LARGURA_MINIMA_TRATOR_47_M = 5.0


def coluna_area_equipamento(nome: str) -> str:
    """Nome da coluna do inventario que guarda a area mecanizada (m2) atendida
    por um equipamento, ex: 'Trator 1.7m' -> 'mec_m2__trator_1_7m'. Para
    alternativas ('Trator 1.7m ou Spider') -> 'mec_m2__trator_1_7m__ou__spider'."""
    import re
    import unicodedata

    def _slug(texto):
        base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
        return re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return "mec_m2__" + "__ou__".join(_slug(p) for p in nome.split(SEPARADOR_ALTERNATIVAS))


def nome_alternativas(nomes) -> str:
    """Junta equipamentos alternativos num nome unico, sem repeticao e na ordem
    do catalogo (ex: ['Spider', 'Trator 1.7m'] -> 'Trator 1.7m ou Spider')."""
    ordem = {n: i for i, n in enumerate(ROCADA_MECANIZADA)}
    unicos = sorted(dict.fromkeys(nomes), key=lambda n: (ordem.get(n, 99), n))
    return SEPARADOR_ALTERNATIVAS.join(unicos)


# --- Ciclos/ano sazonais (dimensionamento chuva x seca) ------------------
# Divisao do ano usada na pratica: 6 meses de chuva e 6 de seca (usuario,
# 2026-10-20; antes era 7 + 5). Vale para todas as atividades e para a aba
# Vegetacao e Clima; cada campo continua editavel na tela.
MESES_CHUVA_PADRAO = 6
MESES_SECA_PADRAO = 12 - MESES_CHUVA_PADRAO

CICLOS_PADRAO = {
    "rocada": {"ciclos_chuva": 10, "meses_chuva": MESES_CHUVA_PADRAO, "ciclos_seca": 5, "meses_seca": MESES_SECA_PADRAO,
               "fonte": "referencia (SPVias: chuva 10 ciclos / seca 5 ciclos)"},
}

# --- Atividades "Full Service" (RioSP FS 4.0) -----------------------------
# unidade "km": extensao do trecho. meta = km atendidos por dia por equipe.
# Janela de execucao das atividades em "ciclos por ano" -> meses padrao.
JANELAS_EXECUCAO = {"Seca": MESES_SECA_PADRAO, "Chuva": MESES_CHUVA_PADRAO, "Ano todo": 12}

FULL_SERVICE_ATIVIDADES = {
    # Aceiro e Drenagem fora: "ciclos por ano" (modo anual), nao chuva/seca --
    # contratos Artesp: 1 ciclo/ano, executado na seca (reuniao Daniel x Omar,
    # 2026-10-16). Cenario 2 = comparativo (ex.: 2 ciclos/ano).
    "Aceiro (com remocao de massa verde)": {
        "unidade": "km", "meta_dia": 2, "modo": "anual", "ciclos_ano": 1, "ciclos_ano_alt": 2,
        "janela": "Seca", "meses_janela": MESES_SECA_PADRAO,
        "fonte": "ciclos: contratos Artesp (1 ciclo/ano, na seca); meta/dia: estimativa (a validar)",
    },
    "Drenagem de plataforma": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 4, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 4, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
    },
    "Drenagem fora de plataforma": {
        "unidade": "km", "meta_dia": 2, "modo": "anual", "ciclos_ano": 1, "ciclos_ano_alt": 2,
        "janela": "Seca", "meses_janela": MESES_SECA_PADRAO,
        "fonte": "ciclos: contratos Artesp (1 ciclo/ano, na seca) -- equivale ao RioSP FS4.0 "
                 "(1/4 do segmento por ciclo x 4 ciclos = 1 passada completa/ano); meta/dia: estimativa (a validar)",
    },
    "Capina": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 6, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 2, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
    },
    "Refilamento": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 4, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 2, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
    },
    "Calcada": {
        "unidade": "m2", "meta_dia": 3000, "ciclos_chuva": 4, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 4, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
    },
    "Lavagem de placas / catadioptricos": {
        "unidade": "un", "meta_dia": 15, "ciclos_chuva": 1, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 1, "meses_seca": MESES_SECA_PADRAO,
        "fonte": "referencia (RioSP FS4.0: 15-16 placas/dia, 2 ciclos/ano no total)",
    },
    "Remocao de lixo": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 12, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 12, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
    },
}

# --- Equipes especialistas -------------------------------------------------
ESPECIALISTAS_ATIVIDADES = {
    "Limpeza / lavagem de EPS e barreira": {
        "unidade": "m", "meta_dia": 500, "ciclos_chuva": 2, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 2, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
        # Modo reativo (ver retroanalises/perguntas_pendentes.md item 7): em vez de
        # varredura ciclica, dimensiona por taxa de acionamentos/km/ano x
        # atendimento/dia por equipe -- mesmo padrao ja usado pela NC.
        "meta_dia_reativo": 2.0, "fonte_reativo": "estimativa (a validar)",
    },
    "Manutencao de defensa metalica": {
        "unidade": "m", "meta_dia": 400, "ciclos_chuva": 1, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 1, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
        "meta_dia_reativo": 1.5, "fonte_reativo": "estimativa (a validar)",
    },
    "Atendimento a Nao Conformidades (NC)": {
        "unidade": "NC", "meta_dia": 1.6, "ciclos_chuva": 1, "meses_chuva": 12,
        "ciclos_seca": 1, "meses_seca": 12,
        "fonte": "referencia (AutoBAn: 35,5 NC/equipe/mes = ~1,6 NC/dia)",
        # 1 ciclo em 12 meses: a quantidade e o volume ANUAL de NCs.
        "ajuda_qtd": "Volume ANUAL de NCs do contrato (1 ciclo em 12 meses). Se você tem o volume mensal, "
                     "multiplique por 12 -- digitar o mensal subdimensiona as equipes em 12 vezes.",
    },
    "Varricao": {
        "unidade": "km", "meta_dia": 8, "ciclos_chuva": 24, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 24, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
    },
    "Poda de arvore": {
        "unidade": "un", "meta_dia": 5, "ciclos_chuva": 1, "meses_chuva": MESES_CHUVA_PADRAO,
        "ciclos_seca": 1, "meses_seca": MESES_SECA_PADRAO, "fonte": "estimativa (a validar)",
    },
}

TIPOS_CONTRATO = ["Full Service", "Especialistas"]

# Atividades com modo reativo disponivel (dano por incidencia/acionamento, nao
# por varredura ciclica) -- ver retroanalises/perguntas_pendentes.md item 7.
ATIVIDADES_COM_MODO_REATIVO = ["Limpeza / lavagem de EPS e barreira", "Manutencao de defensa metalica"]

# Mapeia cada atividade para a coluna do inventario que fornece a quantidade
# (soma de todos os trechos). "extensao_km" e calculada automaticamente a
# partir de km_inicial/km_final.
COLUNA_INVENTARIO_POR_ATIVIDADE = {
    # Aceiro e drenagem NAO cobrem 100% da extensao da rodovia (trechos
    # urbanos/APP ficam de fora, ou parte e mecanizada/manual de forma
    # diferente) -- por isso usam coluna de inventario propria, em vez de
    # "extensao_km" (extensao total). Ver retroanalises/melhorias_propostas.md.
    "Aceiro (com remocao de massa verde)": "aceiro_km",
    "Drenagem de plataforma": "drenagem_plataforma_km",
    "Drenagem fora de plataforma": "drenagem_fora_plataforma_km",
    "Capina": "extensao_km",
    "Refilamento": "extensao_km",
    "Calcada": "calcada_m2",
    "Lavagem de placas / catadioptricos": "placas_qtd",
    "Remocao de lixo": "extensao_km",
    "Limpeza / lavagem de EPS e barreira": "eps_barreira_m",
    "Manutencao de defensa metalica": "defensa_m",
    "Atendimento a Nao Conformidades (NC)": None,  # nao vem do inventario, e informado manualmente (volume ANUAL de NCs do contrato)
    "Varricao": "extensao_km",
    "Poda de arvore": None,  # informado manualmente (nao ha coluna padrao no inventario minimo)
}
