"""Geracao do relatorio executivo em PowerPoint a partir dos resultados de
dimensionamento e analise de contrato."""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# Paleta Motiva (mesma usada nos decks executivos anteriores)
ROXO_PRIMARIO = RGBColor(0x5E, 0x22, 0xF3)
ROXO_ESCURO = RGBColor(0x3D, 0x1A, 0x9E)
LAVANDA = RGBColor(0xED, 0xE8, 0xFB)
TINTA = RGBColor(0x1A, 0x1A, 0x2E)
CINZA = RGBColor(0x55, 0x55, 0x55)
BRANCO = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_BRANCA = ASSETS_DIR / "logo_motiva_branca.png"   # para fundo roxo (capa)
LOGO_ROXA = ASSETS_DIR / "logo_motiva_roxa.png"        # para fundo claro (rodape dos slides)


def _logo_capa(slide):
    if LOGO_BRANCA.exists():
        slide.shapes.add_picture(str(LOGO_BRANCA), Inches(0.8), Inches(0.6), height=Inches(0.5))


def _logo_cabecalho(slide):
    """Logo no canto superior direito, ao lado do título -- posição fixa que
    nunca é coberta pelo conteúdo do slide (diferente do rodapé, onde uma
    tabela comprida podia sobrepor a logo)."""
    if LOGO_ROXA.exists():
        slide.shapes.add_picture(str(LOGO_ROXA), SLIDE_W - Inches(1.7), Inches(0.35), height=Inches(0.35))


def _slide_em_branco(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _titulo(slide, texto, subtitulo=None):
    _logo_cabecalho(slide)
    box = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(10.9), Inches(0.9))
    tf = box.text_frame
    tf.text = texto
    p = tf.paragraphs[0]
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = ROXO_ESCURO
    if subtitulo:
        p2 = tf.add_paragraph()
        p2.text = subtitulo
        p2.font.size = Pt(14)
        p2.font.color.rgb = CINZA


def _capa(prs, titulo, subtitulo):
    slide = _slide_em_branco(prs)
    fundo = slide.shapes.add_shape(1, 0, 0, SLIDE_W, SLIDE_H)
    fundo.fill.solid()
    fundo.fill.fore_color.rgb = ROXO_PRIMARIO
    fundo.line.fill.background()
    fundo.shadow.inherit = False

    _logo_capa(slide)

    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.8), Inches(11.5), Inches(1.5))
    tf = box.text_frame
    tf.text = titulo
    tf.paragraphs[0].font.size = Pt(40)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = BRANCO

    box2 = slide.shapes.add_textbox(Inches(0.8), Inches(3.9), Inches(11.5), Inches(1))
    tf2 = box2.text_frame
    tf2.text = subtitulo
    tf2.paragraphs[0].font.size = Pt(18)
    tf2.paragraphs[0].font.color.rgb = LAVANDA
    return slide


def _tabela(slide, top, dados, larguras=None):
    linhas = len(dados)
    colunas = len(dados[0])
    left = Inches(0.6)
    width = Inches(12.1)
    height = Inches(0.4 * linhas)
    grafico = slide.shapes.add_table(linhas, colunas, left, top, width, height)
    tabela = grafico.table

    if larguras:
        for i, w in enumerate(larguras):
            tabela.columns[i].width = Inches(w)

    for i, linha in enumerate(dados):
        for j, valor in enumerate(linha):
            celula = tabela.cell(i, j)
            celula.text = str(valor)
            p = celula.text_frame.paragraphs[0]
            p.font.size = Pt(12)
            if i == 0:
                p.font.bold = True
                p.font.color.rgb = BRANCO
                celula.fill.solid()
                celula.fill.fore_color.rgb = ROXO_PRIMARIO
            else:
                celula.fill.solid()
                celula.fill.fore_color.rgb = BRANCO if i % 2 else LAVANDA
    return grafico


VERMELHO = RGBColor(0xC0, 0x39, 0x2B)
VERDE = RGBColor(0x2E, 0x7D, 0x32)
MAX_LINHAS_TABELA = 12  # linhas de dados por slide: 13 × 0,4" a partir de 1,4" cabe com folga em 7,5"


def _slides_tabela(prs, titulo, cabecalho, linhas, larguras):
    """Uma tabela por slide, quebrada em páginas de até MAX_LINHAS_TABELA linhas
    (regra do relatório: nada passa do slide nem se sobrepõe)."""
    paginas = [linhas[i:i + MAX_LINHAS_TABELA] for i in range(0, len(linhas), MAX_LINHAS_TABELA)] or [[]]
    for n, pagina in enumerate(paginas, start=1):
        slide = _slide_em_branco(prs)
        _titulo(slide, titulo + (f" ({n}/{len(paginas)})" if len(paginas) > 1 else ""))
        if pagina:
            _tabela(slide, Inches(1.4), [cabecalho] + pagina, larguras=larguras)


def _cartao(slide, left, top, numero, rotulo, cor):
    caixa = slide.shapes.add_shape(5, left, top, Inches(3.8), Inches(1.3))  # retângulo arredondado
    caixa.fill.solid()
    caixa.fill.fore_color.rgb = LAVANDA
    caixa.line.fill.background()
    caixa.shadow.inherit = False
    tf = caixa.text_frame
    tf.text = str(numero)
    tf.paragraphs[0].font.size = Pt(36)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = cor
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    p = tf.add_paragraph()
    p.text = rotulo
    p.font.size = Pt(14)
    p.font.color.rgb = TINTA
    p.alignment = PP_ALIGN.CENTER


