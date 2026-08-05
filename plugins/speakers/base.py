from abc import ABC, abstractmethod

from core.models import AudioChunk


class Speaker(ABC):
    """Classe base abstrata para engines de texto-para-fala (TTS)."""

    @property
    @abstractmethod
    def cost_per_char(self) -> float:
        """Custo por caractere. 0.0 para engines locais."""
        ...

    @abstractmethod
    def synthesize(
        self, text: str, voice: str | None = None, lang_code: str | None = None
    ) -> AudioChunk:
        """Recebe texto e devolve áudio sintetizado; lang_code força um idioma específico do engine, pulando a detecção automática."""
        ...
