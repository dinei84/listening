"""Testes da OS-043: limite declarado pelo Speaker + retry com backoff para falha transitória.

Cobertura:
  - Speaker pode declarar limite de caracteres por requisição; quem não declara mantém comportamento
  - KokoroSpeaker não declara limite (regressão OS-034/037: divisão por fonemas continua interna)
  - Falha transitória é retentada com backoff, sem derrubar o livro
  - Falha permanente falha de imediato, sem gastar tentativas
  - Esgotadas as tentativas, chunks já persistidos continuam e a mensagem diz isso
  - Número de tentativas é configurável
"""

import os
import tempfile
from datetime import UTC, datetime

import numpy as np
import pytest
import soundfile as sf

from core import config as config_module
from core import pipeline
from core.models import AudioChunk, Book, ExtractedPage, Job
from plugins import registry as registry_module
from plugins.extractors.base import Extractor
from plugins.queues import sqlite_queue as sqlite_queue_module
from plugins.speakers import kokoro_speaker as kokoro_speaker_module
from plugins.speakers.base import (
    PermanentSpeakerError,
    Speaker,
    TransientSpeakerError,
)
from storage import audio_store as audio_store_module
from storage import db as db_module
from storage import uploads as uploads_module
from worker import tasks as worker_tasks


class FakeConfig:
    def __init__(
        self,
        extractor="fake_extractor",
        speaker="fake_speaker",
        queue="sqlite",
        max_cost_per_book=None,
        fallback_speaker="kokoro",
        retry_max_attempts=3,
        retry_base_delay_seconds=1.0,
        retry_max_delay_seconds=30.0,
    ):
        self.extractor = extractor
        self.speaker = speaker
        self.queue = queue
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


def _write_wav(duration_seconds: float = 0.01, sample_rate: int = 16000) -> str:
    """Escreve um .wav real de PCM (para o pipeline concatenar com soundfile)."""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    samples = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)
    sf.write(path, samples, sample_rate)
    return path


