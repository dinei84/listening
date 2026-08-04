from plugins.extractors.easyocr_extractor import EasyOCRExtractor
from plugins.extractors.pymupdf_extractor import PyMuPDFExtractor
from plugins.extractors.tesseract_ocr import TesseractOCR
from plugins.queues.sqlite_queue import SQLiteJobQueue
from plugins.speakers.kokoro_speaker import KokoroSpeaker

EXTRACTORS = {
    "pymupdf": PyMuPDFExtractor,
    "tesseract": TesseractOCR,
    "easyocr": EasyOCRExtractor,
}

SPEAKERS = {
    "kokoro": KokoroSpeaker,
}

QUEUES = {
    "sqlite": SQLiteJobQueue,
}
