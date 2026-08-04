import io

import pytest
from fastapi.testclient import TestClient

from api import routes_books
from api.main import app
from core import config as config_module
from core.models import AudioChunk, ExtractedPage
from plugins import registry as registry_module
from plugins.extractors.base import Extractor
from plugins.speakers.base import Speaker
from storage import db as db_module


class FakeConfig:
    def __init__(self, extractor="fake_extractor", speaker="fake_speaker"):
        self.extractor = extractor
        self.speaker = speaker


class FakeExtractor(Extractor):
    def supports(self, pdf_path):
        return True

    def extract(self, pdf_path, page_range=None):
        return [
            ExtractedPage(
                page_number=1,
                text="Some extracted text.",
                confidence=1.0,
                source="fake_extractor",
            )
        ]


class FailingExtractor(Extractor):
    def supports(self, pdf_path):
        return True

    def extract(self, pdf_path, page_range=None):
        raise RuntimeError("boom")


class FakeSpeaker(Speaker):
    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None):
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path="/tmp/fake_api.wav",
            duration_seconds=1.0,
            engine_used="fake_speaker",
        )


def _upload_files():
    return {
        "file": ("book.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")
    }


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_books.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(routes_books, "UPLOAD_DIR", tmp_path / "uploads")
    return db_path


@pytest.fixture
def fake_working_pipeline(monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": FakeSpeaker})


@pytest.fixture
def fake_failing_pipeline(monkeypatch):
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FailingExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": FakeSpeaker})


def test_post_books_creates_book_and_returns_ready_status(
    temp_db, fake_working_pipeline
):
    with TestClient(app) as client:
        response = client.post("/books", files=_upload_files())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "id" in body


def test_post_books_returns_error_status_when_pipeline_fails(
    temp_db, fake_failing_pipeline
):
    with TestClient(app) as client:
        response = client.post("/books", files=_upload_files())

    assert response.status_code == 200
    assert response.json()["status"] == "error"


def test_get_books_status_returns_persisted_status(temp_db, fake_working_pipeline):
    with TestClient(app) as client:
        create_response = client.post("/books", files=_upload_files())
        book_id = create_response.json()["id"]

        status_response = client.get(f"/books/{book_id}/status")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "ready"


def test_get_books_status_returns_404_for_unknown_id(temp_db):
    with TestClient(app) as client:
        response = client.get("/books/does-not-exist/status")

    assert response.status_code == 404
