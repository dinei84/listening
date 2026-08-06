from abc import ABC, abstractmethod

from core.models import AudioChunk


class SpeakerError(Exception):
    """Erro de síntese lançado por um Speaker."""


class TransientSpeakerError(SpeakerError):
    """Falha transitória (rede, timeout, 429/5xx) — pode ser retentada com backoff."""


class PermanentSpeakerError(SpeakerError):
    """Falha permanente (credencial inválida, texto rejeitado, 4xx não-429) — não adianta retentar."""


class Speaker(ABC):
    """Classe base abstrata para engines de texto-para-fala (TTS)."""

    @property
    @abstractmethod
    def cost_per_char(self) -> float:
        """Custo por caractere. 0.0 para engines locais."""
        ...

    @property
    def max_request_chars(self) -> int | None:
        """Limite de caracteres por requisição do engine; None = sem limite declarado (o texto vai inteiro numa chamada)."""
        return None

    @abstractmethod
    def synthesize(
        self, text: str, voice: str | None = None, lang_code: str | None = None
    ) -> AudioChunk:
        """Recebe texto e devolve áudio sintetizado; lang_code força um idioma específico do engine, pulando a detecção automática."""
        ...
