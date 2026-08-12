import shutil
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from core import config as config_module
from core.models import Book, Job
from plugins import registry as registry_module
from plugins.speakers.kokoro_speaker import LANG_CODE_BY_LANGUAGE
from storage import audio_store, db, progress_store, uploads

router = APIRouter()


class ProgressPayload(BaseModel):
    """Corpo de PUT /books/{id}/progress."""

    sequence: int
    position_seconds: float


# Status em que o worker ainda pode estar escrevendo arquivos/linhas do livro:
# deletar agora arriscaria remover algo em uso ou um update_book_status sobre
# um book_id que não existe mais. "uploaded" foi removido na OS-033 (decisão
# #22): em um livro apenas enfileirado o Job está 'queued' e nada está sendo
# escrito — a justificativa da decisão #17 não se aplica a esse status.
_BLOCKED_DELETE_STATUSES = {"extracting", "processing", "synthesizing"}


@router.post("/books")
async def create_book(
    file: UploadFile,
    language: str | None = Form(default=None),
    normalize_text: bool = Form(default=False),
) -> dict[str, str]:
    """Recebe um PDF (e um idioma opcional), salva em disco, cria o Book e enfileira um Job de processamento assíncrono."""
    book_id = str(uuid.uuid4())
    uploads.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = uploads.pdf_path_for(book_id)
    with pdf_path.open("wb") as destination:
        shutil.copyfileobj(file.file, destination)

    # Idioma inválido/desconhecido degrada para None (detecção automática), nunca erro.
    valid_language = language if language in LANG_CODE_BY_LANGUAGE else None
    book = Book(
        id=book_id,
        title=file.filename or book_id,
        original_filename=file.filename or "",
        status="uploaded",
        created_at=datetime.now(UTC),
        language=valid_language,
        # Opt-in do nível médio (OS-038): sem isso, NoOp e nenhuma rede.
        normalize_text=normalize_text,
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
async def get_book_status(book_id: str) -> dict[str, str | int | None | float | bool]:
    """Devolve o status persistido de um Book, o progresso da síntese (chunks_done/chunks_total), o title, error_message quando status == 'error' e os campos da trava de custo (OS-042). 404 se o id não existir."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    response: dict[str, str | int | None | float | bool] = {
        "id": book.id,
        "title": book.title,
        "status": book.status,
        "chunks_done": len(audio_store.list_chunks(book_id)),
        "chunks_total": book.chunk_total,
        "estimated_cost": book.estimated_cost,
        "cost_confirmed": book.cost_confirmed,
        "cost_degraded": book.cost_degraded,
    }
    if book.status == "error":
        response["error_message"] = book.error_message
    return response


@router.post("/books/{book_id}/confirm")
async def confirm_book_cost(book_id: str) -> dict[str, str]:
    """Confirma a estimativa de custo de um livro pago em espera (OS-042): marca cost_confirmed e re-enfileira o processamento. 404 se o livro não existir; 409 se ele não estiver aguardando confirmação."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.status != "pending_confirmation":
        raise HTTPException(
            status_code=409, detail="Book is not awaiting cost confirmation"
        )

    db.set_book_cost_confirmed(book_id, True)
    db.update_book_status(book_id, "uploaded")

    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()
    job = Job(id=str(uuid.uuid4()), book_id=book_id, stage="process", status="queued")
    queue.enqueue(job)

    return {"id": book_id, "status": "confirmed"}


@router.post("/books/{book_id}/prioritize")
async def prioritize_book(book_id: str) -> dict[str, str]:
    """Coloca o Job do livro no topo da fila — a síntese em andamento de outro livro pausa cooperativamente no fim do chunk corrente. 404 se o livro (ou o Job dele) não existir; 409 se o livro já está pronto/falho, não há o que processar."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()
    job = queue.get_job_for_book(book_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if book.status in ("ready", "error"):
        raise HTTPException(status_code=409, detail="Nothing to process")

    queue.prioritize(job.id)
    return {"id": book_id, "status": "prioritized"}


@router.delete("/books/{book_id}")
async def delete_book(book_id: str) -> dict[str, str]:
    """Remove um Book e todo o seu rastro (áudio, jobs, PDF). 404 se não existir; 409 se o processamento ainda está em andamento."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.status in _BLOCKED_DELETE_STATUSES:
        raise HTTPException(status_code=409, detail="Book is still processing")

    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()
    queue.delete_jobs_for_book(book_id)
    audio_store.delete_chunks(book_id)
    uploads.delete_pdf(book_id)
    # Progresso de leitura vai junto: sem isso, um book_id reciclado herdaria a
    # posição de outro livro (OS-028).
    progress_store.delete_progress(book_id)
    db.delete_book(book_id)
    return {"id": book_id, "status": "deleted"}


@router.get("/books/{book_id}/chapters")
async def get_book_chapters(book_id: str) -> list[dict[str, str | int]]:
    """Devolve os capítulos detectados de um Book, ordenados. Sem o texto do capítulo (seria o livro inteiro). 404 se o id não existir."""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return [
        {
            "id": chapter.id,
            "title": chapter.title,
            "order": chapter.order,
            "start_page": chapter.start_page,
            "end_page": chapter.end_page,
        }
        for chapter in db.list_chapters(book_id)
    ]


@router.get("/worker")
async def get_worker_status() -> dict[str, bool | str | None]:
    """Diz se há worker ativo e quando foi o último batimento. Sem worker nunca é erro — é o estado de quem não subiu o processo."""
    ultimo = db.last_worker_heartbeat()
    return {
        "alive": db.worker_is_alive(),
        "last_heartbeat_at": ultimo.isoformat() if ultimo else None,
    }


@router.get("/books/{book_id}/progress")
async def get_book_progress(book_id: str) -> dict[str, str | int | float]:
    """Devolve a posição de leitura salva de um Book. 404 se o livro não existir ou se a posição nunca foi salva."""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    progress = progress_store.get_progress(book_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="No progress saved for this book")
    return {
        "book_id": progress.book_id,
        "sequence": progress.sequence,
        "position_seconds": progress.position_seconds,
        "updated_at": progress.updated_at.isoformat(),
    }


@router.put("/books/{book_id}/progress")
async def put_book_progress(
    book_id: str, payload: ProgressPayload
) -> dict[str, str | int | float]:
    """Grava a posição de leitura atual de um Book, sobrescrevendo a anterior. 404 se o livro não existir."""
    if db.get_book(book_id) is None:
        raise HTTPException(status_code=404, detail="Book not found")
    progress_store.save_progress(book_id, payload.sequence, payload.position_seconds)
    return {
        "book_id": book_id,
        "sequence": payload.sequence,
        "position_seconds": payload.position_seconds,
    }
