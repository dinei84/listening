import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from core import pipeline
from core.models import Book, Chapter
from storage import db

router = APIRouter()

UPLOAD_DIR = Path("uploads")


@router.post("/books")
async def create_book(file: UploadFile) -> dict[str, str]:
    """Recebe um PDF, roda o pipeline síncrono (extração → limpeza → síntese) e devolve o id e o status final do Book."""
    book_id = str(uuid.uuid4())
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = UPLOAD_DIR / f"{book_id}.pdf"
    with pdf_path.open("wb") as destination:
        shutil.copyfileobj(file.file, destination)

    book = Book(
        id=book_id,
        title=file.filename or book_id,
        original_filename=file.filename or "",
        status="uploaded",
        created_at=datetime.now(UTC),
    )
    db.create_book(book)

    try:
        text = pipeline.extract_clean_text(str(pdf_path))
        chapter = Chapter(id=str(uuid.uuid4()), title=book.title, order=0, text=text)
        pipeline.synthesize_text(text, chapter_id=chapter.id)
        status = "ready"
    # Captura ampla intencional: qualquer falha do pipeline vira status "error",
    # nunca um 500 não tratado — requisito da OS-010.
    except Exception:  # noqa: BLE001
        status = "error"

    db.update_book_status(book_id, status)
    return {"id": book_id, "status": status}


@router.get("/books/{book_id}/status")
async def get_book_status(book_id: str) -> dict[str, str]:
    """Devolve o status persistido de um Book. 404 se o id não existir."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"id": book.id, "status": book.status}
