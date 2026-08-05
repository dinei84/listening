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
