from abc import ABC, abstractmethod

from core.models import Job


class JobQueue(ABC):
    """Enfileira e processa Jobs de forma assíncrona."""

    @abstractmethod
    def enqueue(self, job: Job) -> None:
        """Adiciona um Job à fila, status inicial 'queued'."""
        ...

    @abstractmethod
    def claim_next(self) -> Job | None:
        """Reivindica atomicamente o próximo Job 'queued', marcando como 'running'.
        None se a fila estiver vazia. Deve ser seguro para múltiplos workers
        chamando ao mesmo tempo — nenhum Job pode ser reivindicado duas vezes."""
        ...

    @abstractmethod
    def mark_done(self, job_id: str) -> None:
        """Marca um Job como concluído ('done')."""
        ...

    @abstractmethod
    def mark_failed(self, job_id: str, error_message: str) -> None:
        """Marca um Job como falho ('failed'), registrando a mensagem de erro."""
        ...

    @abstractmethod
    def get_job(self, job_id: str) -> Job | None:
        """Busca um Job pelo id. None se não existir."""
        ...

    @abstractmethod
    def requeue_orphaned(self) -> list[Job]:
        """Reseta para 'queued' todo Job preso em 'running' e devolve os Jobs resetados.
        Chamado na inicialização do worker: sem heartbeat/lease não há como distinguir
        um worker vivo de um que morreu no meio, então assume-se um único worker ativo
        por vez (decisão #11) e todo 'running' encontrado é tratado como órfão."""
        ...

    @abstractmethod
    def delete_jobs_for_book(self, book_id: str) -> None:
        """Remove todos os Jobs de um book_id. Nenhum efeito se não houver Jobs."""
        ...

    @abstractmethod
    def prioritize(self, job_id: str) -> None:
        """Dá ao Job uma prioridade maior que a de qualquer outro Job pendente (queued ou running)."""
        ...

    @abstractmethod
    def should_yield(self, job_id: str) -> bool:
        """Devolve True se existe um Job 'queued' com prioridade maior que a do Job informado."""
        ...

    @abstractmethod
    def requeue(self, job_id: str) -> None:
        """Devolve um Job individual para 'queued', preservando a prioridade."""
        ...

    @abstractmethod
    def get_job_for_book(self, book_id: str) -> Job | None:
        """Busca o Job de um book_id (o mais recente). None se o livro não tiver Job."""
        ...
