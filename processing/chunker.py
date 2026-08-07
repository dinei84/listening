import re

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")

# Linha em branco = troca de parágrafo. Preservada até o Speaker desde a OS-045:
# o guia de ritmo trata fim de parágrafo como a maior pausa (1000-1200 ms), e
# juntar tudo com espaço simples fazia essa pausa nunca existir.
_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n")
PARAGRAPH_SEPARATOR = "\n\n"

# Abreviações comuns em PT/EN: o ponto delas NÃO encerra sentença. Sem isso,
# "Segundo o Dr. Silva..." podia virar dois AudioChunk, com pausa no meio do nome
# (OS-035). Lista pequena e local de propósito — spaCy/NLTK seriam ~50MB e uma
# segunda toolchain para um ganho marginal (decisões #12/#13).
_ABBREVIATIONS = {
    "dr",
    "dra",
    "sr",
    "sra",
    "srta",
    "prof",
    "profa",
    "exmo",
    "exma",
    "pag",
    "pág",
    "p",
    "pp",
    "cap",
    "vol",
    "ed",
    "org",
    "trad",
    "fig",
    "ex",
    "etc",
    "cf",
    "op",
    "cit",
    "ibid",
    "art",
    "inc",
    "ltd",
    "co",
    "jr",
    "st",
    "vs",
    "no",
    "nº",
    "num",
    "séc",
    "sec",
    "av",
    "r",
}


def is_false_sentence_boundary(text_before: str) -> bool:
    """True quando o ponto que encerra text_before é de abreviação ou inicial de nome, não de fim de frase."""
    return _is_false_boundary(text_before)


def _is_false_boundary(text_before: str) -> bool:
    """True quando o ponto que precede a fronteira faz parte de abreviação ou inicial de nome, não de fim de frase."""
    # Última "palavra" antes do ponto final do trecho.
    match = re.search(r"([A-Za-zÀ-ÿ0-9º°]+)\.$", text_before.rstrip())
    if match is None:
        return False
    palavra = match.group(1)
    # Inicial de nome ("Robert C. Martin") ou numeração ("1." numa lista).
    if len(palavra) == 1:
        return True
    return palavra.lower() in _ABBREVIATIONS


def _split_sentences(text: str) -> list[str]:
    """Divide o texto em sentenças, remendando as fronteiras falsas criadas por abreviações."""
    partes = _SENTENCE_BOUNDARY_RE.split(text)
    sentencas: list[str] = []
    for parte in partes:
        if sentencas and _is_false_boundary(sentencas[-1]):
            sentencas[-1] = f"{sentencas[-1]} {parte}"
        else:
            sentencas.append(parte)
    return [s for s in sentencas if s.strip()]


def _split_paragraphs(text: str) -> list[list[str]]:
    """Divide o texto em parágrafos e cada parágrafo em sentenças, descartando os vazios."""
    paragrafos = [p for p in _PARAGRAPH_BREAK_RE.split(text) if p.strip()]
    # Quebra de linha simples dentro do parágrafo é continuação da mesma frase (a
    # junção de linhas quebradas do PDF é da OS-035); só a linha em branco separa
    # parágrafo, que é a unidade que o guia de ritmo trata como troca de contexto.
    return [_split_sentences(" ".join(p.split())) for p in paragrafos]


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

    # Cada sentença carrega o separador que a liga à anterior: espaço dentro do
    # mesmo parágrafo, PARAGRAPH_SEPARATOR quando muda de parágrafo. O agrupamento
    # em si não muda — a contagem de chunks continua idêntica, que é o que a
    # checagem de consistência da retomada (OS-022) exige.
    sentences: list[tuple[str, str]] = []
    for paragrafo in _split_paragraphs(stripped):
        for indice, sentence in enumerate(paragrafo):
            primeira_do_paragrafo = indice == 0
            separador = (
                PARAGRAPH_SEPARATOR if primeira_do_paragrafo and sentences else " "
            )
            sentences.append((separador, sentence))

    chunks: list[str] = []
    current = ""
    for separador, sentence in sentences:
        if not current:
            current = sentence
        elif len(current) + len(separador) + len(sentence) <= max_chars:
            current = f"{current}{separador}{sentence}"
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks
