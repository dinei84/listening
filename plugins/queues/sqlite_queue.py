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
                    error_message TEXT,
                    priority INTEGER NOT NULL DEFAULT 0
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
                "INSERT INTO jobs (id, book_id, stage, status, error_message, priority) "
                "VALUES (?, ?, ?, 'queued', ?, ?)",
                (job.id, job.book_id, job.stage, job.error_message, job.priority),
            )
            conn.commit()
        finally:
            conn.close()

    def claim_next(self) -> Job | None:
        """Reivindica atomicamente o próximo Job 'queued' por prioridade (maior primeiro, desempate por inserção), marcando como 'running'."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id, book_id, stage, error_message, priority FROM jobs "
                "WHERE status = 'queued' ORDER BY priority DESC, rowid LIMIT 1"
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
            priority=row[4],
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
                "SELECT id, book_id, stage, error_message, priority FROM jobs "
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
                priority=row[4],
            )
            for row in rows
        ]

    def get_job(self, job_id: str) -> Job | None:
        """Busca um Job pelo id. None se não existir."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, book_id, stage, status, error_message, priority "
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
            priority=row[5],
        )

    def delete_jobs_for_book(self, book_id: str) -> None:
        """Remove todos os Jobs de um book_id."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM jobs WHERE book_id = ?", (book_id,))
            conn.commit()
        finally:
            conn.close()

    def prioritize(self, job_id: str) -> None:
        """Dá ao Job uma prioridade maior que a de qualquer outro Job pendente (queued ou running)."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(priority), 0) + 1 FROM jobs"
            ).fetchone()
            conn.execute("UPDATE jobs SET priority = ? WHERE id = ?", (row[0], job_id))
            conn.commit()
        finally:
            conn.close()

    def should_yield(self, job_id: str) -> bool:
        """Devolve True se existe um Job 'queued' com prioridade maior que a do Job informado."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT priority FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                return False
            higher = conn.execute(
                "SELECT 1 FROM jobs WHERE status = 'queued' AND priority > ? LIMIT 1",
                (row[0],),
            ).fetchone()
            return higher is not None
        finally:
            conn.close()

    def requeue(self, job_id: str) -> None:
        """Devolve um Job individual para 'queued', preservando a prioridade."""
        conn = self._connect()
        try:
            conn.execute("UPDATE jobs SET status = 'queued' WHERE id = ?", (job_id,))
            conn.commit()
        finally:
            conn.close()

    def get_job_for_book(self, book_id: str) -> Job | None:
        """Busca o Job de um book_id (o mais recente). None se o livro não tiver Job."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id, book_id, stage, status, error_message, priority "
                "FROM jobs WHERE book_id = ? ORDER BY rowid DESC LIMIT 1",
                (book_id,),
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
            priority=row[5],
        )
