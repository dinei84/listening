from plugins.extractors.pymupdf_extractor import PyMuPDFExtractor
from plugins.extractors.tesseract_ocr import TesseractOCR
from plugins.queues.sqlite_queue import SQLiteJobQueue
from plugins.registry import EXTRACTORS, QUEUES, SPEAKERS
from plugins.speakers.kokoro_speaker import KokoroSpeaker


def test_registry_extractors_contains_pymupdf_and_tesseract():
    assert EXTRACTORS["pymupdf"] is PyMuPDFExtractor
    assert EXTRACTORS["tesseract"] is TesseractOCR


def test_registry_speakers_contains_kokoro():
    assert SPEAKERS["kokoro"] is KokoroSpeaker


def test_registry_queues_contains_sqlite():
    assert QUEUES["sqlite"] is SQLiteJobQueue
