from storage import progress_store


def test_save_progress_persists_position(tmp_path):
    db_path = str(tmp_path / "test.db")
    progress_store.init_db(db_path)

    progress_store.save_progress("book-1", 7, 42.5, db_path=db_path)

    progress = progress_store.get_progress("book-1", db_path=db_path)
    assert progress is not None
    assert progress.book_id == "book-1"
    assert progress.sequence == 7
    assert progress.position_seconds == 42.5
    assert progress.updated_at is not None


def test_save_progress_overwrites_previous_value_for_same_book(tmp_path):
    db_path = str(tmp_path / "test.db")
    progress_store.init_db(db_path)

    progress_store.save_progress("book-1", 1, 10.0, db_path=db_path)
    progress_store.save_progress("book-1", 9, 99.5, db_path=db_path)

    progress = progress_store.get_progress("book-1", db_path=db_path)
    assert progress.sequence == 9
    assert progress.position_seconds == 99.5


def test_get_progress_returns_none_when_never_saved(tmp_path):
    db_path = str(tmp_path / "test.db")
    progress_store.init_db(db_path)

    assert progress_store.get_progress("nunca-salvo", db_path=db_path) is None


def test_save_progress_isolates_books(tmp_path):
    db_path = str(tmp_path / "test.db")
    progress_store.init_db(db_path)

    progress_store.save_progress("book-1", 1, 10.0, db_path=db_path)
    progress_store.save_progress("book-2", 5, 50.0, db_path=db_path)

    assert progress_store.get_progress("book-1", db_path=db_path).sequence == 1
    assert progress_store.get_progress("book-2", db_path=db_path).sequence == 5


def test_delete_progress_removes_saved_position(tmp_path):
    """Deletar um livro (OS-023) não pode deixar progresso órfão."""
    db_path = str(tmp_path / "test.db")
    progress_store.init_db(db_path)
    progress_store.save_progress("book-1", 3, 30.0, db_path=db_path)

    progress_store.delete_progress("book-1", db_path=db_path)

    assert progress_store.get_progress("book-1", db_path=db_path) is None
