import os
import re
import tempfile
import time
import uuid
from collections.abc import Callable
from itertools import pairwise

import fitz
import numpy as np
import soundfile as sf

from core import config as config_module
from core.models import AudioChunk, Chapter, ExtractedPage
from plugins import registry as registry_module
from plugins.speakers.base import TransientSpeakerError
from processing.chunker import chunk_text
from processing.cleaner import clean_text
from processing.sanitizer import sanitize_text

# Páginas por capítulo sintético quando o PDF não traz sumário embutido (OS-027).
# Valor arbitrário mas estável: grande o bastante para o cleaner ainda detectar
# header/footer repetido (precisa de >=2 páginas), pequeno o bastante para a
# navegação por capítulo ser útil num livro longo.
SYNTHETIC_CHAPTER_PAGES = 10

# Fração máxima do livro que um único capítulo pode cobrir antes de ser considerado
# inútil para navegação (OS-036). Um TOC cujo nível 1 só lista o front matter fazia o
# último capítulo herdar todo o resto — medido: "Sobre o Autor" com 415 de 446 páginas
# (93% do livro) e 320 chunks. Usado para escolher o nível do TOC e para subdividir o
# que ainda ficar grande demais.
MAX_CHAPTER_FRACTION = 0.25


def extract_with_fallback(pdf_path: str) -> list[ExtractedPage]:
    """Extrai texto com o extractor primário configurado, caindo para tesseract se supports() for False."""
    cfg = config_module.load_config()
    primary = registry_module.EXTRACTORS[cfg.extractor]()

    if primary.supports(pdf_path):
        return primary.extract(pdf_path)

    fallback = registry_module.EXTRACTORS["tesseract"]()
    return fallback.extract(pdf_path)


def extract_clean_text(pdf_path: str) -> str:
    """Extrai o PDF com fallback e devolve o texto de todas as páginas já limpo (headers/footers repetidos removidos, hifenização corrigida)."""
    pages = extract_with_fallback(pdf_path)
    return clean_text([page.text for page in pages])


def detect_chapters(pdf_path: str, total_pages: int | None = None) -> list[Chapter]:
    """Detecta os capítulos do PDF escolhendo o nível mais útil do sumário embutido (ou blocos sintéticos, se não houver TOC), subdividindo capítulos desproporcionais e cobrindo as páginas iniciais órfãs; devolve Chapters sem texto preenchido."""
    toc: list = []
    try:
        doc = fitz.open(pdf_path)
        try:
            # get_toc() lê os bookmarks do próprio PDF — é propriedade do arquivo,
            # não do extractor configurado, então vale para PDF nativo ou escaneado.
            toc = doc.get_toc()
            if total_pages is None:
                total_pages = len(doc)
        finally:
            doc.close()
    # Captura ampla intencional: se o fitz não conseguir abrir o arquivo, isso não
    # pode derrubar o livro — quem extrai o texto é o Extractor configurado, que
    # pode ser OCR e ter sucesso onde o fitz falha. Sem TOC, cai no sintético; a
    # falha real, se houver, aparece na extração.
    except Exception:  # noqa: BLE001
        toc = []

    if not total_pages:
        return []

    marcos = _toc_milestones(toc, total_pages)
    if not marcos:
        marcos = [
            (pagina, f"Parte {i + 1}")
            for i, pagina in enumerate(
                range(1, total_pages + 1, SYNTHETIC_CHAPTER_PAGES)
            )
        ]

    # Páginas anteriores ao primeiro marco não podem sumir (OS-036): o primeiro
    # capítulo passa a começar na página 1. Antes elas ficavam fora de todos os
    # intervalos e o texto delas nunca era sintetizado.
    primeira_pagina, primeiro_titulo = marcos[0]
    if primeira_pagina > 1:
        marcos[0] = (1, primeiro_titulo)

    intervalos: list[tuple[int, int, str]] = []
    for i, (inicio, titulo) in enumerate(marcos):
        proximo = marcos[i + 1][0] if i + 1 < len(marcos) else total_pages + 1
        intervalos.append((inicio, max(inicio, proximo - 1), titulo))

    return [
        Chapter(
            id=str(uuid.uuid4()),
            title=titulo,
            order=order,
            text="",
            start_page=inicio,
            end_page=fim,
        )
        for order, (inicio, fim, titulo) in enumerate(
            _subdivide_oversized(intervalos, total_pages)
        )
    ]


def _is_descriptive(title: str) -> bool:
    """True se o título diz algo além de um número/algarismo romano (ex: '1', 'IV')."""
    limpo = title.strip()
    if not limpo:
        return False
    return not re.fullmatch(r"[\dIVXLCDM]+[.)]?", limpo, flags=re.IGNORECASE)


