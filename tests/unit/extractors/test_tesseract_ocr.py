import os

from core.models import ExtractedPage
from plugins.extractors.tesseract_ocr import TesseractOCR

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "ocr")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES_DIR, name)


def test_tesseract_supports_returns_true_for_valid_pdf():
    extractor = TesseractOCR()
    assert extractor.supports(_fixture("clear_text_pdf.pdf")) is True


def test_tesseract_supports_returns_false_for_nonexistent_path():
    extractor = TesseractOCR()
    assert extractor.supports(_fixture("does_not_exist.pdf")) is False


def test_tesseract_supports_returns_false_for_corrupted_file():
    extractor = TesseractOCR()
    assert extractor.supports(_fixture("corrupted.pdf")) is False


def test_tesseract_extract_returns_one_page_per_pdf_page():
    extractor = TesseractOCR()
    pages = extractor.extract(_fixture("clear_text_pdf.pdf"))
    assert len(pages) == 1


def test_tesseract_extract_sets_source_to_tesseract():
    extractor = TesseractOCR()
    pages = extractor.extract(_fixture("clear_text_pdf.pdf"))
    assert all(p.source == "tesseract" for p in pages)


def test_tesseract_extract_confidence_matches_approved_formula_for_legible_text():
    extractor = TesseractOCR()
    pages = extractor.extract(_fixture("clear_text_pdf.pdf"))
    page = pages[0]
    assert isinstance(page, ExtractedPage)
    assert page.text.strip()
    assert page.confidence >= 0.85


def test_tesseract_extract_confidence_is_zero_for_unreadable_image():
    extractor = TesseractOCR()
    pages = extractor.extract(_fixture("unreadable_text_pdf.pdf"))
    page = pages[0]
    assert page.confidence == 0.0
