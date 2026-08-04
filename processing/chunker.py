import re

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")

# 1000 caracteres: alto o suficiente para poucas chamadas ao Speaker por capítulo
# (menos overhead por chamada), baixo o suficiente para manter o tempo de síntese e
# o tamanho de cada AudioChunk gerado previsíveis. Ponto de partida razoável, não um
# valor "oficial" — documentado no relatório da OS-008.
DEFAULT_MAX_CHARS = 1000


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Divide o texto em pedaços por sentença, nunca cortando uma sentença no meio mesmo que isso exceda max_chars."""
    stripped = text.strip()
    if not stripped:
        return []

    sentences = [s for s in _SENTENCE_BOUNDARY_RE.split(stripped) if s.strip()]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks
