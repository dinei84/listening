import sqlite3

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


def test_sqlite_queue_requeue_orphaned_resets_running_jobs_to_queued(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.enqueue(_job("job-2"))
    queue.claim_next()
    queue.claim_next()

    requeued = queue.requeue_orphaned()

    assert [job.id for job in requeued] == ["job-1", "job-2"]
    assert all(job.status == "queued" for job in requeued)
    assert queue.get_job("job-1").status == "queued"
    assert queue.get_job("job-2").status == "queued"
    # Depois do resete, o Job volta a ser visível para claim_next().
    assert queue.claim_next().id == "job-1"


def test_sqlite_queue_requeue_orphaned_ignores_queued_and_done_jobs(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-done"))
    queue.enqueue(_job("job-failed"))
    queue.enqueue(_job("job-queued"))
    queue.claim_next()
    queue.mark_done("job-done")
    queue.claim_next()
    queue.mark_failed("job-failed", "boom")

    requeued = queue.requeue_orphaned()

    assert requeued == []
    assert queue.get_job("job-done").status == "done"
    assert queue.get_job("job-failed").status == "failed"
    assert queue.get_job("job-queued").status == "queued"


def test_sqlite_queue_requeue_orphaned_returns_empty_list_when_no_running_jobs(
    tmp_path,
):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))

    assert queue.requeue_orphaned() == []


def test_sqlite_queue_delete_jobs_for_book_removes_only_that_books_jobs(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-a1", book_id="book-a"))
    queue.enqueue(_job("job-a2", book_id="book-a"))
    queue.enqueue(_job("job-b1", book_id="book-b"))

    queue.delete_jobs_for_book("book-a")

    assert queue.get_job("job-a1") is None
    assert queue.get_job("job-a2") is None
    assert queue.get_job("job-b1") is not None


def test_sqlite_queue_delete_jobs_for_book_is_noop_for_unknown_book(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1", book_id="book-a"))

    queue.delete_jobs_for_book("book-unknown")

    assert queue.get_job("job-1") is not None


def test_sqlite_queue_claim_next_keeps_fifo_when_no_priority_set(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.enqueue(_job("job-2"))

    first = queue.claim_next()
    second = queue.claim_next()

    assert first.id == "job-1"
    assert second.id == "job-2"


def test_sqlite_queue_prioritize_makes_job_claimed_first(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.enqueue(_job("job-2"))

    queue.prioritize("job-2")

    first = queue.claim_next()
    second = queue.claim_next()
    assert first.id == "job-2"
    assert second.id == "job-1"


def test_sqlite_queue_prioritize_priority_strictly_greater_than_running(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.enqueue(_job("job-2"))
    queue.prioritize("job-1")
    queue.claim_next()

    queue.prioritize("job-2")

    assert queue.get_job("job-2").priority > queue.get_job("job-1").priority
    assert queue.should_yield("job-1") is True


def test_sqlite_queue_should_yield_true_when_higher_priority_queued(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.enqueue(_job("job-2"))
    queue.prioritize("job-2")

    assert queue.should_yield("job-1") is True


def test_sqlite_queue_should_yield_false_when_no_higher_priority(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.enqueue(_job("job-2"))

    assert queue.should_yield("job-1") is False


def test_sqlite_queue_should_yield_false_for_unknown_job(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))

    assert queue.should_yield("does-not-exist") is False


def test_sqlite_queue_get_job_returns_priority(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))

    queue.prioritize("job-1")

    assert queue.get_job("job-1").priority == 1


def test_sqlite_queue_requeue_preserves_priority(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.prioritize("job-1")
    queue.claim_next()

    queue.requeue("job-1")

    fetched = queue.get_job("job-1")
    assert fetched.status == "queued"
    assert fetched.priority == 1


def test_sqlite_queue_requeue_does_not_affect_other_jobs(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1"))
    queue.enqueue(_job("job-2"))
    queue.claim_next()

    queue.requeue("job-1")

    assert queue.get_job("job-2").status == "queued"
    assert queue.get_job("job-1").status == "queued"


def test_sqlite_queue_get_job_for_book_returns_most_recent_job(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1", book_id="book-a"))
    queue.enqueue(_job("job-2", book_id="book-a"))

    job = queue.get_job_for_book("book-a")

    assert job is not None
    assert job.id == "job-2"


def test_sqlite_queue_get_job_for_book_returns_none_for_unknown_book(tmp_path):
    queue = SQLiteJobQueue(str(tmp_path / "test.db"))
    queue.enqueue(_job("job-1", book_id="book-a"))

    assert queue.get_job_for_book("book-unknown") is None


def test_init_db_upgrades_legacy_jobs_table(tmp_path):
    """Um banco no formato da OS-017 (jobs sem priority) ganha a coluna nova sem perder linhas."""
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("""
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            book_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT
        )
        """)
    conn.execute(
        "INSERT INTO jobs (id, book_id, stage, status, error_message) "
        "VALUES ('j1', 'book-a', 'extract', 'queued', NULL)"
    )
    conn.commit()
    conn.close()

    queue = SQLiteJobQueue(caminho)

    job = queue.get_job("j1")
    assert job is not None
    assert job.id == "j1"
    assert job.priority == 0

    conn = sqlite3.connect(caminho)
    colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(jobs)")}
    conn.close()
    assert colunas >= {"id", "book_id", "stage", "status", "error_message", "priority"}
