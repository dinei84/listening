import os

import pytest
import torch

from core.models import AudioChunk
from plugins.speakers.base import Speaker
from plugins.speakers.kokoro_speaker import KokoroSpeaker


class FakePipeline:
    def generate_from_tokens(self, text, voice, speed):
        class FakeResult:
            def __init__(self):
                self.output = type("Output", (), {"audio": torch.zeros(1, 24000)})()

        yield FakeResult()


class SplitAwarePipeline:
    """Simula o comportamento real do Kokoro: rejeita texto acima de um limite de caracteres."""

    def __init__(self, limit):
        self.limit = limit
        self.calls = []

    def generate_from_tokens(self, text, voice, speed):
        self.calls.append(text)
        if len(text) > self.limit:
            raise ValueError(f"Phoneme string too long: {len(text)} > {self.limit}")

        class FakeResult:
            def __init__(self):
                self.output = type("Output", (), {"audio": torch.ones(1, 100)})()

        yield FakeResult()


class AlwaysRejectingPipeline:
    def generate_from_tokens(self, text, voice, speed):
        raise ValueError(f"Phoneme string too long: {len(text)} > 510")


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


def test_kokoro_speaker_splits_and_retries_on_phoneme_limit_error(monkeypatch):
    fake_pipeline = SplitAwarePipeline(limit=20)
    monkeypatch.setattr(KokoroSpeaker, "_get_pipeline", lambda self: fake_pipeline)
    speaker = KokoroSpeaker()
    long_text = "one two three four five six seven eight nine ten"

    chunk = speaker.synthesize(long_text, voice="default")

    assert isinstance(chunk, AudioChunk)
    assert len(fake_pipeline.calls) > 1
    assert all(len(call) <= 20 for call in fake_pipeline.calls)
    os.remove(chunk.file_path)


def test_kokoro_speaker_returns_single_audio_chunk_after_split_retry(monkeypatch):
    fake_pipeline = SplitAwarePipeline(limit=20)
    monkeypatch.setattr(KokoroSpeaker, "_get_pipeline", lambda self: fake_pipeline)
    speaker = KokoroSpeaker()

    chunk = speaker.synthesize(
        "one two three four five six seven eight nine ten", voice="default"
    )

    assert isinstance(chunk, AudioChunk)
    assert chunk.duration_seconds > 0
    os.remove(chunk.file_path)


def test_kokoro_speaker_gives_up_with_clear_error_if_split_does_not_help(monkeypatch):
    monkeypatch.setattr(
        KokoroSpeaker, "_get_pipeline", lambda self: AlwaysRejectingPipeline()
    )
    speaker = KokoroSpeaker()

    with pytest.raises(RuntimeError, match="fonema"):
        speaker.synthesize("supercalifragilisticexpialidocious", voice="default")
