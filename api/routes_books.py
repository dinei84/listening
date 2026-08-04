import shutil
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, UploadFile

from core import config as config_module
from core.models import Book, Job
from plugins import registry as registry_module
from storage import db, uploads

router = APIRouter()


@router.post("/books")
async def create_book(file: UploadFile) -> dict[str, str]:
    """Recebe um PDF, salva em disco, cria o Book e enfileira um Job de processamento assíncrono."""
    book_id = str(uuid.uuid4())
    uploads.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = uploads.pdf_path_for(book_id)
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

    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()
    job = Job(id=str(uuid.uuid4()), book_id=book_id, stage="process", status="queued")
    queue.enqueue(job)

    return {"id": book_id, "status": book.status}


@router.get("/books")
async def list_books() -> list[dict[str, str]]:
    """Devolve todos os livros persistidos, ordenados por criação decrescente. Lista vazia se nenhum livro."""
    books = db.list_books()
    return [
        {
            "id": book.id,
            "title": book.title,
            "status": book.status,
            "created_at": book.created_at.isoformat(),
        }
        for book in books
    ]


@router.get("/books/{book_id}/status")
async def get_book_status(book_id: str) -> dict[str, str]:
    """Devolve o status persistido de um Book. 404 se o id não existir."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"id": book.id, "status": book.status}