def _toc_milestones(toc: list, total_pages: int) -> list[tuple[int, str]]:
    """Escolhe o nível do TOC que dá a estrutura mais útil e devolve os marcos (página inicial, título) desse nível, já ordenados."""
    if not toc:
        return []

    # Melhor título disponível para cada página, olhando TODOS os níveis: livros
    # costumam pôr o número do capítulo num nível e o título em outro, na mesma
    # página ("1" no nível 4, "O que são Design e Arquitetura?" no nível 5).
    melhor_titulo: dict[int, str] = {}
    for nivel, titulo, pagina in ((e[0], str(e[1]), int(e[2])) for e in toc):
        del nivel
        pagina = max(1, min(pagina, total_pages))
        atual = melhor_titulo.get(pagina)
        if atual is None or (not _is_descriptive(atual) and _is_descriptive(titulo)):
            melhor_titulo[pagina] = titulo.strip()

    niveis = sorted({int(e[0]) for e in toc})
    candidatos: list[tuple[float, int, list[int]]] = []
    for nivel in niveis:
        paginas = sorted(
            {max(1, min(int(e[2]), total_pages)) for e in toc if int(e[0]) == nivel}
        )
        if not paginas:
            continue
        # Maior capítulo que esse nível produziria, como fração do livro.
        limites = [*paginas, total_pages + 1]
        maior = max(b - a for a, b in pairwise(limites))
        candidatos.append((maior / total_pages, nivel, paginas))

    if not candidatos:
        return []

    # Preferir o nível mais raso cujo maior capítulo caiba no limite; se nenhum
    # couber, ficar com o que tem o menor "maior capítulo" (o mais equilibrado).
    aceitaveis = [c for c in candidatos if c[0] <= MAX_CHAPTER_FRACTION]
    fracao, _, paginas = (
        min(aceitaveis, key=lambda c: c[1])
        if aceitaveis
        else min(candidatos, key=lambda c: c[0])
    )
    del fracao

    return [
        (pagina, melhor_titulo.get(pagina) or f"Capítulo {i + 1}")
        for i, pagina in enumerate(paginas)
    ]


def _subdivide_oversized(
    intervalos: list[tuple[int, int, str]], total_pages: int
) -> list[tuple[int, int, str]]:
    """Quebra em partes os capítulos que sozinhos cobrem uma fatia grande demais do livro, preservando o título original com sufixo."""
    limite = max(SYNTHETIC_CHAPTER_PAGES, int(total_pages * MAX_CHAPTER_FRACTION))
    resultado: list[tuple[int, int, str]] = []
    for inicio, fim, titulo in intervalos:
        paginas = fim - inicio + 1
        if paginas <= limite:
            resultado.append((inicio, fim, titulo))
            continue
        # Divide em blocos de no máximo `limite` páginas, mantendo o título.
        parte = 1
        cursor = inicio
        while cursor <= fim:
            bloco_fim = min(cursor + limite - 1, fim)
            resultado.append((cursor, bloco_fim, f"{titulo} (parte {parte})"))
            cursor = bloco_fim + 1
            parte += 1
    return resultado


def extract_chapters(pdf_path: str) -> list[Chapter]:
    """Extrai o PDF uma vez e devolve os capítulos detectados com o texto limpo de cada um (limpeza feita por capítulo, sobre as páginas dele)."""
    pages = extract_with_fallback(pdf_path)
    if not pages:
        return []

    # O total de páginas vem do que o Extractor realmente leu — assim a detecção
    # funciona mesmo quando o fitz não consegue abrir o arquivo (ex: PDF que só o
    # OCR dá conta), e o intervalo de páginas bate com o texto disponível.
    total_pages = max(page.page_number for page in pages)
    chapters = detect_chapters(pdf_path, total_pages=total_pages)

    if not chapters:
        return []

    by_number = {page.page_number: page.text for page in pages}
    filled: list[Chapter] = []
    for chapter in chapters:
        chapter_pages = [
            by_number[number]
            for number in range(chapter.start_page, chapter.end_page + 1)
            if number in by_number
        ]
        # clean_text roda por capítulo: header/footer repetido é detectado dentro
        # do próprio capítulo, e o texto de um capítulo nunca vaza para outro.
        filled.append(chapter.model_copy(update={"text": clean_text(chapter_pages)}))
    return filled


def count_text_chunks(text: str, max_chars: int | None = None) -> int:
    """Conta em quantos chunks o texto seria dividido, sem sintetizar nada — usado para checar consistência ao retomar um Job interrompido. O texto passa pela sanitização (OS-040) para o total bater com o que a síntese realmente produz."""
    text = sanitize_text(text)
    chunks = chunk_text(text) if max_chars is None else chunk_text(text, max_chars)
    return len(chunks)


