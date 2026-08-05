from core.models import Chapter
from storage import db


def _chapter(chapter_id: str, order: int, start: int, end: int) -> Chapter:
    return Chapter(
        id=chapter_id,
        title=f"Capitulo {order + 1}",
        order=order,
        text="texto que nao deve ser persistido",
        start_page=start,
        end_page=end,
    )


def test_create_and_list_chapters_roundtrip(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    db.create_chapters(
        "book-1",
        [_chapter("c1", 0, 1, 3), _chapter("c2", 1, 4, 6)],
        db_path=db_path,
    )

    chapters = db.list_chapters("book-1", db_path=db_path)
    assert [c.id for c in chapters] == ["c1", "c2"]
    assert [c.order for c in chapters] == [0, 1]
    assert [(c.start_page, c.end_page) for c in chapters] == [(1, 3), (4, 6)]
    assert [c.title for c in chapters] == ["Capitulo 1", "Capitulo 2"]


def test_list_chapters_returns_empty_for_unknown_book(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    assert db.list_chapters("nao-existe", db_path=db_path) == []


def test_list_chapters_is_ordered_by_order_not_insertion(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    db.create_chapters(
        "book-1",
        [_chapter("c3", 2, 7, 9), _chapter("c1", 0, 1, 3), _chapter("c2", 1, 4, 6)],
        db_path=db_path,
    )

    assert [c.order for c in db.list_chapters("book-1", db_path=db_path)] == [0, 1, 2]


def test_create_chapters_isolates_books(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    db.create_chapters("book-1", [_chapter("a", 0, 1, 2)], db_path=db_path)
    db.create_chapters("book-2", [_chapter("b", 0, 1, 2)], db_path=db_path)

    assert [c.id for c in db.list_chapters("book-1", db_path=db_path)] == ["a"]
    assert [c.id for c in db.list_chapters("book-2", db_path=db_path)] == ["b"]


def test_create_chapters_replaces_previous_chapters_of_same_book(tmp_path):
    """Reprocessar um livro não deve duplicar capítulos."""
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    db.create_chapters("book-1", [_chapter("a", 0, 1, 2)], db_path=db_path)
    db.create_chapters(
        "book-1", [_chapter("x", 0, 1, 5), _chapter("y", 1, 6, 9)], db_path=db_path
    )

    assert [c.id for c in db.list_chapters("book-1", db_path=db_path)] == ["x", "y"]
