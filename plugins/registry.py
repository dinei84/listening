from plugins.extractors.pymupdf_extractor import PyMuPDFExtractor
from plugins.extractors.tesseract_ocr import TesseractOCR
from plugins.speakers.kokoro_speaker import KokoroSpeaker

EXTRACTORS = {
    "pymupdf": PyMuPDFExtractor,
    "tesseract": TesseractOCR,
}

SPEAKERS = {
    "kokoro": KokoroSpeaker,
}
