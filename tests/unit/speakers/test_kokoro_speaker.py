import os

import pytest
import torch

from core.models import AudioChunk
from plugins.speakers.base import Speaker
from plugins.speakers.kokoro_speaker import KokoroSpeaker

PT_TEXT = (
    "A engenharia de seguranca requer metodos formais e verificacao rigorosa "
    "de protocolos criptograficos em sistemas distribuidos modernos."
)
EN_TEXT = (
    "Security engineering requires formal methods and rigorous verification "
    "of cryptographic protocols in modern distributed systems."
)
DE_TEXT = (
    "Die Sicherheitstechnik erfordert formale Methoden und eine strenge "
    "Ueberpruefung kryptographischer Protokolle in verteilten Systemen."
)


def _fake_result(num_samples=100):
    class FakeResult:
        def __init__(self):
            self.output = type("Output", (), {"audio": torch.ones(1, num_samples)})()

    return FakeResult()


class FakePipeline:
    """Dublê do KPipeline: registra cada síntese recebida."""

    def __init__(self, lang_code, num_results=1):
        self.lang_code = lang_code
        self.num_results = num_results
        self.calls = []

    def __call__(self, text, voice, speed):
        self.calls.append((text, voice, speed))
        for _ in range(self.num_results):
            yield _fake_result()


class PipelineFactory:
    """Substitui a construção real do KPipeline, registrando cada lang_code construído."""

    def __init__(self, num_results=1, unavailable=()):
        self.num_results = num_results
        self.unavailable = set(unavailable)
        self.built = []
        self.pipelines = {}

    def __call__(self, lang_code):
        self.built.append(lang_code)
        if lang_code in self.unavailable:
            raise ImportError(f"misaki[{lang_code}] nao instalado")
        pipeline = FakePipeline(lang_code, num_results=self.num_results)
        self.pipelines[lang_code] = pipeline
        return pipeline

    def single_call(self):
        """Devolve (lang_code, (text, voice, speed)) da única síntese feita."""
        all_calls = [
            (pipeline.lang_code, call)
            for pipeline in self.pipelines.values()
            for call in pipeline.calls
        ]
        assert len(all_calls) == 1, f"esperava 1 sintese, houve {len(all_calls)}"
        return all_calls[0]


@pytest.fixture
def pipeline_factory(monkeypatch):
    factory = PipelineFactory()
    monkeypatch.setattr(KokoroSpeaker, "_build_pipeline", factory)
    return factory


def test_speaker_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Speaker()


def test_kokoro_speaker_cost_per_char_is_zero():
    speaker = KokoroSpeaker()
    assert speaker.cost_per_char == 0.0


def test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro(
    pipeline_factory,
):
    chunk = KokoroSpeaker().synthesize(EN_TEXT)
    assert chunk.engine_used == "kokoro"
    assert isinstance(chunk, AudioChunk)
    os.remove(chunk.file_path)


def test_kokoro_speaker_synthesize_writes_audio_file(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(EN_TEXT)
    assert os.path.exists(chunk.file_path)
    assert chunk.file_path.endswith(".wav")
    os.remove(chunk.file_path)


def test_kokoro_speaker_concatenates_multiple_results_into_single_audio_chunk(
    monkeypatch,
):
    factory = PipelineFactory(num_results=3)
    monkeypatch.setattr(KokoroSpeaker, "_build_pipeline", factory)

    chunk = KokoroSpeaker().synthesize(EN_TEXT)

    assert isinstance(chunk, AudioChunk)
    assert factory.built == ["a"]
    assert chunk.duration_seconds == pytest.approx(300 / 24000)
    os.remove(chunk.file_path)


def test_kokoro_speaker_detects_portuguese_and_uses_correct_lang_code(
    pipeline_factory,
):
    chunk = KokoroSpeaker().synthesize(PT_TEXT)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pf_dora"
    os.remove(chunk.file_path)


def test_kokoro_speaker_detects_english_and_uses_correct_lang_code(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(EN_TEXT)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_falls_back_to_english_for_unmapped_language(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(DE_TEXT)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_falls_back_to_english_when_pipeline_is_unavailable(monkeypatch):
    factory = PipelineFactory(unavailable={"p"})
    monkeypatch.setattr(KokoroSpeaker, "_build_pipeline", factory)

    chunk = KokoroSpeaker().synthesize(PT_TEXT)

    lang_code, (_, voice, _) = factory.single_call()
    assert factory.built == ["p", "a"]
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_caches_pipeline_per_language(pipeline_factory):
    speaker = KokoroSpeaker()

    for text in (PT_TEXT, PT_TEXT, EN_TEXT, PT_TEXT):
        os.remove(speaker.synthesize(text).file_path)

    assert pipeline_factory.built == ["p", "a"]


def test_kokoro_speaker_handles_short_text_without_crashing(pipeline_factory):
    chunk = KokoroSpeaker().synthesize("Ola")

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_short_text_reuses_last_detected_language(pipeline_factory):
    speaker = KokoroSpeaker()

    os.remove(speaker.synthesize(PT_TEXT).file_path)
    os.remove(speaker.synthesize("Capitulo 2").file_path)

    assert pipeline_factory.built == ["p"]
    assert [call[0] for call in pipeline_factory.pipelines["p"].calls] == [
        PT_TEXT,
        "Capitulo 2",
    ]


def test_kokoro_speaker_explicit_voice_overrides_detected_default(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(PT_TEXT, voice="pm_alex")

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pm_alex"
    os.remove(chunk.file_path)


def test_kokoro_speaker_synthesize_uses_forced_lang_code_when_given(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(EN_TEXT, lang_code="p")

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pf_dora"
    os.remove(chunk.file_path)


def test_kokoro_speaker_synthesize_falls_back_to_detection_when_lang_code_is_none(
    pipeline_factory,
):
    chunk = KokoroSpeaker().synthesize(PT_TEXT, lang_code=None)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pf_dora"
    os.remove(chunk.file_path)
