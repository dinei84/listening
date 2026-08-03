import io

import fitz
import pytesseract
from PIL import Image

from core.models import ExtractedPage
from plugins.extractors.base import Extractor


class TesseractOCR(Extractor):
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
                    source="tesseract",
                )
            )
        doc.close()
        return pages

    def _ocr_page(self, image: Image.Image) -> tuple[str, float]:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        confidences = [
            float(data["conf"][i])
            for i in range(len(data["text"]))
            if (data["text"][i] or "").strip() and float(data["conf"][i]) >= 0
        ]
        text = " ".join(word for word in data["text"] if (word or "").strip())
        confidence = (
            (sum(confidences) / len(confidences)) / 100.0 if confidences else 0.0
        )
        return text, confidence
