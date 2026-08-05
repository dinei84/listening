from itertools import pairwise

import fitz

from core import config as config_module
from core import pipeline
from core.models import ExtractedPage
from plugins import registry as registry_module
from plugins.extractors.base import Extractor


class FakeConfig:
    def __init__(self, extractor="fake_extractor", speaker="fake_speaker"):
        self.extractor = extractor
        self.speaker = speaker
        self.queue = "sqlite"


class PagedExtractor(Extractor):
    """Devolve uma página por página real do PDF, com texto identificável por número."""

    def supports(self, pdf_path):
        return True

    def extract(self, pdf_path, page_range=None):
        doc = fitz.open(pdf_path)
        total = len(doc)
        doc.close()
        return [
            ExtractedPage(
                page_number=i + 1,
                text=f"Conteudo unico da pagina {i + 1}.",
                confidence=1.0,
                source="paged",
            )
            for i in range(total)
        ]


def _pdf_with_toc(tmp_path, pages=9, toc=None):
    """Cria um PDF real com N páginas e, se toc for passado, com sumário embutido."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Pagina {i + 1}")
    if toc:
        doc.set_toc(toc)
    path = tmp_path / "book.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_detect_chapters_reads_toc_when_present(tmp_path):
    pdf = _pdf_with_toc(
        tmp_path,
        pages=9,
        toc=[
            [1, "Primeiro Capitulo", 1],
            [1, "Segundo Capitulo", 4],
            [1, "Terceiro", 7],
        ],
    )

    chapters = pipeline.detect_chapters(pdf)

    assert [c.title for c in chapters] == [
        "Primeiro Capitulo",
        "Segundo Capitulo",
        "Terceiro",
    ]
    assert [c.order for c in chapters] == [0, 1, 2]
    assert [(c.start_page, c.end_page) for c in chapters] == [(1, 3), (4, 6), (7, 9)]


def test_detect_chapters_ignores_sub_levels_of_toc(tmp_path):
    pdf = _pdf_with_toc(
        tmp_path,
        pages=6,
        toc=[
            [1, "Capitulo Um", 1],
            [2, "Secao 1.1", 2],
            [3, "Subsecao 1.1.1", 2],
            [1, "Capitulo Dois", 4],
        ],
    )

    chapters = pipeline.detect_chapters(pdf)

    assert [c.title for c in chapters] == ["Capitulo Um", "Capitulo Dois"]
    assert [(c.start_page, c.end_page) for c in chapters] == [(1, 3), (4, 6)]


def test_detect_chapters_falls_back_to_synthetic_grouping_when_no_toc(tmp_path):
    pdf = _pdf_with_toc(tmp_path, pages=25, toc=None)

    chapters = pipeline.detect_chapters(pdf)

    assert len(chapters) > 1, "PDF sem TOC deve gerar capítulos sintéticos"
    assert chapters[0].start_page == 1
    assert chapters[-1].end_page == 25
    # Contíguos e sem buracos: cada capítulo começa logo após o fim do anterior.
    for anterior, seguinte in pairwise(chapters):
        assert seguinte.start_page == anterior.end_page + 1
    assert all(c.title for c in chapters), "capítulo sintético precisa de título"


def test_detect_chapters_single_page_pdf_without_toc(tmp_path):
    pdf = _pdf_with_toc(tmp_path, pages=1, toc=None)

    chapters = pipeline.detect_chapters(pdf)

    assert len(chapters) == 1
    assert (chapters[0].start_page, chapters[0].end_page) == (1, 1)


def test_extract_chapters_fills_text_from_pages_of_each_chapter(tmp_path, monkeypatch):
    pdf = _pdf_with_toc(tmp_path, pages=6, toc=[[1, "Um", 1], [1, "Dois", 4]])
    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "EXTRACTORS", {"fake_extractor": PagedExtractor}
    )

    chapters = pipeline.extract_chapters(pdf)

    assert len(chapters) == 2
    # Cada capítulo só contém o texto das SUAS páginas.
    assert "pagina 1" in chapters[0].text
    assert "pagina 3" in chapters[0].text
    assert "pagina 4" not in chapters[0].text
    assert "pagina 4" in chapters[1].text
    assert "pagina 6" in chapters[1].text
    assert "pagina 1" not in chapters[1].text


def test_synthesize_text_applies_sequence_offset(monkeypatch):
    import os
    import tempfile

    from core.models import AudioChunk
    from plugins.speakers.base import Speaker

    class FakeSpeaker(Speaker):
        @property
        def cost_per_char(self):
            return 0.0

        def synthesize(self, text, voice=None, lang_code=None):
            fd, path = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(b"RIFF")
            return AudioChunk(
                chapter_id="",
                sequence=0,
                file_path=path,
                duration_seconds=1.0,
                engine_used="fake",
            )

    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: FakeSpeaker()}
    )

    texto = "Frase um. Frase dois. Frase tres."
    chunks = pipeline.synthesize_text(
        texto, chapter_id="cap-2", max_chars=15, sequence_offset=10
    )

    assert [c.sequence for c in chunks] == [10, 11, 12]


def test_synthesize_text_offset_respects_skip_sequences(monkeypatch):
    import os
    import tempfile

    from core.models import AudioChunk
    from plugins.speakers.base import Speaker

    sintetizados = []

    class CountingSpeaker(Speaker):
        @property
        def cost_per_char(self):
            return 0.0

        def synthesize(self, text, voice=None, lang_code=None):
            sintetizados.append(text)
            fd, path = tempfile.mkstemp(suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(b"RIFF")
            return AudioChunk(
                chapter_id="",
                sequence=0,
                file_path=path,
                duration_seconds=1.0,
                engine_used="fake",
            )

    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module, "SPEAKERS", {"fake_speaker": lambda: CountingSpeaker()}
    )

    texto = "Frase um. Frase dois. Frase tres."
    # skip_sequences usa a numeração GLOBAL (com offset aplicado)
    chunks = pipeline.synthesize_text(
        texto,
        chapter_id="cap-2",
        max_chars=15,
        sequence_offset=10,
        skip_sequences={10, 11},
    )

    assert [c.sequence for c in chunks] == [12]
    assert len(sintetizados) == 1
