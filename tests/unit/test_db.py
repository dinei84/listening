import sqlite3
from datetime import UTC, datetime

from core.models import Book
from storage import db


def _book(book_id: str = "book-1", status: str = "uploaded") -> Book:
    return Book(
        id=book_id,
        title="Test Book",
        original_filename="test.pdf",
        status=status,
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
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


def test_db_update_book_status(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    book = _book(status="uploaded")
    db.create_book(book, db_path)

    db.update_book_status(book.id, "ready", db_path)
    fetched = db.get_book(book.id, db_path)

    assert fetched.status == "ready"