def estimate_cost(text: str) -> float:
    """Estima o custo de sintetizar o texto com o Speaker configurado, a partir do texto real (sanitizado, como a síntese o recebe): total de caracteres × cost_per_char do Speaker."""
    text = sanitize_text(text)
    cfg = config_module.load_config()
    speaker = registry_module.SPEAKERS[cfg.speaker]()
    return len(text) * speaker.cost_per_char


def _split_by_char_limit(text: str, limit: int | None) -> list[str]:
    """Divide o texto em pedaços que não excedam `limit` caracteres, sem nunca cortar uma palavra ao meio; limit None devolve o texto inteiro num pedaço só."""
    if limit is None or len(text) <= limit:
        return [text]
    if not re.search(r"\s", text):
        return [text]
    words = text.split()
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _merge_wav_files(paths: list[str]) -> tuple[str, float]:
    """Concatena arquivos .wav PCM16 no mesmo sample rate num único arquivo e devolve (caminho, duração em segundos)."""
    sample_rate = None
    parts: list[np.ndarray] = []
    for path in paths:
        data, sr = sf.read(path, dtype="float32")
        if sample_rate is None:
            sample_rate = sr
        parts.append(data)
    combined = np.concatenate(parts)
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    sf.write(path, combined, sample_rate or 24000)
    return path, len(combined) / (sample_rate or 24000)


def _synthesize_with_retry(
    speaker,
    text: str,
    lang_code: str | None,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
) -> AudioChunk:
    """Chama speaker.synthesize repetindo falha transitória com backoff exponencial (base × 2^(n-1), teto em max_delay); falha permanente não é retentada e sobe de imediato."""
    for attempt in range(1, max_attempts + 1):
        try:
            return speaker.synthesize(text, lang_code=lang_code)
        except TransientSpeakerError:
            if attempt >= max_attempts:
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            time.sleep(delay)
    raise RuntimeError("unreachable")


def synthesize_text(
    text: str,
    chapter_id: str,
    max_chars: int | None = None,
    on_chunk: Callable[[AudioChunk], None] | None = None,
    skip_sequences: set[int] | None = None,
    lang_code: str | None = None,
    sequence_offset: int = 0,
    speaker_name: str | None = None,
) -> list[AudioChunk]:
    """Divide o texto em chunks e sintetiza cada um com o Speaker configurado; se on_chunk for passado é chamado com cada AudioChunk assim que ele fica pronto, antes de sintetizar o próximo, as sequences em skip_sequences não são sintetizadas nem aparecem na lista devolvida, lang_code força o idioma do engine em todos os chunks (None = detecção automática), sequence_offset desloca a numeração para manter a sequence global e contínua entre capítulos e speaker_name sobrescreve o Speaker usado nesta chamada (None = o configurado; usado pela trava de custo ao degradar para a voz local). Falhas transitórias (TransientSpeakerError) são retentadas com backoff conforme a config retry (OS-043). O texto passa pela sanitização (OS-040) antes de virar chunk."""
    text = sanitize_text(text)
    chunks = chunk_text(text) if max_chars is None else chunk_text(text, max_chars)
    already_done = skip_sequences or set()
    # skip_sequences usa a numeração GLOBAL do livro, então o offset é aplicado
    # antes da comparação (OS-027).
    pending = [
        (sequence_offset + index, piece)
        for index, piece in enumerate(chunks)
        if (sequence_offset + index) not in already_done
    ]
    if not pending:
        return []

    cfg = config_module.load_config()
    speaker = registry_module.SPEAKERS[speaker_name or cfg.speaker]()
    # OS-043: se o Speaker declarar limite de caracteres por requisição, o texto do
    # chunk é dividido em pedaços que respeitam o limite (nunca cortando palavra) e
    # os áudios são concatenados num único AudioChunk — mesma granularidade de sempre.
    char_limit = getattr(speaker, "max_request_chars", None)

    audio_chunks: list[AudioChunk] = []
    for sequence, piece in pending:
        pieces = _split_by_char_limit(piece, char_limit)
        sub_chunks = [
            _synthesize_with_retry(
                speaker,
                sub,
                lang_code,
                cfg.retry_max_attempts,
                cfg.retry_base_delay_seconds,
                cfg.retry_max_delay_seconds,
            )
            for sub in pieces
        ]
        if len(sub_chunks) == 1:
            audio_chunk = sub_chunks[0]
        else:
            merged_path, duration = _merge_wav_files([c.file_path for c in sub_chunks])
            audio_chunk = sub_chunks[0].model_copy(
                update={"file_path": merged_path, "duration_seconds": duration}
            )
        audio_chunk = audio_chunk.model_copy(
            update={"chapter_id": chapter_id, "sequence": sequence}
        )
        audio_chunks.append(audio_chunk)
        if on_chunk is not None:
            on_chunk(audio_chunk)
    return audio_chunks
