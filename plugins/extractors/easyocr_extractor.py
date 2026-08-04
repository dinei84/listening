import io

import easyocr
import fitz
import numpy as np
from PIL import Image

from core.models import ExtractedPage
from plugins.extractors.base import Extractor


class EasyOCRExtractor(Extractor):
    def __init__(self):
        self._reader = None

    def supports(self, pdf_path: str) -> bool:
        try:
            doc = fitz.open(pdf_path)
            has_pages = len(doc) >= 1
            doc.close()
            return has_pages
        except RuntimeError:
            return False

    def extract(
        self, pdf_path: str, page_range: tuple[int, int] | None = None
    ) -> list[ExtractedPage]:
        doc = fitz.open(pdf_path)
        pages: list[ExtractedPage] = []
        start, end = page_range if page_range else (0, len(doc))
        for i in range(max(0, start), min(len(doc), end)):
            page = doc[i]
            pix = page.get_pixmap(dpi=150)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            text, confidence = self._ocr_page(image)
            pages.append(
                ExtractedPage(
                    page_number=i + 1,
                    text=text,
                    confidence=confidence,
                    source="easyocr",
                )
            )
        doc.close()
        return pages

    def _ocr_page(self, image: Image.Image) -> tuple[str, float]:
        reader = self._get_reader()
        results = reader.readtext(np.array(image))
        confidences = [confidence for _, _, confidence in results]
        text = " ".join(text for _, text, _ in results)
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return text, confidence

    def _get_reader(self) -> easyocr.Reader:
        if self._reader is None:
            self._reader = easyocr.Reader(["en"], gpu=False)
        return self._reader
