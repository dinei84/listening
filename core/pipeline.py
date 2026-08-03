from core import config as config_module
from core.models import AudioChunk, ExtractedPage
from plugins import registry as registry_module


def extract_with_fallback(pdf_path: str) -> list[ExtractedPage]:
    """Extrai texto com o extractor primário configurado, caindo para tesseract se supports() for False."""
    cfg = config_module.load_config()
    primary = registry_module.EXTRACTORS[cfg.extractor]()

    if primary.supports(pdf_path):
        return primary.extract(pdf_path)

    fallback = registry_module.EXTRACTORS["tesseract"]()
    return fallback.extract(pdf_path)


def synthesize_text(text: str, chapter_id: str) -> list[AudioChunk]:
    """Sintetiza texto extraído com o Speaker configurado, retornando AudioChunk(s) com chapter_id preenchido."""
    cfg = config_module.load_config()
    speaker = registry_module.SPEAKERS[cfg.speaker]()

    chunk = speaker.synthesize(text)
    return [chunk.model_copy(update={"chapter_id": chapter_id})]
