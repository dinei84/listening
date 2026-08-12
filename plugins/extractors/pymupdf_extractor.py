import fitz

from core.models import ExtractedPage
from plugins.extractors.base import Extractor

# Separador entre blocos do PDF (OS-049). É o mesmo que a OS-045 converte em
# pausa de parágrafo no Speaker, então a estrutura do documento cabe no texto
# simples — sem campo novo no ExtractedPage e sem alterar o contrato Extractor.
BLOCK_SEPARATOR = "\n\n"


class PyMuPDFExtractor(Extractor):
    def supports(self, pdf_path: str) -> bool:
        doc = fitz.open(pdf_path)
        for page in doc:
            if page.get_text().strip():
                doc.close()
                return True
        doc.close()
        return False

    def extract(
        self, pdf_path: str, page_range: tuple[int, int] | None = None
    ) -> list[ExtractedPage]:
        doc = fitz.open(pdf_path)
        pages: list[ExtractedPage] = []
        start, end = page_range if page_range else (0, len(doc))
        for i in range(max(0, start), min(len(doc), end)):
            pages.append(
                ExtractedPage(
                    page_number=i + 1,
                    text=_text_with_block_breaks(doc[i]),
                    confidence=1.0,
                    source="pymupdf",
                )
            )
        doc.close()
        return pages


def _text_with_block_breaks(page) -> str:
    """Devolve o texto da página com linha em branco entre blocos do PDF, preservando `\\n` simples dentro de cada bloco."""
    blocos: list[str] = []
    for bloco in page.get_text("dict")["blocks"]:
        # Bloco de imagem não tem 'lines' e não se narra.
        linhas = [
            "".join(span["text"] for span in linha["spans"])
            for linha in bloco.get("lines", [])
        ]
        # `\n` simples entre as linhas do MESMO bloco, e não espaço: a
        # `_fix_hyphenation` da OS-035 procura linha terminada em `-` para
        # recolar palavra partida, e juntar com espaço aqui transformaria
        # "demons-\ntração" em "demons- tração", que ela não sabe consertar.
        texto = "\n".join(linhas).strip()
        if texto:
            blocos.append(texto)
    return BLOCK_SEPARATOR.join(blocos)
