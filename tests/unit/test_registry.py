from plugins.extractors.easyocr_extractor import EasyOCRExtractor
from plugins.extractors.pymupdf_extractor import PyMuPDFExtractor
from plugins.extractors.tesseract_ocr import TesseractOCR
from plugins.queues.sqlite_queue import SQLiteJobQueue
from plugins.registry import EXTRACTORS, QUEUES, SPEAKERS
from plugins.speakers.kokoro_speaker import KokoroSpeaker


def test_registry_extractors_contains_pymupdf_and_tesseract():
    assert EXTRACTORS["pymupdf"] is PyMuPDFExtractor
    assert EXTRACTORS["tesseract"] is TesseractOCR


def test_registry_extractors_contains_easyocr():
    assert EXTRACTORS["easyocr"] is EasyOCRExtractor


def test_registry_speakers_contains_kokoro():
    assert SPEAKERS["kokoro"] is KokoroSpeaker


def test_registry_queues_contains_sqlite():
    assert QUEUES["sqlite"] is SQLiteJobQueue


# --- OS-055: Speaker pago registrado -----------------------------------------


def test_registry_has_openai_speaker():
    """Até a OS-055 só havia Kokoro, e todo teste de expressividade usou ele por falta de opção."""
    from plugins.speakers.openai_speaker import OpenAISpeaker

    assert registry.SPEAKERS["openai"] is OpenAISpeaker


def test_empty_cloud_speaker_placeholder_was_removed():
    """cloud_speaker.py tinha 0 bytes e sugeria uma capacidade que não existia (item 52)."""
    import pathlib

    assert not pathlib.Path("plugins/speakers/cloud_speaker.py").exists()