class FlakySpeaker(Speaker):
    """Speaker dublê: falha com erro transitório nas `failures` primeiras chamadas, depois sintetiza."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0
        self.texts = []

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.calls += 1
        self.texts.append(text)
        if self.calls <= self.failures:
            raise TransientSpeakerError("connection reset")
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=_write_wav(),
            duration_seconds=0.01,
            engine_used="flaky",
        )


class AlwaysFailingSpeaker(Speaker):
    """Speaker dublê que sempre lança erro transitório — para provar esgotamento de tentativas."""

    def __init__(self):
        self.calls = 0

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.calls += 1
        raise TransientSpeakerError("connection reset")


class PermanentFailSpeaker(Speaker):
    """Speaker dublê que sempre lança erro permanente (credencial inválida, 4xx não-429)."""

    def __init__(self):
        self.calls = 0

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.calls += 1
        raise PermanentSpeakerError("invalid credentials")


class RecordingSpeaker(Speaker):
    """Speaker dublê que registra os textos recebidos e devolve wav real (para concatenação)."""

    def __init__(self):
        self.texts = []

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.texts.append(text)
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=_write_wav(),
            duration_seconds=0.01,
            engine_used="recording",
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


def _create_book_and_pdf(upload_dir, book_id="book-1"):
    upload_dir.mkdir(parents=True, exist_ok=True)
    uploads_module.pdf_path_for(book_id).write_bytes(b"%PDF-1.4 fake content")
    book = Book(
        id=book_id,
        title="Test Book",
        original_filename="test.pdf",
        status="uploaded",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    db_module.create_book(book)
    return book


def _persist_previous_chunk(book_id, sequence):
    fd, path = tempfile.mkstemp(suffix=".wav")
    with os.fdopen(fd, "wb") as f:
        f.write(b"RIFF-chunk-de-tentativa-anterior")
    audio_store_module.persist_chunks(
        book_id,
        [
            AudioChunk(
                chapter_id="job-1",
                sequence=sequence,
                file_path=path,
                duration_seconds=1.0,
                engine_used="previous_run",
            )
        ],
    )


# --- (a) limite declarado pelo Speaker ----------------------------------------


class LimitedSpeaker(RecordingSpeaker):
    """Speaker com limite declarado de caracteres por requisição."""

    @property
    def max_request_chars(self):
        return 100


def test_speaker_can_declare_own_size_limit(monkeypatch):
    speaker = LimitedSpeaker()
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="limited")
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"limited": lambda: speaker})

    texto = " ".join(f"palavra{i}" for i in range(40))
    assert len(texto) > 100

    chunks = pipeline.synthesize_text(texto, chapter_id="ch1")

    assert len(chunks) == 1, "pedaços do mesmo chunk devem virar um único AudioChunk"
    assert len(speaker.texts) > 1, "o limite declarado deve forçar mais de uma chamada"
    for texto_enviado in speaker.texts:
        assert len(texto_enviado) <= 100
    # Nunca corta palavra no meio: as palavras enviadas reconstroem o original.
    enviadas = [p for texto_enviado in speaker.texts for p in texto_enviado.split()]
    assert enviadas == texto.split()


def test_kokoro_speaker_output_unchanged(monkeypatch):
    """Regressão OS-034/037: o Kokoro NÃO declara limite de caracteres — a divisão por
    fonemas continua interna ao speaker e o pipeline envia o texto inteiro de uma vez.
    """
    speaker = kokoro_speaker_module.KokoroSpeaker()
    assert speaker.max_request_chars is None

    calls = []
    fake_pipeline = type(
        "FakePipeline",
        (),
        {
            "lang_code": "p",
            "g2p": lambda self, text: ("x" * (len(text) * 2), None),
            "__call__": lambda self, text, voice, speed: calls.append(text)
            or iter(
                [
                    type(
                        "R",
                        (),
                        {
                            "output": type(
                                "O",
                                (),
                                {"audio": __import__("torch").ones(1, 100)},
                            )()
                        },
                    )()
                ]
            ),
        },
    )()
    monkeypatch.setattr(
        kokoro_speaker_module.KokoroSpeaker,
        "_build_pipeline",
        lambda self, lang_code: fake_pipeline,
    )

    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(speaker="kokoro")
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"kokoro": lambda: speaker})

    texto = " ".join(f"palavra{i}" for i in range(30))
    chunks = pipeline.synthesize_text(texto, chapter_id="ch1")

    assert len(chunks) == 1
    # O texto inteiro foi enviado de uma vez (sem divisão por caracteres no pipeline):
    # a divisão por fonemas (OS-034) continua acontecendo DENTRO do KokoroSpeaker.
    assert len(calls) == 1
    assert calls[0] == texto


# --- (b) retry com backoff ----------------------------------------------------


def test_transient_failure_is_retried_with_backoff(monkeypatch):
    speaker = FlakySpeaker(failures=2)
    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(
            speaker="flaky", retry_max_attempts=5, retry_base_delay_seconds=0.01
        ),
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"flaky": lambda: speaker})

    sleeps = []
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: sleeps.append(s))

    chunks = pipeline.synthesize_text("Um texto pequeno.", chapter_id="ch1")

    assert len(chunks) == 1
    assert speaker.calls == 3, "2 falhas + 1 sucesso = 3 chamadas"
    assert sleeps == [0.01, 0.02], "backoff exponencial: base, base*2"


def test_permanent_failure_fails_immediately(monkeypatch):
    speaker = PermanentFailSpeaker()
    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(
            speaker="permanent", retry_max_attempts=5, retry_base_delay_seconds=0.01
        ),
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"permanent": lambda: speaker})

    sleeps = []
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(PermanentSpeakerError):
        pipeline.synthesize_text("Um texto pequeno.", chapter_id="ch1")

    assert speaker.calls == 1, "falha permanente não gasta tentativas"
    assert sleeps == []


def test_retry_exhausted_keeps_persisted_chunks(temp_paths, monkeypatch):
    """Esgotadas as tentativas, o livro vai para error MAS os chunks já persistidos
    continuam no banco e a mensagem diz que o áudio está preservado."""
    MULTI_CHUNK_TEXT = "A" * 599 + ". " + "B" * 599 + ". " + "C" * 599 + "."

    class MultiChunkExtractor(Extractor):
        def supports(self, pdf_path):
            return True

        def extract(self, pdf_path, page_range=None):
            return [
                ExtractedPage(
                    page_number=1,
                    text=MULTI_CHUNK_TEXT,
                    confidence=1.0,
                    source="multi_chunk",
                )
            ]

    book = _create_book_and_pdf(temp_paths)
    # Tentativa anterior já persistiu o chunk 0.
    _persist_previous_chunk(book.id, 0)

    speaker = AlwaysFailingSpeaker()
    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(speaker="always", retry_max_attempts=2),
    )
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": MultiChunkExtractor}
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"always": lambda: speaker})
    queue = sqlite_queue_module.SQLiteJobQueue()
    job = Job(id="job-1", book_id=book.id, stage="process", status="queued")
    queue.enqueue(job)

    worker_tasks.process_job(job)

    fetched = db_module.get_book(book.id)
    assert fetched.status == "error"
    assert fetched.error_message
    assert "preservad" in fetched.error_message.lower()
    assert [c.sequence for c in audio_store_module.list_chunks(book.id)] == [
        0
    ], "o chunk já persistido não pode ser perdido"


def test_retry_count_is_configurable(monkeypatch):
    speaker = AlwaysFailingSpeaker()
    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(speaker="always", retry_max_attempts=2),
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"always": lambda: speaker})
    monkeypatch.setattr(pipeline.time, "sleep", lambda s: None)

    with pytest.raises(TransientSpeakerError):
        pipeline.synthesize_text("Um texto pequeno.", chapter_id="ch1")

    assert speaker.calls == 2, "max_attempts=2 deve gerar exatamente 2 chamadas"
