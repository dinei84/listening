import os

from core.models import ExtractedPage
from plugins.extractors.easyocr_extractor import EasyOCRExtractor

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "ocr")


def _fixture(name: str) -> str:
    return os.path.join(FIXTURES_DIR, name)


class FakeReader:
    def __init__(self, results):
        self._results = results

    def readtext(self, image):
        return self._results


def _legible_reader():
    return FakeReader(
        [
            ([(0, 0), (10, 0), (10, 10), (0, 10)], "Hello", 0.95),
            ([(0, 10), (10, 10), (10, 20), (0, 20)], "world", 0.91),
        ]
    )


def _unreadable_reader():
    return FakeReader([])


def test_easyocr_supports_returns_true_for_valid_pdf():
    extractor = EasyOCRExtractor()
    assert extractor.supports(_fixture("clear_text_pdf.pdf")) is True


def test_easyocr_supports_returns_false_for_nonexistent_path():
    extractor = EasyOCRExtractor()
    assert extractor.supports(_fixture("does_not_exist.pdf")) is False


def test_easyocr_supports_returns_false_for_corrupted_file():
    extractor = EasyOCRExtractor()
    assert extractor.supports(_fixture("corrupted.pdf")) is False


def test_easyocr_extract_returns_one_page_per_pdf_page(monkeypatch):
    monkeypatch.setattr(EasyOCRExtractor, "_get_reader", lambda self: _legible_reader())
    extractor = EasyOCRExtractor()
    pages = extractor.extract(_fixture("clear_text_pdf.pdf"))
    assert len(pages) == 1


def test_easyocr_extract_sets_source_to_easyocr(monkeypatch):
    monkeypatch.setattr(EasyOCRExtractor, "_get_reader", lambda self: _legible_reader())
    extractor = EasyOCRExtractor()
    pages = extractor.extract(_fixture("clear_text_pdf.pdf"))
    assert all(p.source == "easyocr" for p in pages)


def test_easyocr_extract_confidence_matches_formula_for_legible_text(monkeypatch):
    monkeypatch.setattr(EasyOCRExtractor, "_get_reader", lambda self: _legible_reader())
    extractor = EasyOCRExtractor()
    pages = extractor.extract(_fixture("clear_text_pdf.pdf"))
    page = pages[0]
    assert isinstance(page, ExtractedPage)
    assert page.text.strip() == "Hello world"
    assert page.confidence == (0.95 + 0.91) / 2


def test_easyocr_extract_confidence_is_zero_for_unreadable_image(monkeypatch):
    monkeypatch.setattr(
        EasyOCRExtractor, "_get_reader", lambda self: _unreadable_reader()
    )
    extractor = EasyOCRExtractor()
    pages = extractor.extract(_fixture("unreadable_text_pdf.pdf"))
    page = pages[0]
    assert page.confidence == 0.0
