import shutil
import sqlite3
from pathlib import Path

from core.models import AudioChunk
from storage.db import enable_wal

DEFAULT_DB_PATH = "books.db"
AUDIO_DIR = Path("storage/audio")


def _resolve_path(db_path: str | None) -> str:
    return db_path if db_path is not None else DEFAULT_DB_PATH


def init_db(db_path: str | None = None) -> None:
    """Cria a tabela `audio_chunks` no banco (idempotente), no caminho informado ou no padrão do projeto."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        enable_wal(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audio_chunks (
                book_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                engine_used TEXT NOT NULL,
                PRIMARY KEY (book_id, sequence)
            )
            """)
        conn.commit()
    finally:
        conn.close()


def persist_chunks(
    book_id: str, chunks: list[AudioChunk], db_path: str | None = None
) -> list[AudioChunk]:
    """Move cada AudioChunk do local temporário do Speaker para um diretório estável e persiste os metadados; devolve os chunks com file_path atualizado."""
    book_dir = AUDIO_DIR / book_id
    book_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        persisted: list[AudioChunk] = []
        for chunk in chunks:
            source = Path(chunk.file_path)
            destination = book_dir / f"{chunk.sequence}{source.suffix}"
            shutil.move(str(source), str(destination))

            stored_chunk = chunk.model_copy(update={"file_path": str(destination)})
            conn.execute(
                "INSERT INTO audio_chunks "
                "(book_id, chapter_id, sequence, file_path, duration_seconds, engine_used) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    book_id,
                    stored_chunk.chapter_id,
                    stored_chunk.sequence,
                    stored_chunk.file_path,
                    stored_chunk.duration_seconds,
                    stored_chunk.engine_used,
                ),
            )
            persisted.append(stored_chunk)
        conn.commit()
    finally:
        conn.close()

    return persisted


def count_chunks(book_id: str, db_path: str | None = None) -> int:
    """Conta os AudioChunk persistidos de um book_id sem materializar nenhum deles.

    Existe porque `GET /books/{id}/status` fazia `len(list_chunks(...))`: para um
    livro de 533 chunks isso construía 533 objetos Pydantic para produzir um
    inteiro, 1.800 vezes por hora de polling. Medido: 1,33 ms contra 0,10 ms.
    """
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM audio_chunks WHERE book_id = ?", (book_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def list_chunks(
    book_id: str, db_path: str | None = None, *, since: int | None = None
) -> list[AudioChunk]:
    """Lista os AudioChunk persistidos de um book_id, ordenados por sequence; com `since` devolve só os de sequence maior que ele.

    `since` é keyword-only de propósito: `db_path` já é o segundo posicional em
    chamadas existentes, e um `since` posicional viraria db_path em silêncio,
    lendo o banco errado sem erro nenhum.
    """
    consulta = (
        "SELECT chapter_id, sequence, file_path, duration_seconds, engine_used "
        "FROM audio_chunks WHERE book_id = ?"
    )
    parametros: tuple = (book_id,)
    if since is not None:
        consulta += " AND sequence > ?"
        parametros += (since,)
    consulta += " ORDER BY sequence"

    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        rows = conn.execute(consulta, parametros).fetchall()
    finally:
        conn.close()

    return [
        AudioChunk(
            chapter_id=row[0],
            sequence=row[1],
            file_path=row[2],
            duration_seconds=row[3],
            engine_used=row[4],
        )
        for row in rows
    ]


def get_chunk(
    book_id: str, sequence: int, db_path: str | None = None
) -> AudioChunk | None:
    """Busca um AudioChunk específico pelo book_id e sequence. None se não existir."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        row = conn.execute(
            "SELECT chapter_id, sequence, file_path, duration_seconds, engine_used "
            "FROM audio_chunks WHERE book_id = ? AND sequence = ?",
            (book_id, sequence),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return AudioChunk(
        chapter_id=row[0],
        sequence=row[1],
        file_path=row[2],
        duration_seconds=row[3],
        engine_used=row[4],
    )


def delete_chunks(book_id: str, db_path: str | None = None) -> None:
    """Remove os AudioChunk de um book_id (linhas do banco e diretório de áudio do disco)."""
    conn = sqlite3.connect(_resolve_path(db_path))
    try:
        conn.execute("DELETE FROM audio_chunks WHERE book_id = ?", (book_id,))
        conn.commit()
    finally:
        conn.close()

    shutil.rmtree(AUDIO_DIR / book_id, ignore_errors=True)
