from core import config as config_module
from core import pipeline
from core.models import AudioChunk, ExtractedPage
from plugins import registry as registry_module
from plugins.extractors.base import Extractor
from plugins.speakers.base import Speaker


class FakeConfig:
    def __init__(
        self,
        extractor="fake_primary",
        speaker="fake_speaker",
        max_cost_per_book=None,
        fallback_speaker="kokoro",
        retry_max_attempts=3,
        retry_base_delay_seconds=1.0,
        retry_max_delay_seconds=30.0,
    ):
        self.extractor = extractor
        self.speaker = speaker
        self.max_cost_per_book = max_cost_per_book
        self.fallback_speaker = fallback_speaker
        self.retry_max_attempts = retry_max_attempts
        self.retry_base_delay_seconds = retry_base_delay_seconds
        self.retry_max_delay_seconds = retry_max_delay_seconds


class FakePrimaryExtractor(Extractor):
    def __init__(self, supports_result=True):
        self.supports_result = supports_result

    def supports(self, pdf_path):
        return self.supports_result

    def extract(self, pdf_path, page_range=None):
        return [
            ExtractedPage(
                page_number=1,
                text="primary text",
                confidence=1.0,
                source="fake_primary",
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


class FakeTwoPageExtractor(Extractor):
    def supports(self, pdf_path):
        return True

    def extract(self, pdf_path, page_range=None):
        return [
            ExtractedPage(
                page_number=1,
                text="HEADER\nFirst page body.",
                confidence=1.0,
                source="fake_pages",
            ),
            ExtractedPage(
                page_number=2,
                text="HEADER\nSecond page body.",
                confidence=1.0,
                source="fake_pages",
            ),
        ]


class FakeSpeaker(Speaker):
    def __init__(self):
        self.call_count = 0
        self.lang_codes = []
        self.voices = []

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.call_count += 1
        self.lang_codes.append(lang_code)
        self.voices.append(voice)
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=f"/tmp/fake_{self.call_count}.wav",
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
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    chunks = pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20)

    assert len(chunks) == 3
    assert all(isinstance(c, AudioChunk) for c in chunks)
    assert all(c.chapter_id == "ch1" for c in chunks)
    assert all(c.engine_used == "fake_speaker" for c in chunks)


def test_extract_clean_text_combines_extraction_and_cleaning(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(extractor="fake_pages")
    )
    monkeypatch.setattr(
        registry_module,
        "EXTRACTORS",
        {"fake_pages": FakeTwoPageExtractor, "tesseract": FakeTesseractExtractor},
    )

    result = pipeline.extract_clean_text("fake.pdf")

    assert result == "First page body.\nSecond page body."


def test_synthesize_text_calls_speaker_once_per_chunk(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20)

    assert fake_speaker.call_count == 3


def test_synthesize_text_assigns_incrementing_sequence_per_chunk(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    chunks = pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20)

    assert [c.sequence for c in chunks] == [0, 1, 2]


def test_synthesize_text_sets_chapter_id_on_every_chunk(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    chunks = pipeline.synthesize_text(text, chapter_id="chapter-42", max_chars=20)

    assert all(c.chapter_id == "chapter-42" for c in chunks)


def test_synthesize_text_returns_empty_list_for_empty_text_without_calling_speaker(
    monkeypatch,
):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    result = pipeline.synthesize_text("   ", chapter_id="ch1")

    assert result == []
    assert fake_speaker.call_count == 0


def test_synthesize_text_calls_on_chunk_for_each_chunk(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    received: list[AudioChunk] = []

    class TimingSpeaker(FakeSpeaker):
        def __init__(self):
            super().__init__()
            self.received_count_at_call: list[int] = []

        def synthesize(self, text, voice=None, lang_code=None):
            self.received_count_at_call.append(len(received))
            return super().synthesize(text, voice, lang_code)

    timing_speaker = TimingSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: timing_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    chunks = pipeline.synthesize_text(
        text, chapter_id="ch1", max_chars=20, on_chunk=received.append
    )

    assert len(received) == 3
    assert [c.sequence for c in received] == [0, 1, 2]
    assert all(c.chapter_id == "ch1" for c in received)
    assert received == chunks
    # Cada on_chunk disparou antes da síntese do chunk seguinte.
    assert timing_speaker.received_count_at_call == [0, 1, 2]


def test_synthesize_text_skips_sequences_already_synthesized(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    chunks = pipeline.synthesize_text(
        text, chapter_id="ch1", max_chars=20, skip_sequences={0, 1}
    )

    assert fake_speaker.call_count == 1
    assert [c.sequence for c in chunks] == [2]


def test_count_text_chunks_matches_number_of_synthesized_chunks(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": FakeSpeaker})

    text = "Sentence one. Sentence two. Sentence three."

    assert pipeline.count_text_chunks(text, max_chars=20) == 3
    assert pipeline.count_text_chunks("") == 0


def test_synthesize_text_returns_full_list_when_on_chunk_is_none(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    chunks = pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20)

    assert len(chunks) == 3
    assert [c.sequence for c in chunks] == [0, 1, 2]
    assert all(c.chapter_id == "ch1" for c in chunks)
    assert fake_speaker.call_count == 3


def test_synthesize_text_passes_lang_code_to_speaker(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20, lang_code="p")

    assert fake_speaker.lang_codes == ["p", "p", "p"]


def test_synthesize_text_passes_none_lang_code_by_default(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20)

    assert fake_speaker.lang_codes == [None, None, None]


# --- OS-053: escolha de voz --------------------------------------------------


def test_synthesize_text_passes_voice_to_speaker(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20, voice="pm_alex")

    assert fake_speaker.voices == ["pm_alex", "pm_alex", "pm_alex"]


def test_synthesize_text_without_voice_uses_language_default(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="fake_speaker")
    )
    fake_speaker = FakeSpeaker()
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: fake_speaker}
    )

    text = "Sentence one. Sentence two. Sentence three."
    pipeline.synthesize_text(text, chapter_id="ch1", max_chars=20, lang_code="p")

    assert fake_speaker.voices == [None, None, None]
