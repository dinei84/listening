"""Testes da OS-057 na API e no HTML do player."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.models import AudioChunk, Book
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
        yield cliente


def _livro_com_chunks(tmp_path, quantidade, book_id="livro-1"):
    """Cria um Book pronto e persiste `quantidade` chunks com durações distintas."""
    from datetime import UTC, datetime

    db_module.create_book(
        Book(
            id=book_id,
            title="Livro de teste",
            original_filename="teste.pdf",
            status="synthesizing",
            created_at=datetime.now(UTC),
        )
    )
    origem = tmp_path / "origem"
    origem.mkdir(parents=True, exist_ok=True)
    chunks = []
    for sequence in range(quantidade):
        caminho = origem / f"{book_id}-{sequence}.wav"
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
    audio_store_module.persist_chunks(book_id, chunks)
    return book_id


# --------------------------------------------------------------------------
# GET /books/{id}/audio?since=N
# --------------------------------------------------------------------------


def test_audio_endpoint_without_since_returns_all(client, tmp_path):
    """Retrocompatível: sem o parâmetro, resposta idêntica à de hoje."""
    book_id = _livro_com_chunks(tmp_path, 4)
    corpo = client.get(f"/books/{book_id}/audio").json()
    assert [item["sequence"] for item in corpo] == [0, 1, 2, 3]
    assert corpo[0]["duration_seconds"] == 1.0
    assert corpo[0]["url"] == f"/books/{book_id}/audio/0"
    assert corpo[0]["chapter_id"] == "cap-1"


def test_audio_endpoint_since_returns_only_newer(client, tmp_path):
    """O polling reenviava 51,8 KB a cada 2 s (91 MB/hora) para um delta de 0 ou 1."""
    book_id = _livro_com_chunks(tmp_path, 5)
    corpo = client.get(f"/books/{book_id}/audio", params={"since": 2}).json()
    assert [item["sequence"] for item in corpo] == [3, 4]


def test_audio_endpoint_since_at_head_returns_empty(client, tmp_path):
    book_id = _livro_com_chunks(tmp_path, 3)
    assert client.get(f"/books/{book_id}/audio", params={"since": 2}).json() == []


def test_audio_endpoint_since_keeps_full_payload_shape(client, tmp_path):
    """O delta precisa ter os mesmos campos do payload cheio: o cliente usa o
    mesmo mergeChunks para os dois.

    Compara delta contra payload cheio em vez de fixar a lista de campos: a
    versão original travava os quatro campos de então e quebrou quando a OS-059
    acrescentou `engine_used` aos DOIS — uma mudança que este teste deveria
    aprovar, não reprovar."""
    book_id = _livro_com_chunks(tmp_path, 3)
    cheio = client.get(f"/books/{book_id}/audio").json()
    delta = client.get(f"/books/{book_id}/audio", params={"since": 1}).json()
    assert set(delta[0]) == set(cheio[0])


def test_audio_endpoint_negative_since_is_rejected(client, tmp_path):
    """`since` negativo não tem significado; aceitar silenciosamente esconderia
    um bug de cálculo no cliente."""
    book_id = _livro_com_chunks(tmp_path, 3)
    assert (
        client.get(f"/books/{book_id}/audio", params={"since": -1}).status_code == 422
    )


def test_audio_endpoint_since_on_unknown_book_is_404(client):
    assert client.get("/books/nao-existe/audio", params={"since": 1}).status_code == 404


# --------------------------------------------------------------------------
# chunks_done via COUNT(*)
# --------------------------------------------------------------------------


def test_status_chunks_done_uses_count(client, tmp_path, monkeypatch):
    """`chunks_done` construía 533 objetos Pydantic para virar um len() (13× mais
    lento que COUNT(*)), 1.800 vezes por hora de polling."""
    book_id = _livro_com_chunks(tmp_path, 6)

    def proibido(*args, **kwargs):
        raise AssertionError("GET /status não deve materializar os chunks")

    monkeypatch.setattr(audio_store_module, "list_chunks", proibido)
    corpo = client.get(f"/books/{book_id}/status").json()
    assert corpo["chunks_done"] == 6


def test_status_chunks_done_is_zero_without_audio(client, tmp_path):
    from datetime import UTC, datetime

    db_module.create_book(
        Book(
            id="vazio",
            title="Sem áudio",
            original_filename="x.pdf",
            status="uploaded",
            created_at=datetime.now(UTC),
        )
    )
    assert client.get("/books/vazio/status").json()["chunks_done"] == 0


# --------------------------------------------------------------------------
# HTML do player
# --------------------------------------------------------------------------


def test_player_loads_timeline_before_app(client):
    """`app.js` usa o Timeline no carregamento: a ordem das tags importa."""
    html = client.get("/").text
    assert "timeline.js" in html
    assert html.index("timeline.js") < html.index("app.js")


def test_player_serves_timeline_module(client):
    """O módulo é servido pelo StaticFiles, não embutido no app.js."""
    resposta = client.get("/timeline.js")
    assert resposta.status_code == 200
    assert "function build" in resposta.text


def test_player_has_scrub_and_time_readout(client):
    html = client.get("/").text
    assert 'id="scrub"' in html
    assert 'id="time-readout"' in html


def test_player_has_skip_buttons(client):
    html = client.get("/").text
    assert 'id="back-15-btn"' in html
    assert 'id="forward-15-btn"' in html


def test_player_audio_element_has_no_native_controls(client):
    """A régua nativa cobre um trecho de ~53 s num livro de 7,8 h: é justamente o
    que esta OS substitui. Manter as duas barras deixaria duas verdades na tela."""
    html = client.get("/").text
    inicio = html.index('id="audio-player"')
    tag = html[inicio : html.index(">", inicio)]
    assert "controls" not in tag
