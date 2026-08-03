from abc import ABC, abstractmethod

from core.models import ExtractedPage


class Extractor(ABC):
    """Classe base abstrata para extratores de texto de PDF."""

    @abstractmethod
    def supports(self, pdf_path: str) -> bool:
        """Retorna True se este extractor consegue lidar com o arquivo."""
        ...

    @abstractmethod
    def extract(
        self, pdf_path: str, page_range: tuple[int, int] | None = None
    ) -> list[ExtractedPage]:
        """Extrai texto do PDF. Retorna uma ExtractedPage por página."""
        ...
