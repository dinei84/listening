import sqlite3
from datetime import datetime

from core.models import Book

DEFAULT_DB_PATH = "books.db"


def _resolve_path(db_path: str | None) -> str:
    return db_path if db_path is not None else DEFAULT_DB_PATH


def init_db(db_path: str | None = None) -> None:
    """Cria a tabela `books` no banco (idempotente), no caminho informado ou no padrão do projeto."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                error_message TEXT,
                chunk_total INTEGER
            )
            """)
        conn.commit()
    finally:
        conn.close()


def create_book(book: Book, db_path: str | None = None) -> None:
    """Insere um novo Book no banco."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "INSERT INTO books "
            "(id, title, original_filename, status, created_at, error_message, chunk_total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                book.id,
                book.title,
                book.original_filename,
                book.status,
                book.created_at.isoformat(),
                book.error_message,
                book.chunk_total,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_book(book_id: str, db_path: str | None = None) -> Book | None:
    """Busca um Book pelo id. Devolve None se não existir."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        row = conn.execute(
            "SELECT id, title, original_filename, status, created_at, error_message, chunk_total "
            "FROM books WHERE id = ?",
            (book_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return Book(
        id=row[0],
        title=row[1],
        original_filename=row[2],
        status=row[3],
        created_at=datetime.fromisoformat(row[4]),
        error_message=row[5],
        chunk_total=row[6],
    )


def list_books(db_path: str | None = None) -> list[Book]:
    """Devolve todos os livros persistidos, ordenados por created_at decrescente."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        rows = conn.execute(
            "SELECT id, title, original_filename, status, created_at, error_message, chunk_total "
            "FROM books ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()

    return [
        Book(
            id=row[0],
            title=row[1],
            original_filename=row[2],
            status=row[3],
            created_at=datetime.fromisoformat(row[4]),
            error_message=row[5],
            chunk_total=row[6],
        )
        for row in rows
    ]


def update_book_status(
    book_id: str,
    status: str,
    db_path: str | None = None,
    error_message: str | None = None,
) -> None:
    """Atualiza o status (e opcionalmente a error_message) de um Book existente."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "UPDATE books SET status = ?, error_message = ? WHERE id = ?",
            (status, error_message, book_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_book(book_id: str, db_path: str | None = None) -> None:
    """Remove a linha de um Book existente. Nenhum efeito se o book_id não existir."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
    finally:
        conn.close()


def set_book_chunk_total(
    book_id: str, chunk_total: int, db_path: str | None = None
) -> None:
    """Grava o total de chunks previsto para um Book, usado na barra de progresso da síntese."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "UPDATE books SET chunk_total = ? WHERE id = ?", (chunk_total, book_id)
        )
        conn.commit()
    finally:
        conn.close()
