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
        assert alto and baixo, uf
        res = c.ciclos_periodo(taxas, alto, 30, 4)
        assert res["ciclos"] > 0, uf
        # altura máxima maior -> menos ciclos
        assert c.ciclos_periodo(taxas, alto, 50, 4)["ciclos"] < res["ciclos"], uf


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
    assert any("Vegetação e Clima —" in c.value for c in at.caption), "legenda de origem dos ciclos ausente"


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
