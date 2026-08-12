import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from core.models import Book
from storage import db


def _book(
    book_id: str = "book-1",
    status: str = "uploaded",
    created_at: datetime = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
) -> Book:
    return Book(
        id=book_id,
        title="Test Book",
        original_filename="test.pdf",
        status=status,
        created_at=created_at,
    )


def test_db_init_creates_books_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    conn = sqlite3.connect(db_path)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='books'"
        ).fetchall()
    finally:
        conn.close()

    assert len(tables) == 1


def test_db_create_and_get_book_roundtrip(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    book = _book()

    db.create_book(book, db_path)
    fetched = db.get_book(book.id, db_path)

    assert fetched is not None
    assert fetched.id == book.id
    assert fetched.title == book.title
    assert fetched.original_filename == book.original_filename
    assert fetched.status == book.status


def test_db_create_and_get_book_roundtrip_persists_language(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    book = Book(
        id="book-pt",
        title="Test Book",
        original_filename="test.pdf",
        status="uploaded",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        language="pt",
    )

    db.create_book(book, db_path)
    fetched = db.get_book(book.id, db_path)

    assert fetched is not None
    assert fetched.language == "pt"


def test_db_update_book_status(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    book = _book(status="uploaded")
    db.create_book(book, db_path)

    db.update_book_status(book.id, "ready", db_path)
    fetched = db.get_book(book.id, db_path)

    assert fetched.status == "ready"


def test_list_books_returns_empty_list_when_no_books(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    books = db.list_books(db_path)

    assert books == []


def test_list_books_returns_books_ordered_by_created_at_desc(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    older = _book(
        book_id="book-older",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    newer = _book(
        book_id="book-newer",
        created_at=datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC),
    )
    db.create_book(older, db_path)
    db.create_book(newer, db_path)

    books = db.list_books(db_path)

    assert [book.id for book in books] == ["book-newer", "book-older"]


# --- OS-051: sinal de worker ativo -----------------------------------------


def test_heartbeat_absent_reports_worker_stopped(tmp_path):
    """Banco sem batimento é worker parado, nunca erro — é o estado de quem nunca subiu o worker."""
    caminho = str(tmp_path / "t.db")
    db.init_db(caminho)
    assert db.worker_is_alive(db_path=caminho) is False
    assert db.last_worker_heartbeat(db_path=caminho) is None


def test_heartbeat_recent_reports_worker_alive(tmp_path):
    caminho = str(tmp_path / "t.db")
    db.init_db(caminho)
    db.record_worker_heartbeat(db_path=caminho)
    assert db.worker_is_alive(db_path=caminho) is True
    assert db.last_worker_heartbeat(db_path=caminho) is not None


def test_heartbeat_older_than_threshold_reports_worker_stopped(tmp_path):
    """O limiar precisa acomodar o chunk mais lento; acima dele, o worker é dado como parado."""
    caminho = str(tmp_path / "t.db")
    db.init_db(caminho)
    antigo = datetime.now(UTC) - timedelta(
        seconds=db.WORKER_HEARTBEAT_TIMEOUT_SECONDS + 5
    )
    db.record_worker_heartbeat(moment=antigo, db_path=caminho)
    assert db.worker_is_alive(db_path=caminho) is False


def test_heartbeat_keeps_a_single_row(tmp_path):
    """Decisão #11: um worker por vez, então o batimento é sobrescrito, não acumulado."""
    caminho = str(tmp_path / "t.db")
    db.init_db(caminho)
    for _ in range(3):
        db.record_worker_heartbeat(db_path=caminho)
    conn = sqlite3.connect(caminho)
    total = conn.execute("SELECT COUNT(*) FROM worker_heartbeat").fetchone()[0]
    conn.close()
    assert total == 1


def test_init_db_creates_heartbeat_table_on_existing_database(tmp_path):
    """O projeto não tem migração de schema: tabela NOVA é criada sem exigir apagar o books.db."""
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE books (id TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

    db.init_db(caminho)

    db.record_worker_heartbeat(db_path=caminho)
    assert db.worker_is_alive(db_path=caminho) is True


# --- OS-052: migração de schema ---------------------------------------------


def test_ensure_column_adds_missing_column_to_existing_table(tmp_path):
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE teste (id TEXT PRIMARY KEY)")
    conn.commit()

    db.ensure_column(conn, "teste", "nota", "nota TEXT")
    conn.commit()

    colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(teste)")}
    conn.close()
    assert "nota" in colunas


def test_ensure_column_is_idempotent(tmp_path):
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE teste (id TEXT PRIMARY KEY, nota TEXT)")
    conn.commit()

    db.ensure_column(conn, "teste", "nota", "nota TEXT")
    db.ensure_column(conn, "teste", "nota", "nota TEXT")
    conn.commit()

    colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(teste)")}
    conn.close()
    assert colunas == {"id", "nota"}


def test_ensure_column_preserves_existing_rows(tmp_path):
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE teste (id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO teste (id) VALUES ('a')")
    conn.commit()

    db.ensure_column(conn, "teste", "nota", "nota TEXT")
    conn.commit()

    linha = conn.execute("SELECT id, nota FROM teste WHERE id = 'a'").fetchone()
    conn.close()
    assert linha == ("a", None)


def test_ensure_column_applies_default_to_old_rows(tmp_path):
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE teste (id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO teste (id) VALUES ('a')")
    conn.commit()

    db.ensure_column(conn, "teste", "aprovado", "aprovado INTEGER NOT NULL DEFAULT 1")
    conn.commit()

    linha = conn.execute("SELECT id, aprovado FROM teste WHERE id = 'a'").fetchone()
    conn.close()
    assert linha == ("a", 1)


def test_ensure_column_raises_on_invalid_ddl(tmp_path):
    """DDL digitado errado precisa falhar alto, não virar migração silenciosa."""
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE teste (id TEXT PRIMARY KEY)")
    conn.commit()

    with pytest.raises(sqlite3.OperationalError):
        db.ensure_column(conn, "teste", "nota", "nota (mal formado")
    conn.close()


def test_ensure_column_refuses_not_null_without_default(tmp_path):
    """Restrição do SQLite a respeitar: ADD COLUMN recusa NOT NULL sem DEFAULT (com linhas) — o erro sobe."""
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("CREATE TABLE teste (id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO teste (id) VALUES ('a')")
    conn.commit()

    with pytest.raises(sqlite3.OperationalError):
        db.ensure_column(conn, "teste", "obrigatoria", "obrigatoria TEXT NOT NULL")
    conn.close()


def test_init_db_upgrades_legacy_books_table(tmp_path):
    """Um books.db no formato da OS-017 ganha as colunas novas sem perder as linhas existentes."""
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("""
        CREATE TABLE books (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    conn.execute(
        "INSERT INTO books (id, title, original_filename, status, created_at) "
        "VALUES ('legacy-1', 'Livro Antigo', 'antigo.pdf', 'ready', "
        "'2026-01-01T12:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    db.init_db(caminho)

    livro = db.get_book("legacy-1", caminho)
    assert livro is not None
    assert livro.title == "Livro Antigo"
    assert livro.error_message is None
    assert livro.chunk_total is None
    assert livro.language is None
    assert livro.estimated_cost is None
    assert livro.cost_confirmed is False
    assert livro.cost_degraded is False
    assert livro.normalize_text is False

    conn = sqlite3.connect(caminho)
    colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(books)")}
    conn.close()
    assert {
        "error_message",
        "chunk_total",
        "language",
        "estimated_cost",
        "cost_confirmed",
        "cost_degraded",
        "normalize_text",
    } <= colunas


def test_legacy_os017_books_db_opens_without_error(tmp_path):
    """Um books.db no formato da OS-017 (sem error_message, sem priority) abre sem erro; as
    cinco tabelas do projeto funcionam no mesmo arquivo depois da migração."""
    from plugins.queues.sqlite_queue import SQLiteJobQueue
    from storage import audio_store, progress_store

    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("""
        CREATE TABLE books (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    conn.execute("""
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            book_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT
        )
        """)
    conn.execute("""
        CREATE TABLE audio_chunks (
            book_id TEXT NOT NULL,
            chapter_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            engine_used TEXT NOT NULL,
            PRIMARY KEY (book_id, sequence)
        )
        """)
    conn.execute(
        "INSERT INTO books (id, title, original_filename, status, created_at) "
        "VALUES ('a', 'A', 'a.pdf', 'ready', '2026-01-01T12:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO jobs (id, book_id, stage, status) "
        "VALUES ('j1', 'a', 'extract', 'done')"
    )
    conn.commit()
    conn.close()

    db.init_db(caminho)
    SQLiteJobQueue(caminho)
    audio_store.init_db(caminho)
    progress_store.init_db(caminho)

    assert db.get_book("a", caminho) is not None
    fila = SQLiteJobQueue(caminho)
    assert fila.get_job("j1") is not None
    assert audio_store.list_chunks("a", db_path=caminho) == []
    assert progress_store.get_progress("a", db_path=caminho) is None

    conn = sqlite3.connect(caminho)
    colunas_books = {linha[1] for linha in conn.execute("PRAGMA table_info(books)")}
    colunas_jobs = {linha[1] for linha in conn.execute("PRAGMA table_info(jobs)")}
    tabelas = {
        linha[0]
        for linha in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    conn.close()
    assert "error_message" in colunas_books
    assert colunas_jobs >= {"error_message", "priority"}
    assert {"worker_heartbeat", "reading_progress", "audio_chunks"} <= tabelas


# --- OS-053: escolha de voz --------------------------------------------------


def test_book_voice_persists_and_loads(tmp_path):
    caminho = str(tmp_path / "t.db")
    db.init_db(caminho)
    livro = Book(
        id="book-voz",
        title="Livro com voz",
        original_filename="voz.pdf",
        status="uploaded",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        language="pt",
        voice="pm_alex",
    )

    db.create_book(livro, caminho)
    carregado = db.get_book(livro.id, caminho)

    assert carregado is not None
    assert carregado.voice == "pm_alex"


def test_book_voice_defaults_to_none(tmp_path):
    caminho = str(tmp_path / "t.db")
    db.init_db(caminho)
    livro = Book(
        id="book-sem-voz",
        title="Sem voz",
        original_filename="sem.pdf",
        status="uploaded",
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )

    db.create_book(livro, caminho)
    carregado = db.get_book(livro.id, caminho)

    assert carregado is not None
    assert carregado.voice is None


def test_init_db_adds_voice_column_to_legacy_books_table(tmp_path):
    """Um books.db sem a coluna voice (formato da OS-052) ganha a coluna sem perder linhas."""
    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho)
    conn.execute("""
        CREATE TABLE books (
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
    conn.execute(
        "INSERT INTO books (id, title, original_filename, status, created_at, language) "
        "VALUES ('a', 'A', 'a.pdf', 'ready', '2026-01-01T12:00:00+00:00', 'pt')"
    )
    conn.commit()
    conn.close()

    db.init_db(caminho)

    livro = db.get_book("a", caminho)
    assert livro is not None
    assert livro.voice is None
    assert livro.language == "pt"

    conn = sqlite3.connect(caminho)
    colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(books)")}
    conn.close()
    assert "voice" in colunas
