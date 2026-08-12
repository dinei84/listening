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
