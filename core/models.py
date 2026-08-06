from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ExtractedPage(BaseModel):
    page_number: int
    text: str
    confidence: float = 1.0
    source: str


class Chapter(BaseModel):
    id: str
    title: str
    order: int
    text: str
    # Intervalo de páginas (1-based, inclusivo) que o capítulo cobre no PDF (OS-027).
    # Default 1/1 preserva chamadas antigas que não conheciam capítulos reais.
    start_page: int = 1
    end_page: int = 1


class AudioChunk(BaseModel):
    chapter_id: str
    sequence: int
    file_path: str
    duration_seconds: float
    engine_used: str


class Book(BaseModel):
    id: str
    title: str
    original_filename: str
    status: Literal[
        "uploaded",
        "extracting",
        "processing",
        "synthesizing",
        "ready",
        "error",
        "paused",
        "pending_confirmation",
    ]
    chapters: list[Chapter] = []
    created_at: datetime
    error_message: str | None = None
    chunk_total: int | None = None
    language: str | None = None
    # Trava de custo (OS-042): estimativa persistida, flag de confirmação explícita
    # e flag de degradação para voz local quando a estimativa estoura o teto.
    estimated_cost: float | None = None
    cost_confirmed: bool = False
    cost_degraded: bool = False


class ReadingProgress(BaseModel):
    """Posição de leitura atual de um Book — só a atual, sem histórico (OS-028)."""

    book_id: str
    sequence: int
    position_seconds: float
    updated_at: datetime


class Job(BaseModel):
    id: str
    book_id: str
    stage: Literal["extract", "process", "synthesize"]
    status: Literal["queued", "running", "done", "failed"]
    error_message: str | None = None
    priority: int = 0
