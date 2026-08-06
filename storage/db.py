import sqlite3
from datetime import datetime

from core.models import Book, Chapter

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
                chunk_total INTEGER,
                language TEXT,
                estimated_cost REAL,
                cost_confirmed INTEGER NOT NULL DEFAULT 0,
                cost_degraded INTEGER NOT NULL DEFAULT 0,
                normalize_text INTEGER NOT NULL DEFAULT 0
            )
            """)
        # `order` é palavra reservada no SQL, daí a coluna se chamar chapter_order.
        # O texto do capítulo NÃO é persistido: seria o livro inteiro duplicado no
        # banco, e nenhum consumidor precisa dele (OS-027).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                book_id TEXT NOT NULL,
                id TEXT NOT NULL,
                title TEXT NOT NULL,
                chapter_order INTEGER NOT NULL,
                start_page INTEGER NOT NULL,
                end_page INTEGER NOT NULL,
                PRIMARY KEY (book_id, id)
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
            "(id, title, original_filename, status, created_at, error_message, chunk_total, language, estimated_cost, cost_confirmed, cost_degraded, normalize_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                book.id,
                book.title,
                book.original_filename,
                book.status,
                book.created_at.isoformat(),
                book.error_message,
                book.chunk_total,
                book.language,
                book.estimated_cost,
                int(book.cost_confirmed),
                int(book.cost_degraded),
                int(book.normalize_text),
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
            "SELECT id, title, original_filename, status, created_at, error_message, chunk_total, language, estimated_cost, cost_confirmed, cost_degraded, normalize_text "
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
        language=row[7],
        estimated_cost=row[8],
        cost_confirmed=bool(row[9]),
        cost_degraded=bool(row[10]),
        normalize_text=bool(row[11]),
    )


def list_books(db_path: str | None = None) -> list[Book]:
    """Devolve todos os livros persistidos, ordenados por created_at decrescente."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        rows = conn.execute(
            "SELECT id, title, original_filename, status, created_at, error_message, chunk_total, language, estimated_cost, cost_confirmed, cost_degraded, normalize_text "
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
            language=row[7],
            estimated_cost=row[8],
            cost_confirmed=bool(row[9]),
            cost_degraded=bool(row[10]),
            normalize_text=bool(row[11]),
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


def set_book_estimated_cost(
    book_id: str, estimated_cost: float, db_path: str | None = None
) -> None:
    """Persiste a estimativa de custo de um Book (OS-042), calculada antes da síntese."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "UPDATE books SET estimated_cost = ? WHERE id = ?",
            (estimated_cost, book_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_book_cost_confirmed(
    book_id: str, confirmed: bool, db_path: str | None = None
) -> None:
    """Marca a confirmação explícita de custo de um Book (OS-042)."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "UPDATE books SET cost_confirmed = ? WHERE id = ?",
            (int(confirmed), book_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_book_cost_degraded(
    book_id: str, degraded: bool, db_path: str | None = None
) -> None:
    """Marca que um Book foi degradado para a voz local por estourar o teto de custo (OS-042)."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "UPDATE books SET cost_degraded = ? WHERE id = ?",
            (int(degraded), book_id),
        )
        conn.commit()
    finally:
        conn.close()


def create_chapters(
    book_id: str, chapters: list[Chapter], db_path: str | None = None
) -> None:
    """Persiste os capítulos de um Book, substituindo quaisquer capítulos anteriores do mesmo livro (reprocessar não duplica)."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
        conn.executemany(
            "INSERT INTO chapters "
            "(book_id, id, title, chapter_order, start_page, end_page) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    book_id,
                    chapter.id,
                    chapter.title,
                    chapter.order,
                    chapter.start_page,
                    chapter.end_page,
                )
                for chapter in chapters
            ],
        )
        conn.commit()
    finally:
        conn.close()


def list_chapters(book_id: str, db_path: str | None = None) -> list[Chapter]:
    """Lista os capítulos persistidos de um Book, ordenados por order. O campo text vem vazio — não é persistido."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        rows = conn.execute(
            "SELECT id, title, chapter_order, start_page, end_page "
            "FROM chapters WHERE book_id = ? ORDER BY chapter_order",
            (book_id,),
        ).fetchall()
    finally:
        conn.close()

    return [
        Chapter(
            id=row[0],
            title=row[1],
            order=row[2],
            text="",
            start_page=row[3],
            end_page=row[4],
        )
        for row in rows
    ]
