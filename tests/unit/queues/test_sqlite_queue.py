import pytest

from core.models import Job
from plugins.queues.base import JobQueue
from plugins.queues.sqlite_queue import SQLiteJobQueue


def _job(job_id: str = "job-1", book_id: str = "book-1", stage: str = "extract") -> Job:
    return Job(id=job_id, book_id=book_id, stage=stage, status="queued")


def test_job_queue_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        JobQueue()


def test_sqlite_queue_enqueue_sets_status_queued(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    job = _job()

    queue.enqueue(job)
    fetched = queue.get_job(job.id)

    assert fetched is not None
    assert fetched.status == "queued"


def test_sqlite_queue_claim_next_returns_and_marks_running(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    job = _job()
    queue.enqueue(job)

    claimed = queue.claim_next()

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "running"
    assert queue.get_job(job.id).status == "running"


def test_sqlite_queue_claim_next_returns_none_when_empty(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))

    assert queue.claim_next() is None


def test_sqlite_queue_claim_next_does_not_return_same_job_twice(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job())

    first = queue.claim_next()
    second = queue.claim_next()

    assert first is not None
    assert second is None


def test_sqlite_queue_mark_done_updates_status(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    job = _job()
    queue.enqueue(job)
    queue.claim_next()

    queue.mark_done(job.id)

    assert queue.get_job(job.id).status == "done"


def test_sqlite_queue_mark_failed_updates_status_and_error_message(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    job = _job()
    queue.enqueue(job)
    queue.claim_next()

    queue.mark_failed(job.id, "boom")

    fetched = queue.get_job(job.id)
    assert fetched.status == "failed"
    assert fetched.error_message == "boom"


def test_sqlite_queue_get_job_returns_none_for_unknown_id(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))

    assert queue.get_job("does-not-exist") is None
