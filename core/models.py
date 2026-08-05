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
    ]
    chapters: list[Chapter] = []
    created_at: datetime
    error_message: str | None = None
    chunk_total: int | None = None
    language: str | None = None


class Job(BaseModel):
    id: str
    book_id: str
    stage: Literal["extract", "process", "synthesize"]
    status: Literal["queued", "running", "done", "failed"]
    error_message: str | None = None
    priority: int = 0
