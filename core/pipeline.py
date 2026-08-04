from core import config as config_module
from core.models import AudioChunk, ExtractedPage
from plugins import registry as registry_module
from processing.chunker import chunk_text
from processing.cleaner import clean_text


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


def synthesize_text(
    text: str, chapter_id: str, max_chars: int | None = None
) -> list[AudioChunk]:
    """Divide o texto em chunks e sintetiza cada um com o Speaker configurado, devolvendo um AudioChunk por chunk com sequence incremental e chapter_id preenchido."""
    chunks = chunk_text(text) if max_chars is None else chunk_text(text, max_chars)
    if not chunks:
        return []

    cfg = config_module.load_config()
    speaker = registry_module.SPEAKERS[cfg.speaker]()

    audio_chunks: list[AudioChunk] = []
    for sequence, piece in enumerate(chunks):
        audio_chunk = speaker.synthesize(piece)
        audio_chunks.append(
            audio_chunk.model_copy(
                update={"chapter_id": chapter_id, "sequence": sequence}
            )
        )
    return audio_chunks
