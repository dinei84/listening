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


class ChainNormalizer(TextNormalizer):
    """Compõe vários TextNormalizer em sequência; é ele mesmo um TextNormalizer.

    Usado para encadear a normalização de notação (OS-038) e a preparação
    prosódica (OS-054) num único passe lógico. Aplica os elos na ordem em que
    foram recebidos e soma os respectivos custos, de modo que a trava de custo
    da OS-042 enxerga a cadeia inteira sem nenhuma alteração em estimate_cost.
    """

    def __init__(self, normalizers: list[TextNormalizer]):
        self._normalizers = list(normalizers)

    @property
    def cost_per_char(self) -> float:
        return sum(normalizer.cost_per_char for normalizer in self._normalizers)

    def normalize(self, text: str) -> str:
        """Aplica cada normalizador da cadeia, na ordem configurada, devolvendo o texto final."""
        for normalizer in self._normalizers:
            text = normalizer.normalize(text)
        return text


class NoOpNormalizer(TextNormalizer):
    """Normalizador padrão: não faz nada, não custa nada, não toca a rede (nível simples)."""

    @property
    def cost_per_char(self) -> float:
        return 0.0

    def normalize(self, text: str) -> str:
        """Devolve o texto exatamente como veio."""
        return text
