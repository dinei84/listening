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
