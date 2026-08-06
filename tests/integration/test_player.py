from fastapi.testclient import TestClient

from api.main import app
from storage import audio_store as audio_store_module
from storage import db as db_module


def test_player_static_files_are_served(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_player_upload_form_has_language_select_with_auto_default(
    tmp_path, monkeypatch
):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)

    with TestClient(app) as client:
        response = client.get("/")

    html = response.text
    assert 'id="language-select"' in html
    assert '<option value="">Automático</option>' in html


def test_player_has_chapter_list_section(tmp_path, monkeypatch):
    """OS-029: o player precisa ter onde renderizar o seletor de capítulos."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)

    with TestClient(app) as client:
        html = client.get("/").text

    assert 'id="chapters-list"' in html


def test_player_has_position_indicator(tmp_path, monkeypatch):
    """OS-029: indicador de 'onde estou no livro'."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)

    with TestClient(app) as client:
        html = client.get("/").text

    assert 'id="position-indicator"' in html


def test_player_js_consumes_chapters_and_progress_endpoints(tmp_path, monkeypatch):
    """OS-029 só consome o que as OS-027/028 entregaram — sem backend novo."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)

    with TestClient(app) as client:
        js = client.get("/app.js").text

    assert "/chapters" in js
    assert "/progress" in js


def test_player_has_prev_and_next_buttons(tmp_path, monkeypatch):
    """OS-039: controles de trecho anterior/próximo presentes na seção de controles."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)

    with TestClient(app) as client:
        html = client.get("/").text

    assert 'id="prev-btn"' in html
    assert 'id="next-btn"' in html
    assert "Anterior" in html
    assert "Próximo" in html


def test_player_js_wires_trecho_navigation_and_keyboard(tmp_path, monkeypatch):
    """OS-039: app.js liga os botões e os atalhos de teclado (setas + espaço)."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)

    with TestClient(app) as client:
        js = client.get("/app.js").text

    assert 'getElementById("prev-btn")' in js
    assert 'getElementById("next-btn")' in js
    assert "ArrowLeft" in js
    assert "ArrowRight" in js
