import os

import pytest

from plugins.extractors.base import Extractor
from plugins.extractors.pymupdf_extractor import PyMuPDFExtractor

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")


def test_extractor_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Extractor()


def test_pymupdf_supports_returns_true_for_text_pdf():
    extractor = PyMuPDFExtractor()
    pdf_path = os.path.join(FIXTURES_DIR, "native_text_sample.pdf")
    assert extractor.supports(pdf_path) is True


def test_pymupdf_supports_returns_false_for_image_only_pdf():
    extractor = PyMuPDFExtractor()
    pdf_path = os.path.join(FIXTURES_DIR, "image_only_sample.pdf")
    assert extractor.supports(pdf_path) is False


def test_pymupdf_extract_returns_one_page_per_pdf_page():
    extractor = PyMuPDFExtractor()
    pdf_path = os.path.join(FIXTURES_DIR, "native_text_sample.pdf")
    pages = extractor.extract(pdf_path)
    assert len(pages) == 1


def test_pymupdf_extract_sets_confidence_and_source():
    extractor = PyMuPDFExtractor()
    pdf_path = os.path.join(FIXTURES_DIR, "native_text_sample.pdf")
    pages = extractor.extract(pdf_path)
    page = pages[0]
    assert page.confidence == 1.0
    assert page.source == "pymupdf"


# --- OS-049: fronteira de bloco preservada até o Speaker --------------------

STRUCTURED_PDF = os.path.join(FIXTURES_DIR, "structured_layout_sample.pdf")


def test_pymupdf_separates_blocks_with_blank_line():
    """Sem isso, título e prosa chegam grudados e a pausa de parágrafo da OS-045 nunca dispara."""
    texto = PyMuPDFExtractor().extract(STRUCTURED_PDF)[0].text
    assert "TITULO DA SECAO\n\nA primeira frase" in texto


def test_pymupdf_heading_is_not_glued_to_next_paragraph():
    """O defeito observado: 'CÓDIGO-FONTE E OUTROS RECURSOS Grande parte do código...'."""
    texto = PyMuPDFExtractor().extract(STRUCTURED_PDF)[0].text
    assert "TITULO DA SECAO A primeira" not in texto
    assert "paragrafo.\n\nEste e um segundo bloco" in texto


def test_pymupdf_keeps_single_newline_inside_block():
    """Linha do MESMO bloco continua com \\n simples: a OS-035 depende disso para recolar hífen."""
    texto = PyMuPDFExtractor().extract(STRUCTURED_PDF)[0].text
    assert "demons-\ntracao" in texto


def test_pymupdf_hyphenated_word_still_joined_by_cleaner():
    """Contrato da OS-035 preservado ponta a ponta."""
    from processing.cleaner import clean_text

    paginas = PyMuPDFExtractor().extract(STRUCTURED_PDF)
    limpo = clean_text([p.text for p in paginas])
    assert "demonstracao" in limpo
    assert "demons- tracao" not in limpo


def test_chunker_produces_paragraph_from_extracted_pdf():
    """O ponto da OS: a fronteira de parágrafo passa a existir em PDF real (antes: nenhuma)."""
    from processing.chunker import PARAGRAPH_SEPARATOR, chunk_text
    from processing.cleaner import clean_text
    from processing.sanitizer import sanitize_text

    paginas = PyMuPDFExtractor().extract(STRUCTURED_PDF)
    texto = sanitize_text(clean_text([p.text for p in paginas]))
    assert PARAGRAPH_SEPARATOR in "".join(chunk_text(texto))


def test_pymupdf_extract_contract_unchanged():
    """O contrato Extractor NÃO muda nesta OS — uma página, mesmos metadados."""
    paginas = PyMuPDFExtractor().extract(STRUCTURED_PDF)
    assert len(paginas) == 1
    assert paginas[0].confidence == 1.0
    assert paginas[0].source == "pymupdf"
    assert paginas[0].page_number == 1
    assert isinstance(paginas[0].text, str)


# --- OS-050: blocos que não são texto do autor -----------------------------

STYLED_PDF = os.path.join(FIXTURES_DIR, "styled_blocks_sample.pdf")


def _texto_extraido(caminho=STYLED_PDF):
    return "\n\n".join(p.text for p in PyMuPDFExtractor().extract(caminho))


def test_pymupdf_drops_running_header():
    """9,3pt no livro real (0,96x do corpo): escapa de qualquer limiar de tamanho, só a posição o pega."""
    assert "TITULO DO LIVRO" not in _texto_extraido()


def test_pymupdf_drops_footnote_block():
    """Nota de rodapé era narrada no meio do parágrafo; descartada como URL e e-mail na OS-040."""
    assert "nota de rodape" not in _texto_extraido()


def test_pymupdf_keeps_heading_block():
    assert "TITULO DA SECAO" in _texto_extraido()


def test_pymupdf_keeps_italic_quote_block():
    """Citação continua narrada; o que a OS-050 não faz é dar registro diferente a ela."""
    assert "medo de parecer fraco" in _texto_extraido()


def test_pymupdf_keeps_body_block():
    assert "corpo do texto" in _texto_extraido()


def test_pymupdf_keeps_first_block_when_it_is_real_content():
    """O risco declarado na OS: descartar por posição não pode comer conteúdo legítimo do topo."""
    assert "conteudo real do autor" in _texto_extraido()


def test_pymupdf_body_size_is_measured_per_document():
    """Limiar absoluto quebraria em qualquer PDF cujo corpo não seja 9,7pt."""
    import fitz

    from plugins.extractors.pymupdf_extractor import _body_size

    doc = fitz.open(STYLED_PDF)
    assert _body_size(doc) == 10.0
    doc.close()


def test_pymupdf_style_classification_does_not_break_os049_blocks():
    """As fronteiras de bloco da OS-049 seguem valendo entre o que sobrou."""
    texto = PyMuPDFExtractor().extract(STYLED_PDF)[0].text
    assert "TITULO DA SECAO\n\nEste e o corpo" in texto
