import os

import pytest
from core.models import AudioChunk
from plugins.extractors.base import Extractor
from plugins.speakers.base import Speaker
from plugins.speakers.kokoro_speaker import KokoroSpeaker


def test_speaker_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Speaker()


def test_kokoro_speaker_cost_per_char_is_zero():
    speaker = KokoroSpeaker()
    assert speaker.cost_per_char == 0.0


def test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro(
    tmp_path,
):
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize("Hello world", voice="default")
    assert chunk.engine_used == "kokoro"
    assert isinstance(chunk, AudioChunk)


def test_kokoro_speaker_synthesize_writes_audio_file(tmp_path):
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize("Hello world", voice="default")
    assert os.path.exists(chunk.file_path)
    assert chunk.file_path.startswith(str(tmp_path))