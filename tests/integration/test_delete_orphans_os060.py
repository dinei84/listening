"""OS-060 — a rota de delete não pode deixar capítulo para trás."""

import sqlite3
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.models import Book, Chapter
from storage import audio_store as audio_store_module
from storage import db as db_module
from storage import progress_store as progress_store_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    for modulo in (db_module, audio_store_module, progress_store_module):
        monkeypatch.setattr(modulo, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "AUDIO_DIR", tmp_path / "audio")
    with TestClient(app) as cliente:
        yield cliente, db_path


def test_delete_route_leaves_no_orphan_chapters(client):
    """A docstring da rota promete remover 'todo o seu rastro (áudio, jobs, PDF)'."""
    cliente, db_path = client
    db_module.create_book(
        Book(
            id="livro-1",
            title="Livro",
            original_filename="l.pdf",
            status="ready",
            created_at=datetime.now(UTC),
        )
    )
    db_module.create_chapters(
        "livro-1",
        [
            Chapter(id="c1", title="Um", order=0, text="", start_page=1, end_page=2),
            Chapter(id="c2", title="Dois", order=1, text="", start_page=2, end_page=3),
        ],
    )

    assert cliente.delete("/books/livro-1").status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        restantes = conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
    finally:
        conn.close()
    assert restantes == 0
    assert cliente.get("/books/livro-1/chapters").status_code == 404
