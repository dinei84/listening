"""Testes da OS-057 na camada de dados: COUNT(*), `since` e WAL.

A matemática da linha de tempo vive em `tests/player/timeline.test.js` — este
arquivo cobre o que a sustenta no banco e o portão que liga os dois runners.
"""

import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from core.models import AudioChunk
from storage import audio_store, db, progress_store

RAIZ = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def temp_audio_store(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(audio_store, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store, "AUDIO_DIR", tmp_path / "audio")
    audio_store.init_db(db_path)
    return db_path


def _persistir(tmp_path, db_path, quantidade):
    """Persiste `quantidade` chunks sequenciais e devolve a lista resultante."""
    origem = tmp_path / "origem"
    origem.mkdir(parents=True, exist_ok=True)
    chunks = []
    for sequence in range(quantidade):
        caminho = origem / f"{sequence}.wav"
        caminho.write_bytes(b"RIFF-fake")
        chunks.append(
            AudioChunk(
                chapter_id="cap-1",
                sequence=sequence,
                file_path=str(caminho),
                duration_seconds=float(sequence + 1),
                engine_used="kokoro",
            )
        )
    return audio_store.persist_chunks("livro-1", chunks, db_path)


# --------------------------------------------------------------------------
# COUNT(*) em vez de materializar o livro inteiro para fazer um len()
# --------------------------------------------------------------------------


def test_count_chunks_matches_list_chunks_length(tmp_path, temp_audio_store):
    _persistir(tmp_path, temp_audio_store, 7)
    assert audio_store.count_chunks("livro-1", temp_audio_store) == 7
    assert audio_store.count_chunks("livro-1", temp_audio_store) == len(
        audio_store.list_chunks("livro-1", temp_audio_store)
    )


def test_count_chunks_is_zero_for_unknown_book(temp_audio_store):
    assert audio_store.count_chunks("nao-existe", temp_audio_store) == 0


def test_count_chunks_does_not_materialize_chunks(
    tmp_path, temp_audio_store, monkeypatch
):
    """A queixa medida era construir 533 objetos Pydantic para produzir um inteiro
    (1,33 ms contra 0,10 ms de um COUNT(*)), 1.800 vezes por hora de polling.
    Contar não pode instanciar nem um AudioChunk."""
    _persistir(tmp_path, temp_audio_store, 5)

    def proibido(*args, **kwargs):
        raise AssertionError("count_chunks não deve construir AudioChunk")

    monkeypatch.setattr(audio_store, "AudioChunk", proibido)
    assert audio_store.count_chunks("livro-1", temp_audio_store) == 5


# --------------------------------------------------------------------------
# `since`: o polling reenviava 51,8 KB a cada 2 s -> 91 MB por hora
# --------------------------------------------------------------------------


def test_list_chunks_since_returns_only_newer(tmp_path, temp_audio_store):
    _persistir(tmp_path, temp_audio_store, 5)
    recentes = audio_store.list_chunks("livro-1", temp_audio_store, since=2)
    assert [chunk.sequence for chunk in recentes] == [3, 4]


def test_list_chunks_since_is_exclusive(tmp_path, temp_audio_store):
    """`since=N` significa "o que veio DEPOIS de N": o cliente manda a maior
    sequence que já tem, e reenviar essa mesma linha seria desperdício."""
    _persistir(tmp_path, temp_audio_store, 3)
    assert [c.sequence for c in audio_store.list_chunks(
        "livro-1", temp_audio_store, since=2
    )] == []


def test_list_chunks_without_since_returns_all(tmp_path, temp_audio_store):
    """Retrocompatibilidade: sem `since`, comportamento idêntico ao de hoje."""
    _persistir(tmp_path, temp_audio_store, 4)
    assert [c.sequence for c in audio_store.list_chunks("livro-1", temp_audio_store)] == [
        0,
        1,
        2,
        3,
    ]


def test_list_chunks_since_none_returns_all(tmp_path, temp_audio_store):
    _persistir(tmp_path, temp_audio_store, 4)
    assert (
        len(audio_store.list_chunks("livro-1", temp_audio_store, since=None)) == 4
    )


def test_list_chunks_since_is_keyword_only(tmp_path, temp_audio_store):
    """`db_path` já é o segundo posicional em chamadas existentes: `since` posicional
    silenciosamente viraria db_path e o teste passaria lendo o banco errado."""
    _persistir(tmp_path, temp_audio_store, 3)
    with pytest.raises(TypeError):
        audio_store.list_chunks("livro-1", temp_audio_store, 1)


# --------------------------------------------------------------------------
# WAL: journal_mode=delete faz escritor e leitor se bloquearem
# --------------------------------------------------------------------------


def _journal_mode(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
    finally:
        conn.close()


@pytest.mark.parametrize(
    "modulo", [db, audio_store, progress_store], ids=["db", "audio_store", "progress"]
)
def test_init_db_opens_in_wal_mode(tmp_path, modulo):
    """O worker escreve a cada ~1,3 s e a API lê a cada 2 s no mesmo arquivo. Em
    journal_mode=delete os dois se bloqueiam; em WAL, leitor não bloqueia escritor."""
    db_path = str(tmp_path / f"{modulo.__name__.split('.')[-1]}.db")
    modulo.init_db(db_path)
    assert _journal_mode(db_path) == "wal"


def test_wal_migrates_existing_delete_mode_database(tmp_path):
    """Banco criado antes desta OS está em `delete`. Precisa migrar no lugar, sem
    ser apagado — a mesma lição da OS-052 sobre schema, aplicada ao journal."""
    db_path = str(tmp_path / "antigo.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=delete")
    conn.execute("CREATE TABLE books (id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO books (id) VALUES ('livro-antigo')")
    conn.commit()
    conn.close()
    assert _journal_mode(db_path) == "delete"

    db.init_db(db_path)

    assert _journal_mode(db_path) == "wal"
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1
    finally:
        conn.close()


def test_wal_is_idempotent(tmp_path):
    db.init_db(str(tmp_path / "a.db"))
    db.init_db(str(tmp_path / "a.db"))
    assert _journal_mode(str(tmp_path / "a.db")) == "wal"


def _leitor_bloqueado_durante_escrita(db_path: str) -> bool:
    """True se um leitor levar 'database is locked' enquanto um escritor derrama.

    `cache_size=1` força o escritor a derramar as páginas para o disco dentro da
    transação, e é aí que o modo rollback-journal sobe para EXCLUSIVE e barra o
    leitor. Sem forçar o derrame, o escritor fica em RESERVED e o leitor passa
    mesmo em journal_mode=delete — ou seja, o teste não discriminaria nada.
    """
    escritor = sqlite3.connect(db_path)
    escritor.execute("PRAGMA cache_size=1")
    leitor = sqlite3.connect(db_path, timeout=0.1)
    try:
        escritor.execute("BEGIN IMMEDIATE")
        escritor.executemany(
            "INSERT INTO chapters (book_id, id, title, chapter_order, start_page, end_page) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(f"livro-{i}", str(i), "x" * 2000, i, 0, 1) for i in range(3000)],
        )
        try:
            leitor.execute("SELECT COUNT(*) FROM books").fetchone()
            return False
        except sqlite3.OperationalError as erro:
            assert "locked" in str(erro)
            return True
    finally:
        escritor.rollback()
        escritor.close()
        leitor.close()


def test_wal_lets_reader_read_while_writer_is_spilling(tmp_path):
    """O ganho concreto de virar WAL, com o cenário de produção: o worker escreve
    e a API lê o mesmo arquivo. Em journal_mode=delete o leitor leva 'database is
    locked'; em WAL ele lê o estado pré-commit e não espera.

    O contraste é verificado nos DOIS modos no mesmo teste, de propósito: sem o
    ramo `delete` a asserção passaria sem WAL e não seria evidência de nada —
    foi exatamente o que aconteceu na primeira versão deste teste.
    """
    antigo = str(tmp_path / "delete.db")
    db.init_db(antigo)
    conn = sqlite3.connect(antigo)
    conn.execute("PRAGMA journal_mode=delete")
    conn.close()
    assert _journal_mode(antigo) == "delete"
    assert _leitor_bloqueado_durante_escrita(antigo) is True

    novo = str(tmp_path / "wal.db")
    db.init_db(novo)
    assert _journal_mode(novo) == "wal"
    assert _leitor_bloqueado_durante_escrita(novo) is False


# --------------------------------------------------------------------------
# Portão único: pytest roda também os testes de matemática em Node
# --------------------------------------------------------------------------


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node não instalado; os testes de timeline.js são pulados de propósito "
    "para não transformar o Node em dependência obrigatória da suíte.",
)
def test_timeline_js_unit_tests_pass():
    """Liga `node --test` ao pytest para o pytest seguir sendo o portão único.

    São funções puras, sem DOM e sem navegador — a decisão aberta do dono sobre
    adotar suíte de browser (Playwright) continua intocada.
    """
    resultado = subprocess.run(
        ["node", "--test", "tests/player/"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
