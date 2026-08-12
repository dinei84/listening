import sqlite3
from datetime import UTC, datetime, timedelta

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
    antigo = datetime.now(UTC) - timedelta(seconds=db.WORKER_HEARTBEAT_TIMEOUT_SECONDS + 5)
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
