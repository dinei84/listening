from datetime import UTC, datetime

import pytest

from core import config as config_module
from core.models import AudioChunk, Book, ExtractedPage, Job
from plugins import registry as registry_module
from plugins.extractors.base import Extractor
from plugins.queues import sqlite_queue as sqlite_queue_module
from plugins.speakers.base import Speaker
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

    def synthesize(self, text, voice=None):
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path="/tmp/fake_worker.wav",
            duration_seconds=1.0,
            engine_used="fake_speaker",
        )


@pytest.fixture
def temp_paths(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(sqlite_queue_module, "DEFAULT_DB_PATH", db_path)
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads_module, "UPLOAD_DIR", upload_dir)
    return upload_dir


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


def _create_book_and_pdf(upload_dir, book_id="book-1"):
    upload_dir.mkdir(parents=True, exist_ok=True)
    uploads_module.pdf_path_for(book_id).write_bytes(b"%PDF-1.4 fake content")
    book = Book(
        id=book_id,
        title="Test Book",
        original_filename="test.pdf",
        status="uploaded",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    db_module.create_book(book)
    return book


def test_worker_process_job_marks_book_ready_on_success(
    temp_paths, fake_working_pipeline
):
    book = _create_book_and_pdf(temp_paths)
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    assert db_module.get_book(book.id).status == "ready"
    assert queue.get_job(job.id).status == "done"


def test_worker_process_job_marks_book_error_and_job_failed_on_pipeline_failure(
    temp_paths, fake_failing_pipeline
):
    book = _create_book_and_pdf(temp_paths)
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    assert db_module.get_book(book.id).status == "error"
    fetched_job = queue.get_job(job.id)
    assert fetched_job.status == "failed"
    assert fetched_job.error_message


def test_worker_run_worker_stops_after_max_iterations(
    temp_paths, fake_working_pipeline, monkeypatch
):
    sleep_calls = []
    monkeypatch.setattr(
        worker_tasks.time, "sleep", lambda seconds: sleep_calls.append(seconds)
    )

    worker_tasks.run_worker(poll_interval=0.01, max_iterations=3)

    assert len(sleep_calls) == 3
