from core import config as config_module
from core import pipeline
from core.models import AudioChunk, ExtractedPage
from plugins import registry as registry_module
from plugins.extractors.base import Extractor
from plugins.speakers.base import Speaker


class FakeConfig:
    def __init__(self, extractor="fake_primary", speaker="fake_speaker"):
        self.extractor = extractor
        self.speaker = speaker


class FakePrimaryExtractor(Extractor):
    def __init__(self, supports_result=True):
        self.supports_result = supports_result

    def supports(self, pdf_path):
        return self.supports_result

    def extract(self, pdf_path, page_range=None):
        return [
            ExtractedPage(
                page_number=1, text="primary text", confidence=1.0, source="fake_primary"
            )
        ]


class FakeTesseractExtractor(Extractor):
    def __init__(self, confidence=0.2):
        self.confidence = confidence

    def supports(self, pdf_path):
        return True

    def extract(self, pdf_path, page_range=None):
        return [
            ExtractedPage(
                page_number=1,
                text="ocr text",
                confidence=self.confidence,
                source="fake_tesseract",
            )
        ]


class FakeSpeaker(Speaker):
    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None):
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path="/tmp/fake.wav",
            duration_seconds=1.0,
            engine_used="fake_speaker",
        )


def test_pipeline_uses_primary_extractor_when_supports_true(monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module,
        "EXTRACTORS",
        {
            "fake_primary": lambda: FakePrimaryExtractor(supports_result=True),
            "tesseract": FakeTesseractExtractor,
        },
    )

    pages = pipeline.extract_with_fallback("fake.pdf")

    assert pages[0].source == "fake_primary"


def test_pipeline_falls_back_to_tesseract_when_primary_supports_false(monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module,
        "EXTRACTORS",
        {
            "fake_primary": lambda: FakePrimaryExtractor(supports_result=False),
            "tesseract": FakeTesseractExtractor,
        },
    )

    pages = pipeline.extract_with_fallback("fake.pdf")

    assert pages[0].source == "fake_tesseract"


def test_pipeline_exposes_confidence_even_when_low(monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module,
        "EXTRACTORS",
        {
            "fake_primary": lambda: FakePrimaryExtractor(supports_result=False),
            "tesseract": lambda: FakeTesseractExtractor(confidence=0.1),
        },
    )

    pages = pipeline.extract_with_fallback("fake.pdf")

    assert pages[0].confidence == 0.1


def test_pipeline_synthesizes_extracted_text_with_configured_speaker(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": FakeSpeaker})

    chunks = pipeline.synthesize_text("some extracted text", chapter_id="ch1")

    assert len(chunks) == 1
    assert isinstance(chunks[0], AudioChunk)
    assert chunks[0].chapter_id == "ch1"
    assert chunks[0].engine_used == "fake_speaker"
