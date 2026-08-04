import time

from core import config as config_module
from core import pipeline
from core.models import Chapter, Job
from plugins import registry as registry_module
from storage import audio_store, db, uploads


def process_job(job: Job) -> None:
    """Roda o pipeline para o Book do job e marca o Book/Job como concluído ou falho."""
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
        audio_chunks = pipeline.synthesize_text(text, chapter_id=chapter.id)
        audio_store.persist_chunks(job.book_id, audio_chunks)
        db.update_book_status(job.book_id, "ready")
        queue.mark_done(job.id)
    # Captura ampla intencional: mesmo motivo da OS-010 (rota /books) — qualquer
    # falha do pipeline vira Book "error" + Job "failed", nunca derruba o worker.
    except Exception as exc:  # noqa: BLE001
        db.update_book_status(job.book_id, "error")
        queue.mark_failed(job.id, str(exc))


def run_worker(poll_interval: float = 1.0, max_iterations: int | None = None) -> None:
    """Loop de polling que consome a JobQueue configurada; max_iterations existe só para testabilidade."""
    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()

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
