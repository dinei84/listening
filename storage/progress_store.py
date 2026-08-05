import sqlite3
from datetime import UTC, datetime

from core.models import ReadingProgress

DEFAULT_DB_PATH = "books.db"


def _resolve_path(db_path: str | None) -> str:
    return db_path if db_path is not None else DEFAULT_DB_PATH


def init_db(db_path: str | None = None) -> None:
    """Cria a tabela `reading_progress` no banco (idempotente), no caminho informado ou no padrão do projeto."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        # book_id é a chave primária: guarda só a posição ATUAL, sempre sobrescrita.
        # Histórico de leitura está explicitamente fora do escopo (OS-028).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reading_progress (
                book_id TEXT PRIMARY KEY,
                sequence INTEGER NOT NULL,
                position_seconds REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
        conn.commit()
    finally:
        conn.close()


def save_progress(
    book_id: str,
    sequence: int,
    position_seconds: float,
    db_path: str | None = None,
) -> None:
    """Grava a posição de leitura atual de um Book, sobrescrevendo qualquer valor anterior do mesmo livro."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "INSERT INTO reading_progress "
            "(book_id, sequence, position_seconds, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(book_id) DO UPDATE SET "
            "sequence = excluded.sequence, "
            "position_seconds = excluded.position_seconds, "
            "updated_at = excluded.updated_at",
            (book_id, sequence, position_seconds, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_progress(book_id: str, db_path: str | None = None) -> ReadingProgress | None:
    """Busca a posição de leitura salva de um Book. None se nunca foi salva."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        row = conn.execute(
            "SELECT book_id, sequence, position_seconds, updated_at "
            "FROM reading_progress WHERE book_id = ?",
            (book_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return ReadingProgress(
        book_id=row[0],
        sequence=row[1],
        position_seconds=row[2],
        updated_at=datetime.fromisoformat(row[3]),
    )


def delete_progress(book_id: str, db_path: str | None = None) -> None:
    """Remove a posição de leitura de um Book. Nenhum efeito se não existir."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute("DELETE FROM reading_progress WHERE book_id = ?", (book_id,))
        conn.commit()
    finally:
        conn.close()
