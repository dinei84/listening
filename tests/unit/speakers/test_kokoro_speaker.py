import os

import pytest
import torch

from core.models import AudioChunk
from plugins.speakers.base import Speaker
from plugins.speakers.kokoro_speaker import KokoroSpeaker


def _fake_result(num_samples=100):
    class FakeResult:
        def __init__(self):
            self.output = type("Output", (), {"audio": torch.ones(1, num_samples)})()

    return FakeResult()


class FakePipeline:
    def __call__(self, text, voice, speed):
        yield _fake_result(num_samples=24000)


class RecordingPipeline:
    """Simula o Kokoro dividindo um texto longo sozinho: uma chamada, N Results."""

    def __init__(self, num_results=1):
        self.num_results = num_results
        self.calls = []

    def __call__(self, text, voice, speed):
        self.calls.append((text, voice, speed))
        for _ in range(self.num_results):
            yield _fake_result()


def test_speaker_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Speaker()


def test_kokoro_speaker_cost_per_char_is_zero():
    speaker = KokoroSpeaker()
    assert speaker.cost_per_char == 0.0


def test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro(
    monkeypatch,
):
    monkeypatch.setattr(KokoroSpeaker, "_get_pipeline", lambda self: FakePipeline())
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize("Hello world", voice="default")
    assert chunk.engine_used == "kokoro"
    assert isinstance(chunk, AudioChunk)


def test_kokoro_speaker_synthesize_writes_audio_file(monkeypatch):
    monkeypatch.setattr(KokoroSpeaker, "_get_pipeline", lambda self: FakePipeline())
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize("Hello world", voice="default")
    assert os.path.exists(chunk.file_path)
    assert chunk.file_path.endswith(".wav")
    os.remove(chunk.file_path)


def test_kokoro_speaker_calls_pipeline_directly_not_generate_from_tokens(monkeypatch):
    fake_pipeline = RecordingPipeline(num_results=1)
    monkeypatch.setattr(KokoroSpeaker, "_get_pipeline", lambda self: fake_pipeline)
    speaker = KokoroSpeaker()

    chunk = speaker.synthesize("Hello world", voice="default")

    assert fake_pipeline.calls == [("Hello world", "default", 1.0)]
    os.remove(chunk.file_path)


def test_kokoro_speaker_concatenates_multiple_results_into_single_audio_chunk(
    monkeypatch,
):
    fake_pipeline = RecordingPipeline(num_results=3)
    monkeypatch.setattr(KokoroSpeaker, "_get_pipeline", lambda self: fake_pipeline)
    speaker = KokoroSpeaker()

    chunk = speaker.synthesize("um texto longo o suficiente para virar 3 pedaços")

    assert isinstance(chunk, AudioChunk)
    assert len(fake_pipeline.calls) == 1
    assert chunk.duration_seconds == pytest.approx(300 / 24000)
    os.remove(chunk.file_path)
