import uuid
from collections.abc import Callable

import fitz

from core import config as config_module
from core.models import AudioChunk, Chapter, ExtractedPage
from plugins import registry as registry_module
from processing.chunker import chunk_text
from processing.cleaner import clean_text

# Páginas por capítulo sintético quando o PDF não traz sumário embutido (OS-027).
# Valor arbitrário mas estável: grande o bastante para o cleaner ainda detectar
# header/footer repetido (precisa de >=2 páginas), pequeno o bastante para a
# navegação por capítulo ser útil num livro longo.
SYNTHETIC_CHAPTER_PAGES = 10


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
    """Detecta os capítulos do PDF pelo sumário embutido (nível 1 do TOC) ou, na ausência dele, agrupa páginas em blocos sintéticos; devolve Chapters sem texto preenchido."""
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

    top_level = [entry for entry in toc if entry[0] == 1]
    if top_level:
        starts = [max(1, min(int(entry[2]), total_pages)) for entry in top_level]
        titles = [
            str(entry[1]).strip() or f"Capítulo {i + 1}"
            for i, entry in enumerate(top_level)
        ]
    else:
        starts = list(range(1, total_pages + 1, SYNTHETIC_CHAPTER_PAGES))
        titles = [f"Parte {i + 1}" for i in range(len(starts))]

    chapters: list[Chapter] = []
    for order, (start, title) in enumerate(zip(starts, titles)):
        # O capítulo termina onde o próximo começa; o último vai até o fim do PDF.
        next_start = starts[order + 1] if order + 1 < len(starts) else total_pages + 1
        end = max(start, next_start - 1)
        chapters.append(
            Chapter(
                id=str(uuid.uuid4()),
                title=title,
                order=order,
                text="",
                start_page=start,
                end_page=end,
            )
        )
    return chapters


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
    """Conta em quantos chunks o texto seria dividido, sem sintetizar nada — usado para checar consistência ao retomar um Job interrompido."""
    chunks = chunk_text(text) if max_chars is None else chunk_text(text, max_chars)
    return len(chunks)


def synthesize_text(
    text: str,
    chapter_id: str,
    max_chars: int | None = None,
    on_chunk: Callable[[AudioChunk], None] | None = None,
    skip_sequences: set[int] | None = None,
    lang_code: str | None = None,
    sequence_offset: int = 0,
) -> list[AudioChunk]:
    """Divide o texto em chunks e sintetiza cada um com o Speaker configurado; se on_chunk for passado é chamado com cada AudioChunk assim que ele fica pronto, antes de sintetizar o próximo, as sequences em skip_sequences não são sintetizadas nem aparecem na lista devolvida, lang_code força o idioma do engine em todos os chunks (None = detecção automática) e sequence_offset desloca a numeração para manter a sequence global e contínua entre capítulos."""
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
    speaker = registry_module.SPEAKERS[cfg.speaker]()

    audio_chunks: list[AudioChunk] = []
    for sequence, piece in pending:
        audio_chunk = speaker.synthesize(piece, lang_code=lang_code).model_copy(
            update={"chapter_id": chapter_id, "sequence": sequence}
        )
        audio_chunks.append(audio_chunk)
        if on_chunk is not None:
            on_chunk(audio_chunk)
    return audio_chunks
