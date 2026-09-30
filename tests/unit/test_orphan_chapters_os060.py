"""OS-060 — `delete_book` deixava capítulos órfãos (item 58 do backlog).

A rota `DELETE /books/{id}` promete remover "todo o seu rastro" e limpava
`audio_chunks`, `reading_progress`, `jobs` e o PDF — mas nunca `chapters`. A
tabela entrou na OS-027 e o caminho de delete não foi atualizado; não há foreign
key nem ON DELETE CASCADE segurando isso por baixo.

Medido no banco local em 29/09/2026: 94 de 95 linhas órfãs para 1 livro
existente (eram 89 de 90 em 13/08 — cresce com o uso).
"""

import logging
import sqlite3
from datetime import UTC, datetime

import pytest

from core.models import Book, Chapter
from storage import db


@pytest.fixture
def banco(tmp_path):
    caminho = str(tmp_path / "t.db")
    db.init_db(caminho)
    return caminho


def _livro(banco, book_id, capitulos=2):
    db.create_book(
        Book(
            id=book_id,
            title=f"Livro {book_id}",
            original_filename=f"{book_id}.pdf",
            status="ready",
            created_at=datetime.now(UTC),
        ),
        banco,
    )
    db.create_chapters(
        book_id,
        [
            Chapter(
                id=f"{book_id}-cap-{i}",
                title=f"Capítulo {i}",
                order=i,
                text="",
                start_page=i,
                end_page=i + 1,
            )
            for i in range(capitulos)
        ],
        banco,
    )


def _contar_chapters(banco, book_id=None):
    conn = sqlite3.connect(banco)
    try:
        if book_id is None:
            return conn.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM chapters WHERE book_id = ?", (book_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _inserir_orfaos(banco, quantidade, prefixo="fantasma"):
    """Insere capítulos cujo book_id não existe em `books` — o lixo real."""
    conn = sqlite3.connect(banco)
    try:
        conn.executemany(
            "INSERT INTO chapters (book_id, id, title, chapter_order, start_page, end_page) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(f"{prefixo}-{i}", f"cap-{i}", "t", 0, 1, 2) for i in range(quantidade)],
        )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# O vazamento
# --------------------------------------------------------------------------


def test_delete_book_removes_its_chapters(banco):
    _livro(banco, "livro-1", capitulos=3)
    assert _contar_chapters(banco, "livro-1") == 3

    db.delete_book("livro-1", banco)

    assert _contar_chapters(banco, "livro-1") == 0


def test_delete_book_keeps_other_books_chapters(banco):
    """O DELETE precisa ser por book_id, não um limpa-tudo."""
    _livro(banco, "livro-1", capitulos=3)
    _livro(banco, "livro-2", capitulos=2)

    db.delete_book("livro-1", banco)

    assert _contar_chapters(banco, "livro-1") == 0
    assert _contar_chapters(banco, "livro-2") == 2
    assert db.get_book("livro-2", banco) is not None


def test_delete_unknown_book_is_noop(banco):
    """Semântica preservada: apagar id inexistente não tem efeito nem erro."""
    _livro(banco, "livro-1", capitulos=2)

    db.delete_book("nao-existe", banco)

    assert _contar_chapters(banco) == 2
    assert db.get_book("livro-1", banco) is not None


# --------------------------------------------------------------------------
# A varredura do lixo já acumulado
# --------------------------------------------------------------------------


def test_init_db_sweeps_orphan_chapters(banco):
    _inserir_orfaos(banco, 94)
    _livro(banco, "vivo", capitulos=1)
    assert _contar_chapters(banco) == 95

    db.init_db(banco)

    assert _contar_chapters(banco) == 1
    assert _contar_chapters(banco, "vivo") == 1


def test_init_db_sweep_keeps_chapters_of_existing_books(banco):
    """A varredura apaga linhas: só pode tocar no que é provadamente inalcançável."""
    _livro(banco, "a", capitulos=3)
    _livro(banco, "b", capitulos=2)

    db.init_db(banco)

    assert _contar_chapters(banco, "a") == 3
    assert _contar_chapters(banco, "b") == 2


def test_init_db_sweep_is_idempotent(banco):
    _inserir_orfaos(banco, 5)
    db.init_db(banco)
    assert _contar_chapters(banco) == 0
    db.init_db(banco)
    assert _contar_chapters(banco) == 0


def test_init_db_sweep_logs_how_many_it_removed(banco, caplog):
    """Apagar dado em silêncio é o que transforma correção em surpresa."""
    _inserir_orfaos(banco, 7)
    with caplog.at_level(logging.INFO, logger="storage.db"):
        db.init_db(banco)
    assert "7" in caplog.text


def test_init_db_sweep_is_silent_when_there_is_nothing_to_remove(banco, caplog):
    _livro(banco, "a", capitulos=2)
    with caplog.at_level(logging.INFO, logger="storage.db"):
        db.init_db(banco)
    assert "órfão" not in caplog.text and "orfao" not in caplog.text


def test_init_db_on_fresh_database_does_not_break(tmp_path):
    """Banco novo, sem tabela nenhuma: a varredura roda depois do CREATE TABLE."""
    caminho = str(tmp_path / "novo.db")
    db.init_db(caminho)
    assert _contar_chapters(caminho) == 0
