import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core import config as config_module
from core.models import AudioChunk, ExtractedPage
from plugins import registry as registry_module
from plugins.extractors.base import Extractor
from plugins.queues import sqlite_queue as sqlite_queue_module
from plugins.speakers.base import Speaker
from storage import audio_store as audio_store_module
from storage import db as db_module
from storage import uploads as uploads_module
from worker import tasks as worker_tasks


class FakeConfig:
    def __init__(
        self, extractor="fake_extractor", speaker="fake_speaker", queue="sqlite"
    ):
        self.extractor = extractor
        self.speaker = speaker
        self.queue = queue


class FakeExtractor(Extractor):
    def supports(self, pdf_path):
        return True

    def extract(self, pdf_path, page_range=None):
        return [
            ExtractedPage(
                page_number=1,
                text="Some extracted text.",
                confidence=1.0,
                source="fake_extractor",
            )
        ]


class FakeSpeaker(Speaker):
    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None):
        fd, path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(b"RIFF-fake-wav-bytes")
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=path,
            duration_seconds=1.0,
            engine_used="fake_speaker",
        )


def _upload_files():
    return {
        "file": ("book.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")
    }


def _create_and_process_book(client):
    create_response = client.post("/books", files=_upload_files())
    book_id = create_response.json()["id"]
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = queue.claim_next()
    worker_tasks.process_job(job)
    return book_id


@pytest.fixture
def temp_paths(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_books.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(sqlite_queue_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "AUDIO_DIR", tmp_path / "audio")
    audio_store_module.init_db(db_path)
    monkeypatch.setattr(uploads_module, "UPLOAD_DIR", tmp_path / "uploads")
    return db_path


@pytest.fixture
def fake_working_pipeline(monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": FakeSpeaker})


def test_post_books_returns_immediately_without_running_pipeline(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        response = client.post("/books", files=_upload_files())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "uploaded"
    assert "id" in body


def test_post_books_enqueues_a_job_for_the_created_book(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        response = client.post("/books", files=_upload_files())

    book_id = response.json()["id"]
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = queue.claim_next()

    assert job is not None
    assert job.book_id == book_id
    assert job.stage == "process"


def test_get_books_status_returns_persisted_status(temp_paths, fake_working_pipeline):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        status_response = client.get(f"/books/{book_id}/status")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "uploaded"


def test_get_books_status_returns_404_for_unknown_id(temp_paths):
    with TestClient(app) as client:
        response = client.get("/books/does-not-exist/status")

    assert response.status_code == 404


def test_end_to_end_post_then_process_job_then_status_reflects_ready(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        queue = sqlite_queue_module.SQLiteJobQueue()
        job = queue.claim_next()
        worker_tasks.process_job(job)

        status_response = client.get(f"/books/{book_id}/status")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "ready"


def test_get_books_audio_returns_ordered_chunk_list(temp_paths, fake_working_pipeline):
    with TestClient(app) as client:
        book_id = _create_and_process_book(client)
        response = client.get(f"/books/{book_id}/audio")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["sequence"] == 0


def test_get_books_audio_returns_404_for_unknown_book(temp_paths):
    with TestClient(app) as client:
        response = client.get("/books/does-not-exist/audio")

    assert response.status_code == 404


def test_get_book_audio_chunk_serves_file_bytes(temp_paths, fake_working_pipeline):
    with TestClient(app) as client:
        book_id = _create_and_process_book(client)
        response = client.get(f"/books/{book_id}/audio/0")

    assert response.status_code == 200
    assert response.content == b"RIFF-fake-wav-bytes"
    assert response.headers["content-type"].startswith("audio/")


def test_get_book_audio_chunk_returns_404_for_unknown_sequence(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        book_id = _create_and_process_book(client)
        response = client.get(f"/books/{book_id}/audio/999")

    assert response.status_code == 404
