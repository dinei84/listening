import logging
import time

from core import config as config_module
from core import pipeline
from core.models import AudioChunk, Job
from plugins import registry as registry_module
from plugins.speakers.base import TransientSpeakerError
from plugins.speakers.kokoro_speaker import LANG_CODE_BY_LANGUAGE
from storage import audio_store, db, uploads

logger = logging.getLogger(__name__)


class _YieldRequested(Exception):
    """Sentinela interna: a síntese foi interrompida porque um Job de prioridade maior entrou na fila (preempção cooperativa, OS-032)."""


def process_job(job: Job) -> None:
    """Roda o pipeline para o Book do job — pulando os AudioChunks já persistidos por uma tentativa anterior — e marca o Book/Job como concluído ou falho. Antes da síntese, estima o custo do livro e aplica a trava de custo (OS-042): estimativa acima de zero sem confirmação explícita deixa o livro aguardando confirmação; estimativa acima do teto degrada para a voz local."""
    cfg = config_module.load_config()
    queue = registry_module.QUEUES[cfg.queue]()

    book = db.get_book(job.book_id)
    if book is None:
        queue.mark_failed(job.id, f"Book {job.book_id} not found")
        return

    pdf_path = uploads.pdf_path_for(job.book_id)

    try:
        # OS-027: o livro é extraído e limpo por capítulo, não mais numa tacada só.
        chapters = pipeline.extract_chapters(str(pdf_path))
        db.create_chapters(job.book_id, chapters)

        # OS-042: a estimativa acontece ANTES de qualquer chamada ao Speaker. A
        # extração já rodou acima, então o texto real está disponível aqui. O custo
        # do Kokoro (cost_per_char == 0.0) dá zero e segue o fluxo antigo sem fricção.
        estimate = sum(
            pipeline.estimate_cost(chapter.text, normalize=book.normalize_text)
            for chapter in chapters
        )
        db.set_book_estimated_cost(job.book_id, estimate)

        cap = cfg.max_cost_per_book
        if estimate > 0 and cap is not None and estimate > cap:
            # Teto de segurança (OS-042): mesmo confirmado, o Speaker pago não roda —
            # degrada para a voz local (fallback_speaker) e segue a síntese normal.
            degraded = True
            db.set_book_cost_degraded(job.book_id, True)
            logger.info(
                "Book %s: estimativa %.6f acima do teto %.6f; degradando para voz local",
                job.book_id,
                estimate,
                cap,
            )
        elif estimate > 0 and not book.cost_confirmed:
            # Confirmação explícita (OS-042): livro pago sem confirmação fica
            # aguardando; o Job desta rodada (extração + estimativa) é encerrado e a
            # confirmação enfileira um Job novo.
            db.update_book_status(job.book_id, "pending_confirmation")
            logger.info(
                "Book %s: estimativa %.6f; aguardando confirmação de custo",
                job.book_id,
                estimate,
            )
            queue.mark_done(job.id)
            return
        else:
            degraded = False

        already_done = {
            chunk.sequence for chunk in audio_store.list_chunks(job.book_id)
        }
        # O total é a soma dos capítulos — a sequence continua global e contínua
        # no livro inteiro, então a checagem de consistência (OS-022) e a barra de
        # progresso (OS-024) seguem valendo sem mudança de semântica.
        chunks_por_capitulo = [
            pipeline.count_text_chunks(chapter.text) for chapter in chapters
        ]
        chunk_count = sum(chunks_por_capitulo)
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
            # OS-051: bater AQUI, e não só no laço de polling. Durante a síntese
            # de um capítulo o worker fica minutos sem voltar ao laço, e sem este
            # batimento um worker trabalhando seria reportado como morto — o
            # oposto do que o sinal existe para dizer.
            db.record_worker_heartbeat()
            # Preempção cooperativa (OS-032): entre um chunk e outro o worker
            # pergunta se existe Job queued de prioridade maior esperando. Se
            # sim, para no fim do chunk corrente (que já foi persistido acima)
            # e devolve o próprio Job para a fila — retomar continua de onde
            # parou via skip_sequences (OS-022).
            if queue.should_yield(job.id):
                raise _YieldRequested()

        lang_code = LANG_CODE_BY_LANGUAGE.get(book.language) if book.language else None
        offset = 0
        for chapter, chapter_chunks in zip(chapters, chunks_por_capitulo):
            pipeline.synthesize_text(
                chapter.text,
                chapter_id=chapter.id,
                on_chunk=_persist,
                skip_sequences=already_done,
                lang_code=lang_code,
                sequence_offset=offset,
                speaker_name=cfg.fallback_speaker if degraded else None,
                normalize=book.normalize_text,
                voice=book.voice,
            )
            offset += chapter_chunks
        db.update_book_status(job.book_id, "ready")
        queue.mark_done(job.id)
    except _YieldRequested:
        # Não é falha: o Job volta para 'queued' preservando a prioridade e o
        # Book fica 'paused' — nada é apagado, os chunks já persistidos é que
        # permitem retomar exatamente de onde parou.
        logger.info(
            "Job %s (book %s) preemptado por Job de prioridade maior; livro pausado",
            job.id,
            job.book_id,
        )
        db.update_book_status(job.book_id, "paused")
        queue.requeue(job.id)
    except TransientSpeakerError as exc:
        # OS-043: retry esgotado numa falha transitória (rede/timeout/429/5xx).
        # Não é bug do pipeline — merece atenção humana, mas o áudio já gerado e
        # persistido está preservado: reprocessar o livro retoma de onde parou (OS-022).
        message = (
            f"{exc} — falha de rede persistente após {cfg.retry_max_attempts} tentativas. "
            "O áudio já sintetizado e persistido está preservado; reprocesse o livro "
            "para retomar do ponto em que parou."
        )
        db.update_book_status(job.book_id, "error", error_message=message)
        queue.mark_failed(job.id, message)
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

    # O worker roda em processo separado do `uvicorn`, então não pode depender de
    # a API ter subido antes para as tabelas existirem. init_db é idempotente
    # (OS-051 — antes disso, só o api/main.py inicializava o banco).
    db.init_db()

    # Assume um único worker ativo por vez (decisão #11): sem heartbeat/lease não há
    # como distinguir um Job de outro worker vivo de um deixado por um worker morto.
    for orphan in queue.requeue_orphaned():
        logger.info(
            "Job %s (book %s) estava órfão em 'running'; devolvido para a fila",
            orphan.id,
            orphan.book_id,
        )

    # Antes do primeiro job: quem sobe o worker precisa ver o sinal na hora, sem
    # esperar um livro entrar na fila.
    db.record_worker_heartbeat()

    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        db.record_worker_heartbeat()
        job = queue.claim_next()
        if job is not None:
            process_job(job)
        else:
            time.sleep(poll_interval)
        iterations += 1


if __name__ == "__main__":
    # Sem isto o root logger fica sem handler: o lastResort do Python emite WARNING
    # em diante, mas todo logger.info do worker (confirmação de custo, retomada,
    # preempção) some sem deixar rastro — o que torna o pipeline indiagnosticável.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # INFO global também liga o INFO das bibliotecas: o httpx narra cada HEAD que o
    # Kokoro faz no HuggingFace e afoga as linhas do pipeline. Em WARNING elas ainda
    # aparecem quando têm algo de fato a dizer.
    for ruidoso in ("httpx", "httpcore", "huggingface_hub", "urllib3", "filelock"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    run_worker()
