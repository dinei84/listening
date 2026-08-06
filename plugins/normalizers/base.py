from abc import ABC, abstractmethod


class TextNormalizer(ABC):
    """Ajusta o texto antes da síntese (números e abreviações por extenso, pontuação para respiro)."""

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Recebe o texto de um chunk e devolve a versão normalizada. Nunca deve levantar: em qualquer falha, devolver o texto original."""
        ...

    @property
    @abstractmethod
    def cost_per_char(self) -> float:
        """Custo por caractere de entrada. 0.0 para implementações locais."""
        ...


class NoOpNormalizer(TextNormalizer):
    """Normalizador padrão: não faz nada, não custa nada, não toca a rede (nível simples)."""

    @property
    def cost_per_char(self) -> float:
        return 0.0

    def normalize(self, text: str) -> str:
        """Devolve o texto exatamente como veio."""
        return text
