from plugins.extractors.easyocr_extractor import EasyOCRExtractor
from plugins.extractors.pymupdf_extractor import PyMuPDFExtractor
from plugins.extractors.tesseract_ocr import TesseractOCR
from plugins.normalizers.base import NoOpNormalizer
from plugins.normalizers.llm_normalizer import from_config as _llm_from_config
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


# Normalizadores de texto (OS-038). "noop" é o padrão do nível simples: não toca a
# rede e não custa nada. "llm" é o nível médio — provedor definido em config.yaml.
NORMALIZERS = {
    "noop": NoOpNormalizer,
    "llm": _llm_from_config,
}
