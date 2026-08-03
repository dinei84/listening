import fitz

from core.models import ExtractedPage
from plugins.extractors.base import Extractor


class PyMuPDFExtractor(Extractor):
    def supports(self, pdf_path: str) -> bool:
        doc = fitz.open(pdf_path)
        for page in doc:
            if page.get_text().strip():
                doc.close()
                return True
        doc.close()
        return False

    def extract(
        self, pdf_path: str, page_range: tuple[int, int] | None = None
    ) -> list[ExtractedPage]:
        doc = fitz.open(pdf_path)
        pages: list[ExtractedPage] = []
        start, end = page_range if page_range else (0, len(doc))
        for i in range(max(0, start), min(len(doc), end)):
            page = doc[i]
            text = page.get_text()
            pages.append(
                ExtractedPage(
                    page_number=i + 1,
                    text=text,
                    confidence=1.0,
                    source="pymupdf",
                )
            )
        doc.close()
        return pages
