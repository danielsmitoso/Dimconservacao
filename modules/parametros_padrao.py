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


def coluna_area_equipamento(nome: str) -> str:
    """Nome da coluna do inventario que guarda a area mecanizada (m2) atendida
    por um equipamento, ex: 'Trator 1.7m' -> 'mec_m2__trator_1_7m'."""
    import re
    import unicodedata
    base = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii").lower()
    return "mec_m2__" + re.sub(r"[^a-z0-9]+", "_", base).strip("_")


# --- Ciclos/ano sazonais (dimensionamento chuva x seca) ------------------
CICLOS_PADRAO = {
    "rocada": {"ciclos_chuva": 10, "meses_chuva": 7, "ciclos_seca": 5, "meses_seca": 5,
               "fonte": "referencia (SPVias: chuva 10 ciclos / seca 5 ciclos)"},
}

# --- Atividades "Full Service" (RioSP FS 4.0) -----------------------------
# unidade "km": extensao do trecho. meta = km atendidos por dia por equipe.
FULL_SERVICE_ATIVIDADES = {
    "Aceiro (com remocao de massa verde)": {
        "unidade": "km", "meta_dia": 2, "ciclos_chuva": 4, "meses_chuva": 7,
        "ciclos_seca": 2, "meses_seca": 5, "fonte": "estimativa (a validar)",
    },
    "Drenagem de plataforma": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 4, "meses_chuva": 7,
        "ciclos_seca": 4, "meses_seca": 5, "fonte": "estimativa (a validar)",
    },
    "Drenagem fora de plataforma": {
        "unidade": "km", "meta_dia": 2, "ciclos_chuva": 4, "meses_chuva": 7,
        "ciclos_seca": 4, "meses_seca": 5,
        "fonte": "referencia (RioSP FS4.0: 1/4 do segmento por ciclo, 4 ciclos/ano)",
    },
    "Capina": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 6, "meses_chuva": 7,
        "ciclos_seca": 2, "meses_seca": 5, "fonte": "estimativa (a validar)",
    },
    "Refilamento": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 4, "meses_chuva": 7,
        "ciclos_seca": 2, "meses_seca": 5, "fonte": "estimativa (a validar)",
    },
    "Calcada": {
        "unidade": "m2", "meta_dia": 3000, "ciclos_chuva": 4, "meses_chuva": 7,
        "ciclos_seca": 4, "meses_seca": 5, "fonte": "estimativa (a validar)",
    },
    "Lavagem de placas / catadioptricos": {
        "unidade": "un", "meta_dia": 15, "ciclos_chuva": 1, "meses_chuva": 7,
        "ciclos_seca": 1, "meses_seca": 5,
        "fonte": "referencia (RioSP FS4.0: 15-16 placas/dia, 2 ciclos/ano no total)",
    },
    "Remocao de lixo": {
        "unidade": "km", "meta_dia": 5, "ciclos_chuva": 12, "meses_chuva": 7,
        "ciclos_seca": 12, "meses_seca": 5, "fonte": "estimativa (a validar)",
    },
}

# --- Equipes especialistas -------------------------------------------------
ESPECIALISTAS_ATIVIDADES = {
    "Limpeza / lavagem de EPS e barreira": {
        "unidade": "m", "meta_dia": 500, "ciclos_chuva": 2, "meses_chuva": 7,
        "ciclos_seca": 2, "meses_seca": 5, "fonte": "estimativa (a validar)",
        # Modo reativo (ver retroanalises/perguntas_pendentes.md item 7): em vez de
        # varredura ciclica, dimensiona por taxa de acionamentos/km/ano x
        # atendimento/dia por equipe -- mesmo padrao ja usado pela NC.
        "meta_dia_reativo": 2.0, "fonte_reativo": "estimativa (a validar)",
    },
    "Manutencao de defensa metalica": {
        "unidade": "m", "meta_dia": 400, "ciclos_chuva": 1, "meses_chuva": 7,
        "ciclos_seca": 1, "meses_seca": 5, "fonte": "estimativa (a validar)",
        "meta_dia_reativo": 1.5, "fonte_reativo": "estimativa (a validar)",
    },
    "Atendimento a Nao Conformidades (NC)": {
        "unidade": "NC", "meta_dia": 1.6, "ciclos_chuva": 1, "meses_chuva": 12,
        "ciclos_seca": 1, "meses_seca": 12,
        "fonte": "referencia (AutoBAn: 35,5 NC/equipe/mes = ~1,6 NC/dia)",
    },
    "Varricao": {
        "unidade": "km", "meta_dia": 8, "ciclos_chuva": 24, "meses_chuva": 7,
        "ciclos_seca": 24, "meses_seca": 5, "fonte": "estimativa (a validar)",
    },
    "Poda de arvore": {
        "unidade": "un", "meta_dia": 5, "ciclos_chuva": 1, "meses_chuva": 7,
        "ciclos_seca": 1, "meses_seca": 5, "fonte": "estimativa (a validar)",
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
    "Atendimento a Nao Conformidades (NC)": None,  # nao vem do inventario, e informado manualmente (volume mensal de NCs do contrato)
    "Varricao": "extensao_km",
    "Poda de arvore": None,  # informado manualmente (nao ha coluna padrao no inventario minimo)
}
