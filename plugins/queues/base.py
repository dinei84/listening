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
