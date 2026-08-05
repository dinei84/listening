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


class FailingExtractor(Extractor):
    def supports(self, pdf_path):
        return True

    def extract(self, pdf_path, page_range=None):
        raise RuntimeError("boom")


class FakeSpeaker(Speaker):
    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
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


@pytest.fixture
def fake_failing_pipeline(monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FailingExtractor}
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


def test_get_books_status_includes_error_message_when_status_is_error(
    temp_paths, fake_failing_pipeline
):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        queue = sqlite_queue_module.SQLiteJobQueue()
        job = queue.claim_next()
        worker_tasks.process_job(job)

        status_response = client.get(f"/books/{book_id}/status")

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "error"
    assert body["error_message"]


def test_get_books_status_omits_error_message_when_status_is_not_error(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        status_response = client.get(f"/books/{book_id}/status")

    assert status_response.status_code == 200
    assert "error_message" not in status_response.json()


def test_get_books_status_returns_chunks_done_and_chunks_total(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        book_id = _create_and_process_book(client)
        status_response = client.get(f"/books/{book_id}/status")

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "ready"
    assert body["chunks_done"] == 1
    assert body["chunks_total"] == 1


def test_get_books_status_chunks_total_is_none_before_synthesis_starts(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]
        status_response = client.get(f"/books/{book_id}/status")

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "uploaded"
    assert body["chunks_total"] is None
    assert body["chunks_done"] == 0


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


def test_get_books_endpoint_returns_list_of_books(temp_paths, fake_working_pipeline):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        response = client.get("/books")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == book_id
    assert body[0]["title"] == "book.pdf"
    assert body[0]["status"] == "uploaded"
    assert "created_at" in body[0]


def test_get_books_endpoint_returns_empty_list_when_no_books(temp_paths):
    with TestClient(app) as client:
        response = client.get("/books")

    assert response.status_code == 200
    assert response.json() == []


def test_get_books_audio_returns_partial_chunks_while_synthesizing(
    temp_paths, monkeypatch
):
    MULTI_CHUNK_TEXT = "A" * 599 + ". " + "B" * 599 + ". " + "C" * 599 + "."

    class MultiChunkExtractor(Extractor):
        def supports(self, pdf_path):
            return True

        def extract(self, pdf_path, page_range=None):
            return [
                ExtractedPage(
                    page_number=1,
                    text=MULTI_CHUNK_TEXT,
                    confidence=1.0,
                    source="multi_chunk",
                )
            ]

    observations: dict = {}

    class ObservingSpeaker(Speaker):
        def __init__(self, client, book_id):
            self.call_count = 0
            self._client = client
            self._book_id = book_id

        @property
        def cost_per_char(self):
            return 0.0

        def synthesize(self, text, voice=None, lang_code=None):
            self.call_count += 1
            if self.call_count == 2:
                observations["status"] = self._client.get(
                    f"/books/{self._book_id}/status"
                )
                observations["audio"] = self._client.get(
                    f"/books/{self._book_id}/audio"
                )
            fd, path = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(b"RIFF-fake-wav-bytes")
            return AudioChunk(
                chapter_id="",
                sequence=0,
                file_path=path,
                duration_seconds=1.0,
                engine_used="observing_speaker",
            )

    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        speaker = ObservingSpeaker(client, book_id)
        monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
        monkeypatch.setattr(
            registry_module,
            "EXTRACTORS",
            {"fake_extractor": MultiChunkExtractor},
        )
        monkeypatch.setattr(
            registry_module,
            "SPEAKERS",
            {"fake_speaker": lambda: speaker},
        )

        queue = sqlite_queue_module.SQLiteJobQueue()
        job = queue.claim_next()
        worker_tasks.process_job(job)

        assert observations["status"].json()["status"] == "synthesizing"
        mid_audio = observations["audio"].json()
        assert len(mid_audio) == 1
        assert mid_audio[0]["sequence"] == 0

        final_response = client.get(f"/books/{book_id}/audio")
    assert len(final_response.json()) == 3
    assert final_response.json()[2]["sequence"] == 2


def test_delete_book_removes_book_chunks_jobs_and_pdf(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        queue = sqlite_queue_module.SQLiteJobQueue()
        job = queue.claim_next()
        worker_tasks.process_job(job)
        assert queue.get_job(job.id) is not None

        chunks_before = audio_store_module.list_chunks(book_id)
        assert len(chunks_before) == 1
        wav_path = chunks_before[0].file_path
        assert os.path.exists(wav_path)
        assert uploads_module.pdf_path_for(book_id).exists()

        response = client.delete(f"/books/{book_id}")

        assert response.status_code == 200
        assert db_module.get_book(book_id) is None
        assert audio_store_module.list_chunks(book_id) == []
        assert not os.path.exists(wav_path)
        assert not uploads_module.pdf_path_for(book_id).exists()
        assert queue.get_job(job.id) is None

        status_response = client.get(f"/books/{book_id}/status")
    assert status_response.status_code == 404


def test_delete_book_returns_404_for_unknown_book(temp_paths):
    with TestClient(app) as client:
        response = client.delete("/books/does-not-exist")

    assert response.status_code == 404


def test_delete_book_returns_409_while_processing(temp_paths, fake_working_pipeline):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        response = client.delete(f"/books/{book_id}")

    assert response.status_code == 409
    assert db_module.get_book(book_id) is not None


def test_delete_book_allowed_when_ready_or_error(temp_paths, fake_working_pipeline):
    with TestClient(app) as client:
        ready_id = _create_and_process_book(client)
        ready_response = client.delete(f"/books/{ready_id}")

        create_response = client.post("/books", files=_upload_files())
        error_id = create_response.json()["id"]
        db_module.update_book_status(error_id, "error", error_message="boom")
        error_response = client.delete(f"/books/{error_id}")

        assert ready_response.status_code == 200
        assert error_response.status_code == 200
        assert db_module.get_book(ready_id) is None
        assert db_module.get_book(error_id) is None

        list_response = client.get("/books")
    assert all(book["id"] not in (ready_id, error_id) for book in list_response.json())


def test_create_book_persists_chosen_language(temp_paths, fake_working_pipeline):
    files = _upload_files()
    files["language"] = (None, "pt")

    with TestClient(app) as client:
        response = client.post("/books", files=files)

    assert response.status_code == 200
    book = db_module.get_book(response.json()["id"])
    assert book.language == "pt"


def test_create_book_without_language_defaults_to_auto(
    temp_paths, fake_working_pipeline
):
    with TestClient(app) as client:
        response = client.post("/books", files=_upload_files())

    assert response.status_code == 200
    book = db_module.get_book(response.json()["id"])
    assert book.language is None


def test_create_book_with_invalid_language_falls_back_to_auto(
    temp_paths, fake_working_pipeline
):
    files = _upload_files()
    files["language"] = (None, "xx")

    with TestClient(app) as client:
        response = client.post("/books", files=files)

    assert response.status_code == 200
    book = db_module.get_book(response.json()["id"])
    assert book.language is None
