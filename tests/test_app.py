"""Teste automatizado do app (AppTest, já incluso no Streamlit -- sem dependência nova).

Cobre a família de bugs "campo congelado" (melhorias_propostas.md itens 33-35):
campos pré-preenchidos que não acompanhavam o inventário/cálculo.

Como rodar (na pasta do projeto):
    python tests/test_app.py
(também funciona com `pytest tests/`, se o pytest estiver instalado)
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from streamlit.testing.v1 import AppTest  # noqa: E402

from modules import inventario as inv  # noqa: E402
from modules import parametros_padrao as pp  # noqa: E402

TIMEOUT = 120


def _app_com_exemplo() -> AppTest:
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, at.exception
    botao = next(b for b in at.button if b.label.startswith("Usar inventário de exemplo"))
    botao.click().run()
    assert not at.exception, at.exception
    return at


def _quantidades_esperadas() -> dict:
    df = inv.gerar_inventario_exemplo()
    esperado = {}
    for nome, coluna in pp.COLUNA_INVENTARIO_POR_ATIVIDADE.items():
        if coluna and coluna in df.columns:
            esperado[nome] = float(df[coluna].sum())
    return esperado


def _chave_quantidade(at: AppTest, nome: str):
    for prefixo in ("fs_qtd_", "esp_qtd_"):
        if f"{prefixo}{nome}" in at.session_state:
            return f"{prefixo}{nome}"
    return None


def test_quantidades_seguem_inventario():
    at = _app_com_exemplo()
    esperado = _quantidades_esperadas()
    assert esperado, "nenhuma atividade com coluna no inventário de exemplo"
    for nome, valor in esperado.items():
        chave = _chave_quantidade(at, nome)
        assert chave, f"campo de quantidade não encontrado para {nome}"
        assert at.session_state[chave] == valor, f"{nome}: campo={at.session_state[chave]} inventário={valor}"


def test_contratado_segue_dimensionado():
    at = _app_com_exemplo()
    atividades = [(n, r["equipes_arredondadas"]) for n, r in at.session_state["resumo_rocada"].items()]
    for linhas in at.session_state["resultados_atividades"].values():
        atividades += [(linha[0], linha[-1]) for linha in linhas]
    assert atividades, "nenhuma atividade dimensionada"
    for nome, dimensionado in atividades:
        assert at.session_state[f"contr_{nome}"] == int(dimensionado), f"{nome}: contratado != dimensionado"


def test_contratado_acompanha_mudanca_de_quantidade():
    at = _app_com_exemplo()
    nome = "Remocao de lixo"
    chave = _chave_quantidade(at, nome)
    at.number_input(key=chave).set_value(at.session_state[chave] * 10).run()
    assert not at.exception, at.exception
    novo = next(linha[-1] for linhas in at.session_state["resultados_atividades"].values()
                for linha in linhas if linha[0] == nome)
    assert at.session_state[f"contr_{nome}"] == int(novo), f"{nome}: contratado não acompanhou ({novo})"


def test_edicao_manual_preservada():
    at = _app_com_exemplo()
    chave = _chave_quantidade(at, "Capina")
    at.number_input(key=chave).set_value(999.0).run()
    assert not at.exception, at.exception
    at.run()  # novo rerun não pode sobrescrever a edição do usuário
    assert at.session_state[chave] == 999.0


def test_modelo_crescimento_todos_estados():
    from modules import crescimento as c
    assert len(c.CLIMA_UF) == 27
    for uf, clima in c.CLIMA_UF.items():
        taxas = c.taxa_mensal(clima, {c.ESPECIE_PADRAO: 100})
        alto = c.meses_crescimento_alto(taxas)
        baixo = [i for i in range(12) if i not in alto]
        assert len(alto) == pp.MESES_CHUVA_PADRAO == 6 and len(baixo) == 6, uf  # padrão 6 + 6
        assert sum((m + 1) % 12 not in alto for m in alto) == 1, uf  # meses consecutivos (um bloco só)
        assert len(c.meses_crescimento_alto(taxas, 7)) == 7, uf
        res = c.ciclos_periodo(taxas, alto, 30, 4)
        assert res["ciclos"] > 0, uf
        # altura máxima maior -> menos ciclos
        assert c.ciclos_periodo(taxas, alto, 50, 4)["ciclos"] < res["ciclos"], uf


def test_modelo_v2_todos_estados():
    """Modelo diário (2026-10-20): 27 estados com série embutida; 6 + 6 em bloco único
    escolhido pela demanda; seca com pico menor que a chuva; ano exigente >= típico."""
    from modules import crescimento as c
    for uf in c.CLIMA_UF:
        r = c.resumo_mensal(c.crescimento_diario(c.serie_uf(uf), {c.ESPECIE_PADRAO: 100}))
        alto = c.escolher_periodos(r["pico"], 6)
        baixo = [i for i in range(12) if i not in alto]
        assert len(alto) == 6 and sum((m + 1) % 12 not in alto for m in alto) == 1, uf
        assert max(r["pico"][i] for i in alto) >= max(r["pico"][i] for i in baixo), uf
        assert all(p8 >= p - 1e-9 for p8, p in zip(r["pico_p80"], r["pico"])), uf
        assert all(p >= m - 1e-9 for p, m in zip(r["pico"], r["media"])), uf  # pico de 30 dias >= média do mês
        assert c.ciclos_periodo(r["pico"], alto, 30, 4)["ciclos"] > 0, uf
        livre = c.divisao_otima_livre(r["pico"])
        assert c.custo_divisao(r["pico"], livre) <= c.custo_divisao(r["pico"], alto) + 1e-9, uf


def test_modelo_v2_sp_enxerga_a_seca():
    """SP (Campinas): o v1 dava água ~100% em julho; o diário mostra o inverno seco, a
    chuva pela demanda é nov–abr e a seca exige bem menos ciclos que a chuva."""
    from modules import crescimento as c
    r = c.resumo_mensal(c.crescimento_diario(c.serie_uf("SP"), {c.ESPECIE_PADRAO: 100}))
    assert max(r["agua"][6:9]) < 0.6  # jul-set
    alto = c.escolher_periodos(r["pico"], 6)
    assert c.rotulo_meses(alto) == "Nov–Abr", c.rotulo_meses(alto)
    baixo = [i for i in range(12) if i not in alto]
    ch = c.ciclos_periodo(r["pico"], alto, 30, 4)["ciclos"]
    se = c.ciclos_periodo(r["pico"], baixo, 30, 4)["ciclos"]
    assert 1.2 < ch / se < 2.5, (ch, se)


def test_modelo_v2_combina_pontos():
    """Vários pontos: a curva combinada é a média diária ponderada; o pico combinado
    não passa da média ponderada dos picos; um ponto só devolve ele mesmo."""
    from modules import crescimento as c
    comp = {c.ESPECIE_PADRAO: 100}
    sp = c.crescimento_diario(c.serie_uf("SP"), comp)
    go = c.crescimento_diario(c.serie_uf("GO"), comp)
    assert c.combinar([(100, sp)]) is sp
    comb = c.combinar([(70, sp), (30, go)])
    assert abs(comb["taxa"][500] - (0.7 * sp["taxa"][500] + 0.3 * go["taxa"][500])) < 1e-12
    r_sp, r_go, r_c = (c.resumo_mensal(x) for x in (sp, go, comb))
    for m in range(12):
        assert r_c["pico"][m] <= 0.7 * r_sp["pico"][m] + 0.3 * r_go["pico"][m] + 1e-9, m


def test_memoria_v2_bate_com_termico():
    """A memória (graus-dia de cada espécie × k × cobertura) soma o crescimento térmico do mês."""
    from modules import crescimento as c
    comp = {"Braquiarão Marandu (Urochloa brizantha)": 60, "Colonião / Mombaça / Tanzânia (Megathyrsus maximus)": 40}
    r = c.resumo_mensal(c.crescimento_diario(c.serie_uf("MG"), comp))
    for m in range(12):
        soma = sum(p * c.ESPECIES[e]["k"] * r["gd"][e][m] for e, p in r["pesos"].items())
        assert abs(soma - r["termico"][m]) < 1e-9, m
    base = r["media"]
    altura = 4 + 0.6 * c.crescimento_acumulado(base, 10, 60)
    fator = c.fator_calibracao([{"mes": 10, "dias": 60, "altura_cm": altura}], None, comp, c.SOLO_PADRAO, 4, base=base)
    assert abs(fator - 0.6) < 1e-9


def test_calibracao_integra_os_dias():
    """Item 44: medição de julho com 90 dias cobre abril-julho; o fator tem de sair
    igual à razão real (0,6), não à razão contra a taxa só de julho."""
    from modules import crescimento as c
    clima, comp, h0 = c.CLIMA_UF["GO"], {c.ESPECIE_PADRAO: 100}, 4
    base = c.taxa_mensal(clima, comp)
    for mes, dias in ((10, 10), (10, 60), (6, 90), (0, 400)):
        altura = h0 + 0.6 * c.crescimento_acumulado(base, mes, dias)
        fator = c.fator_calibracao([{"mes": mes, "dias": dias, "altura_cm": altura}], clima, comp, c.SOLO_PADRAO, h0)
        assert abs(fator - 0.6) < 1e-6, (mes, dias, fator)


def test_memoria_crescimento_bate_com_taxa():
    from modules import crescimento as c
    clima, comp = c.CLIMA_UF["GO"], {"Braquiarão Marandu (Urochloa brizantha)": 60, c.ESPECIE_PADRAO: 40}
    taxas = c.taxa_mensal(clima, comp, c.SOLO_PADRAO, 0.7)
    for mes in range(12):
        m = c.memoria_taxa(clima, comp, c.SOLO_PADRAO, 0.7, mes)
        assert abs(m["taxa"] - taxas[mes]) < 1e-9, mes
        assert abs(sum(e["contribuicao"] for e in m["especies"]) - m["termico"]) < 1e-9


def test_equipamentos_alternativos_nao_dividem_area():
    """Decisão do usuário (2026-10-16): 'Trator 1.7m, Spider' = qualquer um faz a
    área inteira. A área não é dividida; ocupa primeiro a folga das unidades já
    necessárias e o resto vai para o de maior produtividade."""
    import pandas as pd
    from modules import mecanizacao as mec
    cap = {"Trator 1.7m": 300_000.0, "Spider": 50_000.0}
    prod = {"Trator 1.7m": 20_000, "Spider": 5_000}
    areas = pd.DataFrame({
        "Trator 1.7m": [250_000.0, 0.0],      # 1 unidade, folga de 50.000
        "Spider": [0.0, 20_000.0],            # 1 unidade, folga de 30.000
        "Trator 1.7m ou Spider": [0.0, 100_000.0],
    })
    alocado, explicacao, _ = mec.alocar_frota(areas, prod, cap)
    assert list(alocado.columns) == ["Trator 1.7m", "Spider"]
    assert abs(alocado.values.sum() - areas.values.sum()) < 1e-6, "área tem de ser conservada"
    # folga do trator (50.000) + folga do spider (30.000) + resto (20.000) para o trator
    assert abs(alocado["Trator 1.7m"].sum() - 320_000) < 1e-6
    assert abs(alocado["Spider"].sum() - 50_000) < 1e-6
    assert len(explicacao) == 1
    # inventário manual com "Trator 1.7m, Spider" vira coluna de alternativas (não 50/50)
    df = inv.preparar_inventario(pd.DataFrame([{
        "trecho": "T1", "km_inicial": 0, "km_final": 5, "area_verde_m2": 1000, "pct_mecanizada": 100,
        "equipamento_predominante": "spider, Trator 1.7m",
    }]))
    coluna = pp.coluna_area_equipamento("Trator 1.7m ou Spider")
    assert coluna in df.columns and df[coluna].sum() == 1000
    from modules import quasar
    assert quasar.equipamentos_do_inventario(df) == {"Trator 1.7m ou Spider": coluna}


def test_substituicao_elimina_unidade_parcial():
    """Pergunta 31 (2026-10-16): restrição de tamanho e acesso. O Eixo-zero faz área
    de Trator 1.7m; a área da última unidade do trator vai para a folga do Eixo-zero
    e o trator perde 1 unidade. Sem a substituição, nada muda. Nunca cria unidade."""
    import math
    import pandas as pd
    from modules import mecanizacao as mec
    cap = {"Trator 1.7m": 300_000.0, "Eixo-zero": 400_000.0, "Trator 4.7m": 600_000.0}
    prod = {"Trator 1.7m": 20_000, "Eixo-zero": 30_000, "Trator 4.7m": 40_000}
    areas = pd.DataFrame({
        "Trator 1.7m": [300_000.0, 50_000.0],   # 1,17 unidade -> 2
        "Eixo-zero": [100_000.0, 0.0],          # 0,25 unidade -> 1 (folga 300.000)
        "Trator 4.7m": [10_000.0, 0.0],         # 0,02 unidade -> 1
    })

    def unidades(df):
        return {t: math.ceil(df[t].sum() / cap[t] - 1e-9) for t in df.columns}

    sem, _, trocas_sem = mec.alocar_frota(areas, prod, cap)
    assert unidades(sem) == {"Trator 4.7m": 1, "Trator 1.7m": 2, "Eixo-zero": 1} and trocas_sem.empty
    com, _, trocas = mec.alocar_frota(areas, prod, cap, pp.SUBSTITUICOES_PADRAO)
    assert abs(com.values.sum() - areas.values.sum()) < 1e-6
    assert unidades(com) == {"Trator 1.7m": 1, "Eixo-zero": 1}, unidades(com)  # 4.7m e 1 trator a menos
    assert set(trocas["Executado por"]) <= {"Eixo-zero", "Trator 1.7m"}


def test_regra_trator_47_quasar():
    """Pergunta 32: canteiro > 5 m, sem bloqueio, indicado para Trator 1.7m, aceita
    também o 4.7m; Eixo-zero e bloqueados não mudam."""
    import pandas as pd
    from modules import quasar
    df = pd.DataFrame({
        "equipamento": ["Trator 1.7m", "Trator 1.7m", "Trator 1.7m", "Eixo-zero", "Trator 1.7m"],
        "largura_m": [8.0, 4.0, 8.0, 8.0, 8.0],
        "bloqueio": [False, False, True, False, False],
        "observacao": ["", "", "", "", "drenagem + defensa"],
        "area_mecanizada_m2": [100.0] * 5,
    })
    novo, mascara = quasar.aplicar_regra_trator_47(df, 5.0)
    assert mascara.tolist() == [True, False, False, False, False]
    assert novo.loc[0, "equipamento"] == "Trator 1.7m, Trator 4.7m"


def test_aceiro_drenagem_fora_em_ciclos_por_ano():
    """Item 48 (reunião com Omar, 2026-10-16): Aceiro e Drenagem fora = ciclos por
    ano numa janela (padrão: 1 ciclo/ano na seca), sem equipe na chuva."""
    import math
    at = _app_com_exemplo()
    qtd = 300.0  # km (o exemplo não tem coluna de aceiro: informada à mão, como o usuário faria)

    def linha(nome):
        return next(l for l in at.session_state["resultados_atividades"]["Full Service"] if l[0] == nome)

    def esperado(cfg, ciclos):
        return math.ceil(round(qtd * ciclos / (cfg["meses_janela"] * 22 * cfg["meta_dia"]), 6))

    for nome in ("Aceiro (com remocao de massa verde)", "Drenagem fora de plataforma"):
        cfg = pp.FULL_SERVICE_ATIVIDADES[nome]
        assert cfg["modo"] == "anual"
        at.number_input(key=f"fs_qtd_{nome}").set_value(qtd).run()
        assert not at.exception, at.exception
        l = linha(nome)
        assert l[3] == 0, f"{nome}: não deveria ter equipe na chuva ({l})"
        assert l[4] == l[5] == esperado(cfg, cfg["ciclos_ano"]), (nome, l)
    # cenário 2 (2 ciclos/ano) passa a valer no dimensionamento
    nome = "Aceiro (com remocao de massa verde)"
    at.radio(key=f"fs_cen_{nome}").set_value("Cenário 2").run()
    assert not at.exception, at.exception
    assert linha(nome)[5] == esperado(pp.FULL_SERVICE_ATIVIDADES[nome], 2), linha(nome)


def test_aba_vegetacao_aplica_ciclos_na_rocada():
    at = _app_com_exemplo()
    botao = next(b for b in at.button if b.label.startswith("✅ Usar estes ciclos"))
    botao.click().run()
    assert not at.exception, at.exception
    aplicado = at.session_state["veg_aplicado"]["valores"]
    for pre in ("man", "mec"):
        for chave, valor in aplicado.items():
            assert at.session_state[f"{pre}_{chave}"] == valor, f"{pre}_{chave}"
    assert aplicado["mc"] + aplicado["ms"] == 12
    assert aplicado["mc"] == pp.MESES_CHUVA_PADRAO == 6
    assert any("Vegetação e Clima —" in c.value for c in at.caption), "legenda de origem dos ciclos ausente"


def test_quadro_resumo_e_totais_da_analise():
    """Itens 58 e 59 (2026-10-19): o quadro-resumo de Full Service/Especialistas mostra
    o valor editado (sem abrir o expansor) e a Análise de Contrato conta os déficits e
    soma dimensionado × contratado por unidade."""
    at = _app_com_exemplo()

    def quadro(atividade):
        return next(d.value for d in at.dataframe
                    if "Pico" in d.value.columns and atividade in set(d.value["Atividade"]))

    def metrica(rotulo):
        return next(m for m in at.metric if m.label == rotulo)

    for grupo, atividade in (("Full Service", "Capina"), ("Especialistas", "Varricao")):
        df = quadro(atividade)
        picos = {l[0]: l[5] for l in at.session_state["resultados_atividades"][grupo]}
        assert dict(zip(df["Atividade"], df["Pico"])) == picos, grupo

    chave = _chave_quantidade(at, "Capina")
    at.number_input(key=chave).set_value(at.session_state[chave] * 20).run()
    assert not at.exception, at.exception
    novo = next(l[5] for l in at.session_state["resultados_atividades"]["Full Service"] if l[0] == "Capina")
    df = quadro("Capina")
    assert df.loc[df["Atividade"] == "Capina", "Pico"].item() == novo
    assert df.loc[df["Atividade"] == "Capina", "Origem"].item() == "Manual"

    assert metrica("⚠️ Em déficit").value == "0"
    total_antes = int(metrica("Total contratado (equipe(s))").value)
    at.number_input(key="contr_Capina").set_value(novo - 1).run()
    assert not at.exception, at.exception
    assert metrica("⚠️ Em déficit").value == "1"
    assert int(metrica("Total contratado (equipe(s))").value) == total_antes - 1


def test_contratado_sobrevive_troca_de_modo():
    """Item 61: o Contratado de EPS/defensa não volta ao dimensionado ao alternar Preventivo/Reativo."""
    at = _app_com_exemplo()
    nome = sorted(pp.ATIVIDADES_COM_MODO_REATIVO)[0]
    at.number_input(key=f"contr_{nome}").set_value(42).run()
    assert not at.exception, at.exception
    radio = at.radio(key=f"esp_modo_{nome}")
    for opcao in (radio.options[1], radio.options[0]):
        at.radio(key=f"esp_modo_{nome}").set_value(opcao).run()
        assert not at.exception, at.exception
        assert at.session_state[f"contr_{nome}"] == 42, opcao


def test_padrao_seis_mais_seis():
    """Padrão 6 meses de chuva + 6 de seca em todas as atividades e nas abas de roçada (2026-10-20)."""
    for grupo in (pp.FULL_SERVICE_ATIVIDADES, pp.ESPECIALISTAS_ATIVIDADES):
        for nome, cfg in grupo.items():
            if cfg.get("modo") == "anual":
                assert cfg["meses_janela"] == pp.JANELAS_EXECUCAO[cfg["janela"]], nome
            elif cfg["meses_chuva"] != 12:  # NC: 1 ciclo em 12 meses (volume anual)
                assert (cfg["meses_chuva"], cfg["meses_seca"]) == (6, 6), nome
    at = _app_com_exemplo()
    for pre in ("man", "mec"):
        assert (at.session_state[f"{pre}_mc"], at.session_state[f"{pre}_ms"]) == (6, 6), pre
    assert len(at.session_state["veg_meses_alto"]) == 6


def test_rocada_manual_tres_contagens():
    """Pergunta 35: roçadores, equipes e colaboradores totais chegam à Análise de Contrato."""
    at = _app_com_exemplo()
    r = at.session_state["resumo_rocada"]["Roçada Manual"]
    total_equipe = at.session_state["comp_total_equipe"]
    assert r["equipes_divisao"] >= 1
    assert r["colaboradores_totais"] == r["equipes_divisao"] * total_equipe
    assert r["equipes_divisao"] * at.session_state["comp_rocadores_ativos"] >= r["equipes_arredondadas"]
    analise = {l[0]: l[1] for l in at.session_state["analise_contrato"]}
    assert analise["Roçada Manual"] == r["equipes_arredondadas"]
    assert analise["Roçada Manual — equipes"] == r["equipes_divisao"]
    assert analise["Roçada Manual — colaboradores totais"] == r["colaboradores_totais"]
    assert "colaborador(es)" in at.session_state["totais_analise"]


def test_checagem_inventario():
    """Item 65: a checagem acusa os erros típicos de planilha e não acusa o exemplo."""
    import pandas as pd
    assert inv.checar_inventario(inv.gerar_inventario_exemplo()).empty
    bruto = pd.DataFrame([
        {"trecho": "A", "rodovia": "SP-1", "km_inicial": 0, "km_final": 5, "area_verde_m2": "1.234,5",
         "pct_manual": 60, "pct_mecanizada": 40},
        {"trecho": "A", "rodovia": "SP-1", "km_inicial": 4, "km_final": 10, "area_verde_m2": 1000,
         "pct_manual": 70, "pct_mecanizada": 40},
        {"trecho": "C", "rodovia": "SP-2", "km_inicial": 3, "km_final": 3, "area_verde_m2": -5,
         "pct_manual": 50, "pct_mecanizada": 50},
    ])
    r = inv.checar_inventario(inv.preparar_inventario(bruto), bruto)
    texto = " | ".join(r["Problema"])
    for trecho_esperado in ("não é número", "deveria ser 100%", "repetido", "se sobrepõe", "Extensão zero",
                            "negativa"):
        assert trecho_esperado in texto, trecho_esperado
    assert r.iloc[0]["Gravidade"] == inv.ATENCAO  # atenção vem primeiro
    assert set(r["Linha"]) == {2, 3, 4}  # linha da planilha (cabeçalho = 1)


def test_pptx_sintese_e_paginacao():
    """Item 62: slide de síntese antes da tabela da Análise, e nada passa do slide."""
    import tempfile
    from pptx import Presentation
    from modules import export_pptx
    analise = [[f"Atividade {i}", 4, 4 - (i % 3), "-"] for i in range(25)]
    with tempfile.TemporaryDirectory() as tmp:
        caminho = str(Path(tmp) / "r.pptx")
        export_pptx.gerar_relatorio(caminho, "Teste", {"Roçada Manual": {
            "equipes_arredondadas": 9, "cenario": "Chuva", "unidade": "roçador(es)",
            "equipes_divisao": 3, "colaboradores_totais": 18}}, {}, analise, {"equipe(s)": [100, 75]})
        prs = Presentation(caminho)
    titulos = [next(s.text_frame.text.split("\n")[0] for s in sl.shapes if s.has_text_frame) for sl in prs.slides]
    assert any(t.startswith("Síntese") for t in titulos), titulos
    assert sum(t.startswith("Análise de Contrato") for t in titulos) == 3, titulos  # 25 linhas → 3 páginas
    assert sum(t.startswith("Resumo — Roçada") for t in titulos) == 1, titulos  # sem slide vazio duplicado
    for sl in list(prs.slides)[1:]:
        assert len(list(sl.shapes)) > 2, "slide só com título e logo"
    textos = " ".join(sh.text_frame.text for sl in prs.slides for sh in sl.shapes if sh.has_text_frame)
    assert "Maiores déficits" in textos
    for sl in prs.slides:
        for sh in sl.shapes:
            assert sh.top + sh.height <= prs.slide_height, (sh.name, sh.top + sh.height)


if __name__ == "__main__":
    testes = [v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    falhas = 0
    for t in testes:
        try:
            t()
            print(f"OK    {t.__name__}")
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"FALHA {t.__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes passaram")
    sys.exit(1 if falhas else 0)
