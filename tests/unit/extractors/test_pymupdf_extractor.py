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
