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
        "uploaded", "extracting", "processing", "synthesizing", "ready", "error"
    ]
    chapters: list[Chapter] = []
    created_at: datetime


class Job(BaseModel):
    id: str
    book_id: str
    stage: Literal["extract", "process", "synthesize"]
    status: Literal["queued", "running", "done", "failed"]
    error_message: str | None = None
