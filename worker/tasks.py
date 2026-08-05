import logging
import time

from core import config as config_module
from core import pipeline
from core.models import AudioChunk, Chapter, Job
from plugins import registry as registry_module
from storage import audio_store, db, uploads

logger = logging.getLogger(__name__)


def process_job(job: Job) -> None:
    """Roda o pipeline para o Book do job — pulando os AudioChunks já persistidos por uma tentativa anterior — e marca o Book/Job como concluído ou falho."""
    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()

    book = db.get_book(job.book_id)
    if book is None:
        queue.mark_failed(job.id, f"Book {job.book_id} not found")
        return

    pdf_path = uploads.pdf_path_for(job.book_id)

    try:
        text = pipeline.extract_clean_text(str(pdf_path))
        chapter = Chapter(id=job.id, title=book.title, order=0, text=text)

        already_done = {
            chunk.sequence for chunk in audio_store.list_chunks(job.book_id)
        }
        chunk_count = pipeline.count_text_chunks(text)
        inconsistency = _resume_inconsistency(already_done, chunk_count)
        if inconsistency is not None:
            logger.error("Book %s: %s", job.book_id, inconsistency)
            db.update_book_status(job.book_id, "error", error_message=inconsistency)
            queue.mark_failed(job.id, inconsistency)
            return

        if already_done:
            logger.info(
                "Book %s: retomando processamento, %d de %d chunks já persistidos",
                job.book_id,
                len(already_done),
                chunk_count,
            )

        db.set_book_chunk_total(job.book_id, chunk_count)
        db.update_book_status(job.book_id, "synthesizing")

        def _persist(chunk: AudioChunk) -> None:
            audio_store.persist_chunks(job.book_id, [chunk])

        pipeline.synthesize_text(
            text,
            chapter_id=chapter.id,
            on_chunk=_persist,
            skip_sequences=already_done,
        )
        db.update_book_status(job.book_id, "ready")
        queue.mark_done(job.id)
    # Captura ampla intencional: mesmo motivo da OS-010 (rota /books) — qualquer
    # falha do pipeline vira Book "error" + Job "failed", nunca derruba o worker.
    except Exception as exc:  # noqa: BLE001
        db.update_book_status(job.book_id, "error", error_message=str(exc))
        queue.mark_failed(job.id, str(exc))


def _resume_inconsistency(already_done: set[int], chunk_count: int) -> str | None:
    """Devolve a descrição da inconsistência entre os chunks persistidos e o texto re-chunkado, ou None se estiver tudo coerente."""
    if not already_done:
        return None

    highest = max(already_done)
    if highest >= chunk_count:
        return (
            "retomada inconsistente: existem AudioChunks persistidos até a sequence "
            f"{highest}, mas o texto re-extraído produz apenas {chunk_count} chunk(s). "
            "O PDF ou a lógica de limpeza/chunking mudou desde a tentativa anterior — "
            "os chunks já gravados não foram apagados; reenvie o livro para "
            "reprocessar do zero."
        )
    return None


def run_worker(poll_interval: float = 1.0, max_iterations: int | None = None) -> None:
    """Loop de polling que consome a JobQueue configurada, retomando Jobs órfãos em 'running' antes de começar; max_iterations existe só para testabilidade."""
    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()

    # Assume um único worker ativo por vez (decisão #11): sem heartbeat/lease não há
    # como distinguir um Job de outro worker vivo de um deixado por um worker morto.
    for orphan in queue.requeue_orphaned():
        logger.info(
            "Job %s (book %s) estava órfão em 'running'; devolvido para a fila",
            orphan.id,
            orphan.book_id,
        )

    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        job = queue.claim_next()
        if job is not None:
            process_job(job)
        else:
            time.sleep(poll_interval)
        iterations += 1


if __name__ == "__main__":
    run_worker()