def _slide_sintese(prs, analise_contrato, totais_analise):
    """Síntese da Análise de Contrato (backlog item 62): contagem por status, totais
    por unidade e os maiores déficits, num slide próprio antes da tabela."""
    slide = _slide_em_branco(prs)
    _titulo(slide, "Síntese — Dimensionado × Contratado",
            "Totais por unidade: roçadores, equipes e equipamentos não se somam entre si")
    deltas = [(l[0], l[1], l[2], l[2] - l[1]) for l in analise_contrato]
    deficits = [d for d in deltas if d[3] < 0]
    topo = Inches(1.5)
    _cartao(slide, Inches(0.6), topo, len(deficits), "atividades em déficit", VERMELHO)
    _cartao(slide, Inches(4.75), topo, sum(1 for d in deltas if d[3] == 0), "conformes", VERDE)
    _cartao(slide, Inches(8.9), topo, sum(1 for d in deltas if d[3] > 0), "com excedente", ROXO_PRIMARIO)

    fim = 3.05  # polegadas: o texto dos déficits começa logo abaixo da tabela, sem sobrepor
    if totais_analise:
        linhas = [["Unidade", "Dimensionado", "Contratado", "Diferença"]]
        for unidade, (dimensionado, contratado) in list(totais_analise.items())[:6]:  # 7 × 0,4" cabe
            linhas.append([unidade, dimensionado, contratado, f"{contratado - dimensionado:+d}"])
        _tabela(slide, Inches(3.05), linhas, larguras=[4.6, 2.5, 2.5, 2.5])
        fim += 0.4 * len(linhas)

    box = slide.shapes.add_textbox(Inches(0.6), Inches(fim + 0.25), Inches(12.1), Inches(7.2 - fim - 0.25))
    tf = box.text_frame
    tf.word_wrap = True
    if deficits:
        maiores = sorted(deficits, key=lambda d: d[3] / d[1] if d[1] else 0)[:3]
        tf.text = "Maiores déficits: " + "; ".join(
            f"{nome} ({delta:+d}" + (f", {100 * delta / dim:+.0f}%)" if dim else ")")
            for nome, dim, _contr, delta in maiores)
    else:
        tf.text = "Nenhuma atividade em déficit: o contratado cobre o dimensionado em todas as linhas."
    tf.paragraphs[0].font.size = Pt(14)
    tf.paragraphs[0].font.color.rgb = TINTA


def gerar_relatorio(
    caminho_saida: str,
    nome_contrato: str,
    resumo_rocada: dict,
    resultados_atividades: dict,
    analise_contrato: list | None = None,
    totais_analise: dict | None = None,
):
    """Monta o PPTX executivo.

    resumo_rocada: dict com uma chave por modalidade de roçada (ex: "Roçada
        Manual"), cada uma um dict com 'equipes_arredondadas', 'cenario' e
        'unidade' (ex: "roçador(es)").
    resultados_atividades: dict {grupo: linhas}, ex: {"Full Service": [...],
        "Especialistas": [...]}, cada linha [atividade, unidade, qtd, chuva,
        seca, pico] -- um slide de tabela é gerado por grupo, em vez de uma
        tabela única com todas as atividades (evita tabela comprida demais).
    analise_contrato: lista de linhas [atividade, dimensionado, contratado, status]
    totais_analise: dict {unidade: [dimensionado, contratado]} para o slide de síntese
    """
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    _capa(prs, "Dimensionamento de Conservação Rodoviária",
          f"{nome_contrato}  ·  Relatório gerado pelo DimConservação")

    # Slide resumo roçada
    linhas = [["Modalidade", "Quantidade necessária", "Cenário de pico"]]
    for nome, r in resumo_rocada.items():
        qtd = r.get("equipes_arredondadas", "-")
        unidade = r.get("unidade", "equipe(s)")
        texto = f"{qtd} {unidade}" if qtd != "-" else "-"
        if "equipes_divisao" in r:  # Roçada Manual: roçadores, equipes e colaboradores totais
            texto += f" · {r['equipes_divisao']} equipe(s) · {r['colaboradores_totais']} colaborador(es)"
        linhas.append([nome, texto, r.get("cenario", "-")])
    _slides_tabela(prs, "Resumo — Roçada (cenário de pico)", linhas[0], linhas[1:], [4, 5.8, 2.3])

    # Um slide de tabela por grupo de atividades (Full Service, Especialistas, ...)
    cabecalho = ["Atividade", "Unidade", "Quantidade", "Equipes (chuva)", "Equipes (seca)", "Equipes (pico)"]
    for grupo, linhas_grupo in resultados_atividades.items():
        if not linhas_grupo:
            continue
        _slides_tabela(prs, f"Dimensionamento por atividade — {grupo}", cabecalho, linhas_grupo,
                       [4, 1.3, 2, 1.8, 1.8, 1.8])

    # Slide analise de contrato (se houver)
    if analise_contrato:
        _slide_sintese(prs, analise_contrato, totais_analise)
        _slides_tabela(prs, "Análise de Contrato — Dimensionado × Contratado",
                       ["Atividade", "Dimensionado", "Contratado", "Status"], analise_contrato, [5, 2.5, 2.5, 2.5])

    prs.save(caminho_saida)
    return caminho_saida
