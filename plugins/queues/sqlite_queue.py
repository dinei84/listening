import sqlite3

from core.models import Job
from plugins.queues.base import JobQueue

DEFAULT_DB_PATH = "books.db"


class SQLiteJobQueue(JobQueue):
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path if db_path is not None else DEFAULT_DB_PATH
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    book_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
                """)
            conn.commit()
        finally:
            conn.close()

    def enqueue(self, job: Job) -> None:
        """Insere um Job na fila com status 'queued'."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO jobs (id, book_id, stage, status, error_message) "
                "VALUES (?, ?, ?, 'queued', ?)",
                (job.id, job.book_id, job.stage, job.error_message),
            )
            conn.commit()
        finally:
            conn.close()

    def claim_next(self) -> Job | None:
        """Reivindica atomicamente o próximo Job 'queued', marcando como 'running'."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id, book_id, stage, error_message FROM jobs "
                "WHERE status = 'queued' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            conn.execute(
                "UPDATE jobs SET status = 'running' WHERE id = ? AND status = 'queued'",
                (row[0],),
            )
            conn.commit()
        finally:
            conn.close()

        return Job(
            id=row[0],
            book_id=row[1],
            stage=row[2],
            status="running",
            error_message=row[3],
        )

    def mark_done(self, job_id: str) -> None:
        """Marca um Job como concluído ('done')."""
        conn = self._connect()
        try:
            conn.execute("UPDATE jobs SET status = 'done' WHERE id = ?", (job_id,))
            conn.commit()
        finally:
            conn.close()

    def mark_failed(self, job_id: str, error_message: str) -> None:
        """Marca um Job como falho ('failed'), registrando a mensagem de erro."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE jobs SET status = 'failed', error_message = ? WHERE id = ?",
                (error_message, job_id),
            )
            conn.commit()
        finally:
            conn.close()

    def requeue_orphaned(self) -> list[Job]:
        """Reseta para 'queued' todo Job preso em 'running' e devolve os Jobs resetados."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT id, book_id, stage, error_message FROM jobs "
                "WHERE status = 'running' ORDER BY rowid"
            ).fetchall()
            if not rows:
                conn.rollback()
                return []
            conn.execute("UPDATE jobs SET status = 'queued' WHERE status = 'running'")
            conn.commit()
        finally:
            conn.close()

        return [
            Job(
                id=row[0],
                book_id=row[1],
                stage=row[2],
                status="queued",
                error_message=row[3],
            )
            for row in rows
        ]

    def get_job(self, job_id: str) -> Job | None:
        """Busca um Job pelo id. None se não existir."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, book_id, stage, status, error_message "
                "FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        return Job(
            id=row[0],
            book_id=row[1],
            stage=row[2],
            status=row[3],
            error_message=row[4],
        )
