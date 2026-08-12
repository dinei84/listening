import sqlite3
from datetime import UTC, datetime, timedelta

from core.models import Book, Chapter

DEFAULT_DB_PATH = "books.db"

# Depois de quanto tempo sem batimento o worker é dado como parado (OS-051).
# Precisa acomodar o chunk mais lento: o worker só bate entre chunks, e com um
# Speaker remoto um chunk demora bem mais que com o Kokoro local. 120s dá folga
# sem tornar a detecção inútil.
WORKER_HEARTBEAT_TIMEOUT_SECONDS = 120

# Linha única da tabela de batimento. Decisão #11: um worker ativo por vez, então
# o batimento é sobrescrito em vez de acumulado.
_HEARTBEAT_ROW_ID = 1


def _resolve_path(db_path: str | None) -> str:
    return db_path if db_path is not None else DEFAULT_DB_PATH


def ensure_column(conn, table: str, column: str, ddl: str) -> None:
    """Adiciona uma coluna a uma tabela existente se ela não existir (idempotente)."""
    colunas = {linha[1] for linha in conn.execute(f"PRAGMA table_info({table})")}
    if column not in colunas:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


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
        # Migração de schema (OS-052): `CREATE TABLE IF NOT EXISTS` cria tabela
        # ausente mas nunca adiciona coluna. Cada coluna acrescentada depois da
        # versão original da tabela entra aqui — antes, isso quebrava o books.db
        # local nas OS-018, OS-032 e OS-042. O `DEFAULT` declarado preenche as
        # linhas antigas; `NOT NULL` sem `DEFAULT` falha de propósito (SQLite).
        ensure_column(conn, "books", "error_message", "error_message TEXT")
        ensure_column(conn, "books", "chunk_total", "chunk_total INTEGER")
        ensure_column(conn, "books", "language", "language TEXT")
        ensure_column(
            conn,
            "books",
            "normalize_text",
            "normalize_text INTEGER NOT NULL DEFAULT 0",
        )
        ensure_column(conn, "books", "estimated_cost", "estimated_cost REAL")
        ensure_column(
            conn,
            "books",
            "cost_confirmed",
            "cost_confirmed INTEGER NOT NULL DEFAULT 0",
        )
        ensure_column(
            conn,
            "books",
            "cost_degraded",
            "cost_degraded INTEGER NOT NULL DEFAULT 0",
        )
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
        # Tabela NOVA, nunca coluna nova numa tabela existente (OS-051): o projeto
        # não tinha migração de schema antes da OS-052, e `CREATE TABLE IF NOT
        # EXISTS` cria tabela ausente mas nunca adiciona coluna. Como tabela, o
        # heartbeat aparece sozinho em banco antigo.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS worker_heartbeat (
                id INTEGER PRIMARY KEY,
                beat_at TEXT NOT NULL
            )
            """)
        conn.commit()
    finally:
        conn.close()


def record_worker_heartbeat(
    moment: datetime | None = None, db_path: str | None = None
) -> None:
    """Registra que o worker está vivo neste instante, sobrescrevendo o batimento anterior."""
    quando = moment if moment is not None else datetime.now(UTC)
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute(
            "INSERT INTO worker_heartbeat (id, beat_at) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET beat_at = excluded.beat_at",
            (_HEARTBEAT_ROW_ID, quando.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def last_worker_heartbeat(db_path: str | None = None) -> datetime | None:
    """Devolve o instante do último batimento do worker, ou None se nunca houve nenhum."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        row = conn.execute(
            "SELECT beat_at FROM worker_heartbeat WHERE id = ?", (_HEARTBEAT_ROW_ID,)
        ).fetchone()
    finally:
        conn.close()
    return datetime.fromisoformat(row[0]) if row else None


def worker_is_alive(db_path: str | None = None) -> bool:
    """True quando há batimento dentro do limiar; banco sem batimento é worker parado, nunca erro."""
    ultimo = last_worker_heartbeat(db_path)
    if ultimo is None:
        return False
    limite = timedelta(seconds=WORKER_HEARTBEAT_TIMEOUT_SECONDS)
    return datetime.now(UTC) - ultimo <= limite


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
