import re

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")

# Recalibrado na OS-018: o Kokoro (via KokoroSpeaker.synthesize) rejeita qualquer texto
# acima de 510 caracteres com "Phoneme string too long" — validado empiricamente contra
# o Kokoro real como um limite de caractere, não de densidade de texto (ver
# docs/report/OS-018-report.md). 480 dá uma margem de segurança abaixo de 510; sentenças
# isoladas que ainda assim excedam o limite são cobertas pelo split-retry do
# KokoroSpeaker, não por este valor.
DEFAULT_MAX_CHARS = 480


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
