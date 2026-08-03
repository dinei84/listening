from datetime import datetime, timezone

import pytest

from core.models import Book, ExtractedPage, Job


def test_book_rejects_invalid_status():
    with pytest.raises(ValueError):
        Book(
            id="book-1",
            title="Test Book",
            original_filename="test.pdf",
            status="invalid_status",
            created_at=datetime.now(timezone.utc),
        )


def test_job_rejects_invalid_status():
    with pytest.raises(ValueError):
        Job(
            id="job-1",
            book_id="book-1",
            stage="extract",
            status="invalid_status",
        )


def test_book_defaults_to_empty_chapters_list():
    book = Book(
        id="book-1",
        title="Test Book",
        original_filename="test.pdf",
        status="uploaded",
        created_at=datetime.now(timezone.utc),
    )
    assert book.chapters == []


def test_extracted_page_defaults_confidence_to_one():
    page = ExtractedPage(
        page_number=1,
        text="Hello world",
        source="pymupdf",
    )
    assert page.confidence == 1.0
