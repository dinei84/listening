import os

import pytest

from core.models import AudioChunk
from storage import audio_store


@pytest.fixture
def temp_audio_store(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(audio_store, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store, "AUDIO_DIR", tmp_path / "audio")
    audio_store.init_db(db_path)
    return db_path


def _fake_source_chunk(
    tmp_path, sequence, name="chunk.wav", content=b"RIFF-fake-wav-bytes"
):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / f"{sequence}_{name}"
    source_path.write_bytes(content)
    return AudioChunk(
        chapter_id="chapter-1",
        sequence=sequence,
        file_path=str(source_path),
        duration_seconds=1.5,
        engine_used="fake_speaker",
    )


def test_audio_store_persists_chunks_with_book_id(temp_audio_store, tmp_path):
    chunk = _fake_source_chunk(tmp_path, sequence=0)

    persisted = audio_store.persist_chunks("book-1", [chunk], db_path=temp_audio_store)

    assert len(persisted) == 1
    fetched = audio_store.list_chunks("book-1", db_path=temp_audio_store)
    assert len(fetched) == 1
    assert fetched[0].sequence == 0


def test_audio_store_moves_file_to_stable_location(temp_audio_store, tmp_path):
    chunk = _fake_source_chunk(tmp_path, sequence=0)
    source_path = chunk.file_path

    persisted = audio_store.persist_chunks("book-1", [chunk], db_path=temp_audio_store)

    assert not os.path.exists(source_path)
    assert os.path.exists(persisted[0].file_path)
    assert persisted[0].file_path != source_path
    assert "book-1" in persisted[0].file_path


def test_audio_store_list_chunks_returns_ordered_by_sequence(
    temp_audio_store, tmp_path
):
    chunk_b = _fake_source_chunk(tmp_path, sequence=1, name="b.wav")
    chunk_a = _fake_source_chunk(tmp_path, sequence=0, name="a.wav")
    audio_store.persist_chunks("book-1", [chunk_b, chunk_a], db_path=temp_audio_store)

    chunks = audio_store.list_chunks("book-1", db_path=temp_audio_store)

    assert [c.sequence for c in chunks] == [0, 1]
