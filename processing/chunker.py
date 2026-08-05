import re

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")

# Revertido para 1000 na OS-019: o valor 480 da OS-018 foi calibrado em cima do limite
# de 510 caracteres brutos da API do Kokoro mal usada (generate_from_tokens), não de um
# limite de fonemas de verdade (decisão #14, docs/report/OS-018-report.md). Com a OS-019
# chamando pipeline() (G2P real), o Kokoro passou a dividir texto longo sozinho — mas só
# para inglês (en_tokenize). Para es/fr/hi/it/pt o Kokoro NÃO divide: uma frase que passe
# de 510 fonemas era truncada silenciosamente, corrigido na OS-034 dentro do
# KokoroSpeaker (mede com g2p e divide por fronteira natural). Este valor segue sendo
# só sobre nº de chamadas ao Speaker por capítulo e tamanho prático de cada AudioChunk
# pra playback, a razão original da OS-008.
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
