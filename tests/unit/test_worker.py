import logging
import os
import tempfile
from datetime import UTC, datetime

import pytest

from core import config as config_module
from core.models import AudioChunk, Book, ExtractedPage, Job
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


# Três "sentenças" de 600 caracteres cada: com max_chars=1000 nenhuma cabe
# junto de outra, então o chunker produz exatamente 3 chunks.
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
                source="multi_chunk_extractor",
            )
        ]


class RecordingSpeaker(Speaker):
    """Speaker dublê que registra, a cada síntese, quantos chunks já estão no banco, o status do Book e o chunk_total dele."""

    def __init__(self, book_id):
        self.book_id = book_id
        self.chunks_in_db_at_call = []
        self.statuses_at_call = []
        self.chunk_total_at_call = []
        self.lang_codes = []

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.chunks_in_db_at_call.append(
            len(audio_store_module.list_chunks(self.book_id))
        )
        fetched = db_module.get_book(self.book_id)
        self.statuses_at_call.append(fetched.status)
        self.chunk_total_at_call.append(fetched.chunk_total)
        self.lang_codes.append(lang_code)
        fd, path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(b"RIFF-fake-wav-bytes")
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=path,
            duration_seconds=1.0,
            engine_used="recording_speaker",
        )


class CountingSpeaker(Speaker):
    """Speaker dublê que registra o texto de cada chamada — usado para provar o que NÃO foi sintetizado."""

    def __init__(self):
        self.synthesized_texts = []

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.synthesized_texts.append(text)
        fd, path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(b"RIFF-fake-wav-bytes")
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=path,
            duration_seconds=1.0,
            engine_used="counting_speaker",
        )


@pytest.fixture
def temp_paths(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(sqlite_queue_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "AUDIO_DIR", tmp_path / "audio")
    audio_store_module.init_db(db_path)
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


@pytest.fixture
def fake_multi_chunk_pipeline(monkeypatch):
    """Pipeline dublê de 3 chunks com um CountingSpeaker; devolve o speaker para inspeção."""
    speaker = CountingSpeaker()
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": MultiChunkExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": lambda: speaker})
    return speaker


