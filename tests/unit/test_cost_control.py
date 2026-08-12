"""Testes da trava de custo (OS-042): estimativa com confirmação + teto de segurança.

Cobertura:
  - estimate_cost usa cost_per_char do Speaker configurado
  - livro de custo zero (Kokoro) processa direto, sem confirmação (regressão)
  - livro pago não é sintetizado antes da confirmação
  - livro confirmado prossegue para a síntese
  - estimativa acima do teto não processa com o Speaker pago mesmo confirmado (degrada)
  - a estimativa acontece antes de qualquer chamada ao Speaker
"""

import os
import tempfile
from datetime import UTC, datetime

import pytest

from core import config as config_module
from core import pipeline
from core.models import AudioChunk, Book, ExtractedPage, Job
from plugins import registry as registry_module
from plugins.extractors.base import Extractor
from plugins.queues import sqlite_queue as sqlite_queue_module
from plugins.speakers.base import Speaker
from storage import audio_store as audio_store_module
from storage import db as db_module
from storage import uploads as uploads_module
from worker import tasks as worker_tasks


class FakeConfig:
    def __init__(
        self,
        speaker="fake_speaker",
        max_cost_per_book=None,
        fallback_speaker="kokoro",
        retry_max_attempts=3,
        retry_base_delay_seconds=1.0,
        retry_max_delay_seconds=30.0,
    ):
        self.extractor = "fake_extractor"
        self.speaker = speaker
        self.queue = "sqlite"
        self.max_cost_per_book = max_cost_per_book
        self.fallback_speaker = fallback_speaker
        self.retry_max_attempts = retry_max_attempts
        self.retry_base_delay_seconds = retry_base_delay_seconds
        self.retry_max_delay_seconds = retry_max_delay_seconds


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


class CountingSpeaker(Speaker):
    """Speaker dublê que registra chamadas de synthesize — o custo vem de cost_per_char."""

    def __init__(self):
        self.synthesized_texts = []

    def synthesize(self, text, voice=None, lang_code=None):
        self.synthesized_texts.append(text)
        fd, path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(b"RIFF-fake-wav-bytes")
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=path,
            duration_seconds=1.0,
            engine_used="fake",
        )


class VoiceRecordingSpeaker(CountingSpeaker):
    """Speaker dublê que também registra a voz de cada chamada — usado para provar que a voz escolhida atravessa a degradação de custo."""

    def __init__(self, cost_per_char=0.0):
        super().__init__()
        self._cost_per_char = cost_per_char
        self.voices = []

    @property
    def cost_per_char(self):
        return self._cost_per_char

    def synthesize(self, text, voice=None, lang_code=None):
        self.voices.append(voice)
        return super().synthesize(text, voice=voice, lang_code=lang_code)


class PaidSpeaker(CountingSpeaker):
    """Speaker pago fictício (cost_per_char > 0), registrado como 'paid'."""

    @property
    def cost_per_char(self):
        return 0.001


class LocalSpeaker(CountingSpeaker):
    """Speaker local fictício (cost_per_char == 0.0), registrado como 'kokoro' (fallback de degradação)."""

    @property
    def cost_per_char(self):
        return 0.0


class EstimateAwareSpeaker(Speaker):
    """Speaker que prova que a estimativa foi persistida antes de qualquer chamada de síntese."""

    def __init__(self, book_id):
        self.book_id = book_id

    @property
    def cost_per_char(self):
        return 0.001

    def synthesize(self, text, voice=None, lang_code=None):
        book = db_module.get_book(self.book_id)
        assert (
            book is not None and book.estimated_cost is not None
        ), "a estimativa precisa estar persistida antes de qualquer chamada ao Speaker"
        fd, path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(b"RIFF-fake-wav-bytes")
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=path,
            duration_seconds=1.0,
            engine_used="estimate_aware",
        )


@pytest.fixture
def temp_paths(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(sqlite_queue_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "AUDIO_DIR", tmp_path / "audio")
    audio_store_module.init_db(db_path)
    db_module.init_db(db_path)
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads_module, "UPLOAD_DIR", upload_dir)
    return upload_dir


def _create_book_and_pdf(upload_dir, book_id="book-1", voice=None):
    upload_dir.mkdir(parents=True, exist_ok=True)
    uploads_module.pdf_path_for(book_id).write_bytes(b"%PDF-1.4 fake content")
    book = Book(
        id=book_id,
        title="Test Book",
        original_filename="test.pdf",
        status="uploaded",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        voice=voice,
    )
    db_module.create_book(book)
    return book


def test_estimate_cost_uses_speaker_cost_per_char(monkeypatch):
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="paid")
    )
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"paid": PaidSpeaker, "kokoro": LocalSpeaker}
    )

    cost = pipeline.estimate_cost("Some extracted text.")

    assert cost == pytest.approx(len("Some extracted text.") * 0.001)


