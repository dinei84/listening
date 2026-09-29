from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from storage import audio_store, db

router = APIRouter()


@router.get("/books/{book_id}/audio")
async def list_book_audio(
    book_id: str,
    since: int | None = Query(
        default=None,
        ge=0,
        description="Devolve só os chunks de sequence MAIOR que este valor.",
    ),
) -> list[dict]:
    """Lista os chunks de áudio persistidos de um Book, ordenados por sequence; com `since` devolve só os mais novos que ele. 404 se o livro não existir."""
    book = db.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    # `since` existe para o polling do player não rebaixar a rede: sem ele, um
    # livro de 533 chunks reenviava 51,8 KB a cada 2 s (91 MB por hora de escuta)
    # para um delta que quase sempre é de 0 ou 1 chunk. Omitir o parâmetro mantém
    # o comportamento original, então nenhum cliente antigo quebra.
    chunks = audio_store.list_chunks(book_id, since=since)
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