def _persist_previous_chunk(book_id, sequence):
    """Simula um AudioChunk deixado no banco por uma tentativa anterior interrompida."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    with os.fdopen(fd, "wb") as f:
        f.write(b"RIFF-chunk-de-tentativa-anterior")
    audio_store_module.persist_chunks(
        book_id,
        [
            AudioChunk(
                chapter_id="job-1",
                sequence=sequence,
                file_path=path,
                duration_seconds=1.0,
                engine_used="previous_run",
            )
        ],
    )


def _create_book_and_pdf(upload_dir, book_id="book-1", language=None):
    upload_dir.mkdir(parents=True, exist_ok=True)
    uploads_module.pdf_path_for(book_id).write_bytes(b"%PDF-1.4 fake content")
    db_module.init_db()
    book = Book(
        id=book_id,
        title="Test Book",
        original_filename="test.pdf",
        status="uploaded",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        language=language,
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


def test_worker_process_job_persists_audio_chunks(temp_paths, fake_working_pipeline):
    book = _create_book_and_pdf(temp_paths)
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    chunks = audio_store_module.list_chunks(book.id)
    assert len(chunks) == 1
    assert chunks[0].sequence == 0
    assert os.path.exists(chunks[0].file_path)


def test_worker_process_job_persists_chunks_incrementally(temp_paths, monkeypatch):
    book = _create_book_and_pdf(temp_paths)
    speaker = RecordingSpeaker(book.id)
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": MultiChunkExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": lambda: speaker})
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    assert speaker.chunks_in_db_at_call == [0, 1, 2]
    chunks = audio_store_module.list_chunks(book.id)
    assert len(chunks) == 3
    assert db_module.get_book(book.id).status == "ready"


def test_worker_process_job_sets_book_status_to_synthesizing_before_ready(
    temp_paths, monkeypatch
):
    book = _create_book_and_pdf(temp_paths)
    speaker = RecordingSpeaker(book.id)
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": MultiChunkExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": lambda: speaker})
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    assert len(speaker.statuses_at_call) == 3
    assert all(s == "synthesizing" for s in speaker.statuses_at_call)
    assert db_module.get_book(book.id).status == "ready"


def test_worker_run_worker_requeues_orphaned_jobs_on_startup(
    temp_paths, fake_working_pipeline, monkeypatch
):
    book = _create_book_and_pdf(temp_paths)
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)
    # Worker anterior morreu no meio: o Job ficou órfão em "running".
    queue.claim_next()
    assert queue.get_job(job.id).status == "running"
    monkeypatch.setattr(worker_tasks.time, "sleep", lambda seconds: None)

    worker_tasks.run_worker(poll_interval=0.01, max_iterations=1)

    assert queue.get_job(job.id).status == "done"
    assert db_module.get_book(book.id).status == "ready"


def test_worker_process_job_skips_already_persisted_chunks(
    temp_paths, fake_multi_chunk_pipeline
):
    speaker = fake_multi_chunk_pipeline
    book = _create_book_and_pdf(temp_paths)
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)
    # Tentativa anterior sintetizou os chunks 0 e 1 antes de ser interrompida.
    _persist_previous_chunk(book.id, 0)
    _persist_previous_chunk(book.id, 1)

    worker_tasks.process_job(job)

    assert len(speaker.synthesized_texts) == 1
    assert speaker.synthesized_texts[0].startswith("C")
    chunks = audio_store_module.list_chunks(book.id)
    assert [c.sequence for c in chunks] == [0, 1, 2]
    assert [c.engine_used for c in chunks] == [
        "previous_run",
        "previous_run",
        "counting_speaker",
    ]
    assert db_module.get_book(book.id).status == "ready"
    assert queue.get_job(job.id).status == "done"


def test_worker_process_job_handles_chunk_count_inconsistency_safely(
    temp_paths, fake_multi_chunk_pipeline, caplog
):
    speaker = fake_multi_chunk_pipeline
    book = _create_book_and_pdf(temp_paths)
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)
    # O texto re-extraído produz 3 chunks (sequences 0..2), mas existe um chunk
    # persistido em sequence 5 — o chunking mudou desde a tentativa anterior.
    _persist_previous_chunk(book.id, 5)

    with caplog.at_level(logging.ERROR):
        worker_tasks.process_job(job)

    assert speaker.synthesized_texts == []
    fetched_book = db_module.get_book(book.id)
    assert fetched_book.status == "error"
    assert "inconsisten" in fetched_book.error_message.lower()
    fetched_job = queue.get_job(job.id)
    assert fetched_job.status == "failed"
    assert "inconsisten" in fetched_job.error_message.lower()
    assert any("inconsisten" in record.message.lower() for record in caplog.records)
    # Caminho seguro: nada do que já existia foi apagado silenciosamente.
    assert [c.sequence for c in audio_store_module.list_chunks(book.id)] == [5]


def test_worker_process_job_sets_book_chunk_total_before_synthesizing(
    temp_paths, monkeypatch
):
    book = _create_book_and_pdf(temp_paths)
    assert book.chunk_total is None
    speaker = RecordingSpeaker(book.id)
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": MultiChunkExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": lambda: speaker})
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    assert speaker.chunk_total_at_call == [3, 3, 3]
    assert db_module.get_book(book.id).chunk_total == 3


def test_worker_process_job_passes_book_language_to_pipeline(temp_paths, monkeypatch):
    book = _create_book_and_pdf(temp_paths, language="pt")
    speaker = RecordingSpeaker(book.id)
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": MultiChunkExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": lambda: speaker})
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    assert speaker.lang_codes == ["p", "p", "p"]
    assert db_module.get_book(book.id).status == "ready"


def test_worker_process_job_passes_none_lang_code_without_book_language(
    temp_paths, monkeypatch
):
    book = _create_book_and_pdf(temp_paths)
    speaker = RecordingSpeaker(book.id)
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": MultiChunkExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": lambda: speaker})
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    assert speaker.lang_codes == [None, None, None]
    assert db_module.get_book(book.id).status == "ready"