def test_zero_cost_book_processes_without_confirmation(temp_paths, monkeypatch):
    book = _create_book_and_pdf(temp_paths)
    speaker = LocalSpeaker()
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(
        registry_module,
        "SPEAKERS",
        {"fake_speaker": lambda: speaker, "kokoro": lambda: speaker},
    )
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    fetched = db_module.get_book(book.id)
    assert fetched.status == "ready"
    assert fetched.estimated_cost == 0.0
    assert speaker.synthesized_texts, "livro de custo zero precisa sintetizar"
    assert queue.get_job(job.id).status == "done"


def test_paid_book_is_not_synthesized_before_confirmation(temp_paths, monkeypatch):
    book = _create_book_and_pdf(temp_paths)
    speaker = PaidSpeaker()
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="paid")
    )
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"paid": lambda: speaker, "kokoro": LocalSpeaker}
    )
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    fetched = db_module.get_book(book.id)
    assert fetched.status == "pending_confirmation"
    assert fetched.estimated_cost == pytest.approx(len("Some extracted text.") * 0.001)
    assert (
        speaker.synthesized_texts == []
    ), "livro pago não pode ser sintetizado antes de confirmar"
    assert audio_store_module.list_chunks(book.id) == []
    # O Job da rodada de extração+estimativa é encerrado; a confirmação enfileira um novo.
    assert queue.get_job(job.id).status == "done"


def test_confirmed_book_proceeds_to_synthesis(temp_paths, monkeypatch):
    book = _create_book_and_pdf(temp_paths)
    speaker = PaidSpeaker()
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="paid")
    )
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"paid": lambda: speaker, "kokoro": LocalSpeaker}
    )
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    # Primeira rodada: extrai, estima e para aguardando confirmação.
    worker_tasks.process_job(job)
    assert db_module.get_book(book.id).status == "pending_confirmation"

    # Usuário confirma: marca cost_confirmed, devolve o livro à fila e enfileira novo Job.
    db_module.set_book_cost_confirmed(book.id, True)
    db_module.update_book_status(book.id, "uploaded")
    job2 = Job(id="job-2", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job2)

    worker_tasks.process_job(job2)

    fetched = db_module.get_book(book.id)
    assert fetched.status == "ready"
    assert fetched.cost_confirmed is True
    assert (
        speaker.synthesized_texts
    ), "livro confirmado precisa sintetizar com o Speaker pago"
    assert len(audio_store_module.list_chunks(book.id)) == 1


def test_estimate_above_cap_does_not_process_even_when_confirmed(
    temp_paths, monkeypatch
):
    """Teto de segurança: mesmo confirmado, o Speaker pago nunca roda — degrada para a voz local."""
    book = _create_book_and_pdf(temp_paths)
    paid = PaidSpeaker()
    local = LocalSpeaker()
    monkeypatch.setattr(
        config_module,
        "load_config",
        # 20 caracteres × 0.001 = 0.02 > teto de 0.01 → degrada.
        lambda: FakeConfig(speaker="paid", max_cost_per_book=0.01),
    )
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"paid": lambda: paid, "kokoro": lambda: local}
    )
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    # Confirma antes mesmo da primeira rodada — o teto deve continuar barrando o pago.
    db_module.set_book_cost_confirmed(book.id, True)
    db_module.update_book_status(book.id, "uploaded")
    worker_tasks.process_job(job)

    fetched = db_module.get_book(book.id)
    assert paid.synthesized_texts == [], "Speaker pago não pode rodar acima do teto"
    assert local.synthesized_texts, "acima do teto o livro degrada para a voz local"
    assert fetched.status == "ready"
    assert fetched.cost_degraded is True
    assert len(audio_store_module.list_chunks(book.id)) == 1


def test_estimate_happens_before_any_speaker_call(temp_paths, monkeypatch):
    book = _create_book_and_pdf(temp_paths)
    speaker = EstimateAwareSpeaker(book.id)
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="paid")
    )
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"paid": lambda: speaker, "kokoro": LocalSpeaker}
    )
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)
    db_module.set_book_cost_confirmed(book.id, True)
    db_module.update_book_status(book.id, "uploaded")

    # O próprio Speaker falha se a estimativa não estiver persistida quando ele for chamado.
    worker_tasks.process_job(job)

    assert db_module.get_book(book.id).status == "ready"


def test_voice_is_passed_even_when_degraded_to_fallback(temp_paths, monkeypatch):
    """A voz escolhida não pode se perder quando a trava de custo degrada para a voz local (OS-053)."""
    book = _create_book_and_pdf(temp_paths, voice="pm_alex")
    paid = VoiceRecordingSpeaker(cost_per_char=0.001)
    local = VoiceRecordingSpeaker(cost_per_char=0.0)
    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(speaker="paid", max_cost_per_book=0.01),
    )
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": FakeExtractor}
    )
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"paid": lambda: paid, "kokoro": lambda: local}
    )
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)
    db_module.set_book_cost_confirmed(book.id, True)
    db_module.update_book_status(book.id, "uploaded")

    worker_tasks.process_job(job)

    fetched = db_module.get_book(book.id)
    assert fetched.status == "ready"
    assert fetched.cost_degraded is True
    assert paid.voices == [], "Speaker pago não pode rodar acima do teto"
    assert local.voices == ["pm_alex"], "a voz escolhida atravessa a degradação"
