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


def gerar_relatorio(
    caminho_saida: str,
    nome_contrato: str,
    resumo_rocada: dict,
    resultados_atividades: dict,
    analise_contrato: list | None = None,
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
    """
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    _capa(prs, "Dimensionamento de Conservação Rodoviária",
          f"{nome_contrato}  ·  Relatório gerado pelo DimConservação")

    # Slide resumo roçada
    slide = _slide_em_branco(prs)
    _titulo(slide, "Resumo — Roçada (cenário de pico)")
    linhas = [["Modalidade", "Quantidade necessária", "Cenário de pico"]]
    for nome, r in resumo_rocada.items():
        qtd = r.get("equipes_arredondadas", "-")
        unidade = r.get("unidade", "equipe(s)")
        linhas.append([nome, f"{qtd} {unidade}" if qtd != "-" else "-", r.get("cenario", "-")])
    _tabela(slide, Inches(1.5), linhas, larguras=[5, 4, 3])

    # Um slide de tabela por grupo de atividades (Full Service, Especialistas, ...)
    cabecalho = ["Atividade", "Unidade", "Quantidade", "Equipes (chuva)", "Equipes (seca)", "Equipes (pico)"]
    for grupo, linhas_grupo in resultados_atividades.items():
        if not linhas_grupo:
            continue
        slide = _slide_em_branco(prs)
        _titulo(slide, f"Dimensionamento por atividade — {grupo}")
        _tabela(slide, Inches(1.4), [cabecalho] + linhas_grupo, larguras=[4, 1.3, 2, 1.8, 1.8, 1.8])

    # Slide analise de contrato (se houver)
    if analise_contrato:
        slide = _slide_em_branco(prs)
        _titulo(slide, "Análise de Contrato — Dimensionado × Contratado")
        cabecalho = ["Atividade", "Dimensionado", "Contratado", "Status"]
        _tabela(slide, Inches(1.4), [cabecalho] + analise_contrato, larguras=[5, 2.5, 2.5, 2.5])

    prs.save(caminho_saida)
    return caminho_saida
