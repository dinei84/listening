from collections import Counter

import fitz

from core.models import ExtractedPage
from plugins.extractors.base import Extractor

# Separador entre blocos do PDF (OS-049). É o mesmo que a OS-045 converte em
# pausa de parágrafo no Speaker, então a estrutura do documento cabe no texto
# simples — sem campo novo no ExtractedPage e sem alterar o contrato Extractor.
BLOCK_SEPARATOR = "\n\n"

# Limiares de classificação por estilo (OS-050), relativos ao corpo do próprio
# documento. Medidos em 70 páginas do "Programador Pragmático", corpo a 9,7pt:
# nota de rodapé a 7,0-8,0pt (<=0,85x) e título a 20,0pt (>=1,35x).
SMALL_BLOCK_RATIO = 0.85
HEADING_RATIO = 1.35

# Faixa de topo onde vive o cabeçalho corrente, como fração da altura da página.
# Medido em 10 páginas consecutivas: sempre o primeiro bloco, sempre em y=53,9
# numa página de 708,7 — 7,6% do topo. 10% dá margem sem alcançar o corpo, que
# nas mesmas páginas começa bem abaixo.
HEADER_BAND = 0.10

# Cabeçalho corrente é curto por natureza (medido: 31 a 50 caracteres). Exigir
# isto ALÉM da posição é o que impede a regra de comer um parágrafo legítimo que
# comece no alto da página — o risco declarado na seção 4 da OS-050.
HEADER_MAX_CHARS = 80


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
        # O corpo é medido do documento inteiro, nunca fixado: cada PDF tem o
        # seu, e um limiar absoluto quebraria em todo livro diagramado diferente.
        corpo = _body_size(doc)
        pages: list[ExtractedPage] = []
        start, end = page_range if page_range else (0, len(doc))
        for i in range(max(0, start), min(len(doc), end)):
            pages.append(
                ExtractedPage(
                    page_number=i + 1,
                    text=_narratable_text(doc[i], corpo),
                    confidence=1.0,
                    source="pymupdf",
                )
            )
        doc.close()
        return pages


def _spans(bloco) -> list[dict]:
    """Devolve os spans com texto de um bloco, ignorando bloco de imagem e span vazio."""
    return [
        span
        for linha in bloco.get("lines", [])
        for span in linha["spans"]
        if span["text"].strip()
    ]


def _body_size(doc) -> float:
    """Mede o tamanho de fonte do corpo do documento: o mais frequente ponderado por caractere."""
    contagem: Counter[float] = Counter()
    for page in doc:
        for bloco in page.get_text("dict")["blocks"]:
            for span in _spans(bloco):
                contagem[round(span["size"], 1)] += len(span["text"])
    return contagem.most_common(1)[0][0] if contagem else 0.0


def _is_running_header(
    bloco, primeiro: bool, altura_pagina: float, corpo: float
) -> bool:
    """True quando o bloco é cabeçalho corrente: primeiro da página, no topo, curto e não maior que o corpo."""
    if not primeiro or altura_pagina <= 0:
        return False
    spans = _spans(bloco)
    if not spans:
        return False
    # As três condições juntas, nunca só a posição. O número da página muda a
    # cada página, então o cabeçalho nunca se repete idêntico e escapa do
    # clean_text — mas tanto um parágrafo legítimo quanto um TÍTULO de seção
    # podem começar no alto, e o título é curto como o cabeçalho.
    #
    # O que separa os dois é tipografia: cabeçalho corrente nunca é maior que o
    # corpo (medido: 9,3pt contra 9,7pt), enquanto título é (20,0pt). Sem esta
    # terceira condição, um título no topo da página era descartado — pego pelo
    # teste de regressão da OS-049.
    if corpo and max(span["size"] for span in spans) >= corpo * HEADING_RATIO:
        return False
    no_topo = bloco["bbox"][1] <= altura_pagina * HEADER_BAND
    texto = " ".join(span["text"] for span in spans).strip()
    return no_topo and len(texto) <= HEADER_MAX_CHARS


def _narratable_text(page, corpo: float) -> str:
    """Devolve o texto da página sem o que não é do autor (cabeçalho corrente, número de página, nota de rodapé), com linha em branco entre blocos."""
    blocos: list[str] = []
    com_linhas = [b for b in page.get_text("dict")["blocks"] if "lines" in b]
    for indice, bloco in enumerate(com_linhas):
        spans = _spans(bloco)
        if not spans:
            continue
        if _is_running_header(bloco, indice == 0, page.rect.height, corpo):
            continue
        # Bloco miúdo é nota de rodapé, crédito de imagem ou número de página
        # solto. Descartado como a OS-040 já faz com URL e e-mail: não é prosa
        # do autor e interrompe a frase quando narrado.
        if corpo and max(span["size"] for span in spans) <= corpo * SMALL_BLOCK_RATIO:
            continue
        # `\n` simples entre as linhas do MESMO bloco, e não espaço: a
        # `_fix_hyphenation` da OS-035 procura linha terminada em `-` para
        # recolar palavra partida, e juntar com espaço aqui transformaria
        # "demons-\ntração" em "demons- tração", que ela não sabe consertar.
        texto = "\n".join(
            "".join(span["text"] for span in linha["spans"])
            for linha in bloco.get("lines", [])
        ).strip()
        if texto:
            blocos.append(texto)
    return BLOCK_SEPARATOR.join(blocos)
