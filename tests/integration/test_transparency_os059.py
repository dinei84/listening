"""OS-059 — o que a API e o player expõem sobre motor e custo."""

from datetime import UTC, datetime

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


def _livro(tmp_path, motores, status="ready", book_id="livro-1"):
    """Cria um Book e persiste um chunk por motor informado, na ordem dada."""
    db_module.create_book(
        Book(
            id=book_id,
            title="Livro de teste",
            original_filename="teste.pdf",
            status=status,
            created_at=datetime.now(UTC),
        )
    )
    origem = tmp_path / "origem"
    origem.mkdir(parents=True, exist_ok=True)
    chunks = []
    for sequence, motor in enumerate(motores):
        caminho = origem / f"{book_id}-{sequence}.wav"
        caminho.write_bytes(b"RIFF-fake")
        chunks.append(
            AudioChunk(
                chapter_id="cap-1",
                sequence=sequence,
                file_path=str(caminho),
                duration_seconds=1.0,
                engine_used=motor,
            )
        )
    if chunks:
        audio_store_module.persist_chunks(book_id, chunks)
    return book_id


# --------------------------------------------------------------------------
# engine_used no payload — a resposta para "está consumindo da API key?"
# --------------------------------------------------------------------------


def test_audio_endpoint_exposes_engine_used(client, tmp_path):
    """O campo é gravado desde sempre e nunca saiu do banco (achado 2.4 do estudo)."""
    book_id = _livro(tmp_path, ["kokoro", "openai", "kokoro"])
    corpo = client.get(f"/books/{book_id}/audio").json()
    assert [item["engine_used"] for item in corpo] == ["kokoro", "openai", "kokoro"]


def test_audio_endpoint_engine_used_survives_since(client, tmp_path):
    """O delta do polling (OS-057) precisa dos mesmos campos do payload cheio."""
    book_id = _livro(tmp_path, ["kokoro", "openai", "kokoro"])
    item = client.get(f"/books/{book_id}/audio", params={"since": 1}).json()[0]
    assert item["engine_used"] == "kokoro"
    assert set(item) == {
        "sequence",
        "chapter_id",
        "duration_seconds",
        "url",
        "engine_used",
    }


# --------------------------------------------------------------------------
# Divisão do custo em GET /status
# --------------------------------------------------------------------------


def test_status_exposes_cost_breakdown(client, tmp_path):
    book_id = _livro(tmp_path, [], status="pending_confirmation", book_id="pend")
    db_module.set_book_estimated_cost(book_id, 0.85)
    db_module.set_book_cost_breakdown(
        book_id, premium_cost=0.85, premium_chunks=57, estimated_chunks=624
    )

    corpo = client.get(f"/books/{book_id}/status").json()
    assert corpo["estimated_cost"] == pytest.approx(0.85)
    assert corpo["estimated_premium_cost"] == pytest.approx(0.85)
    assert corpo["premium_chunk_count"] == 57
    assert corpo["estimated_chunk_count"] == 624


def test_status_breakdown_is_null_when_never_estimated(client, tmp_path):
    """Livro que nunca passou pela estimativa não pode inventar zeros: zero
    significaria "medido e deu nada", e null significa "ainda não se sabe"."""
    book_id = _livro(tmp_path, [], status="uploaded", book_id="novo")
    corpo = client.get(f"/books/{book_id}/status").json()
    assert corpo["estimated_premium_cost"] is None
    assert corpo["premium_chunk_count"] is None


# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------


def test_player_serves_engines_module(client):
    resposta = client.get("/engines.js")
    assert resposta.status_code == 200
    assert "function label" in resposta.text


def test_player_loads_engines_before_app(client):
    html = client.get("/").text
    assert html.index('src="engines.js"') < html.index('src="app.js"')


def test_player_has_engine_indicator(client):
    """A marca de qual motor narrou o trecho corrente."""
    assert 'id="engine-indicator"' in client.get("/").text


def test_player_has_engine_summary(client):
    """O resumo por livro: quantos trechos em cada motor."""
    assert 'id="engine-summary"' in client.get("/").text


def test_player_confirmation_banner_shows_split(client):
    """O banner dizia só "deve custar US$ X" e calava sobre o que sustenta o número."""
    js = client.get("/app.js").text
    assert "estimated_premium_cost" in js
    assert "premium_chunk_count" in js


def test_player_says_local_voice_is_free(client):
    """O ponto que faz o número parecer razoável: o resto do livro não custa nada."""
    assert "não custa nada" in client.get("/app.js").text
