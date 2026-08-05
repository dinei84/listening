from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from storage import audio_store, db

router = APIRouter()


@router.get("/books/{book_id}/audio")
async def list_book_audio(book_id: str) -> list[dict]:
    """Lista os chunks de áudio persistidos de um Book, ordenados por sequence. 404 se o livro não existir."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    chunks = audio_store.list_chunks(book_id)
    return [
        {
            "sequence": chunk.sequence,
            # chapter_id acompanha cada chunk desde a OS-027; exposto aqui na OS-029
            # para o player mapear trecho → capítulo sem uma chamada extra.
            "chapter_id": chunk.chapter_id,
            "duration_seconds": chunk.duration_seconds,
            "url": f"/books/{book_id}/audio/{chunk.sequence}",
        }
        for chunk in chunks
    ]


@router.get("/books/{book_id}/audio/{sequence}")
async def get_book_audio_chunk(book_id: str, sequence: int) -> FileResponse:
    """Serve os bytes de um chunk de áudio específico. 404 se o livro ou o chunk não existir."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    chunk = audio_store.get_chunk(book_id, sequence)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Audio chunk not found")

    return FileResponse(chunk.file_path, media_type="audio/wav")
