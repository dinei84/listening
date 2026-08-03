# OS-005 — Relatorio de entrega (spike)

**Data:** 2026-08-03
**Branch:** `main`
**Commit(s) relevante(s):** N/A (spike de pesquisa; sem commit nesta execucao)

## 1. Resumo do que foi feito

OS-005 retomada apos desbloqueio do ambiente. O experimento real com Tesseract foi executado sobre 4 fixtures locais de qualidade diferente, com coleta de confidence por palavra via `pytesseract.image_to_data()`. Foi levantada tambem a forma como PaddleOCR expoe confidence na documentacao oficial (`rec_score` / `rec_scores`), sem instalacao/validacao empirica local.

## 2. Checklist de DoD

### Checklist especifica da OS-005

- [x] Relatorio explica, com fonte, como o confidence score do Tesseract funciona
- [x] Relatorio explica, com fonte, como funcionaria o confidence score do PaddleOCR (documental)
- [x] Ao menos 3 execucoes reais do Tesseract sobre fixtures de qualidade diferente, com numeros reais colados
- [x] Recomendacao final com numero concreto de threshold
- [x] Recomendacao registrada em `PROJECT_STATE.md` como proposta pendente de aprovacao (decisao #8)
- [x] Nenhuma chamada a API paga (Cloud OCR)
- [x] Nao houve bloqueio de instalacao nesta retomada (tesseract ja estava instalado)

## 3. Experimentos rodados

### 3.1 Script reproduzivel

Arquivo: `scripts/spike_ocr_confidence.py`

- Usa `pytesseract.image_to_data(..., output_type=DICT)`
- Filtra palavras com `text != ""` e `conf >= 0`
- Calcula `avg_confidence_words`
- Imprime linhas detalhadas (TSV-like) em JSON

### 3.2 Fixtures usadas

- `tests/fixtures/ocr/clear_text.png` (texto nitido)
- `tests/fixtures/ocr/degraded_text.png` (degradacao moderada)
- `tests/fixtures/ocr/very_degraded_text.png` (degradacao severa)
- `tests/fixtures/ocr/native_pdf_rendered.png` (PDF nativo renderizado como imagem)

## 4. Evidencias e fontes

### 4.1 Tesseract confidence (fonte oficial)

Fonte: `https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html`

- Secao TSV mostra coluna `conf` e valores por palavra (`level=5`), com `-1` em niveis estruturais.
- Secao hOCR mostra `x_wconf` por palavra.

### 4.2 pytesseract confidence (fonte oficial)

Fonte: `https://raw.githubusercontent.com/madmaze/pytesseract/master/README.rst`

- `image_to_data` retorna "box boundaries, confidences, and other information".
- Exemplo explicito de uso para extrair confidences.

### 4.3 PaddleOCR confidence (fonte oficial, documental)

Fonte (doc oficial): `https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html`

Trechos da propria documentacao (extraidos):

- Exemplo de retorno de reconhecimento: `{'res': {..., 'rec_text': '...', 'rec_score': 0.982...}}`
- Explicacao do campo: `rec_score: The confidence score of the predicted text for the text line image`
- No pipeline OCR, aparece `rec_scores` (array de scores por item reconhecido)

Status: **nao validado empiricamente aqui** (sem instalacao/execucao local de PaddleOCR neste spike).

## 5. Saida de comandos relevantes (bruta)

### Comando: `tesseract --version 2>&1`

```text
tesseract 5.3.4
 leptonica-1.82.0
  libgif 5.2.1 : libjpeg 8d (libjpeg-turbo 2.1.5) : libpng 1.6.43 : libtiff 4.5.1 : zlib 1.3 : libwebp 1.3.2 : libopenjp2 2.5.0
 Found AVX2
 Found AVX
 Found FMA
 Found SSE4.1
 Found OpenMP 201511
 Found libarchive 3.7.2 zlib/1.3 liblzma/5.4.5 bz2lib/1.0.8 liblz4/1.9.4 libzstd/1.5.5
 Found libcurl/8.5.0 OpenSSL/3.0.13 zlib/1.3 brotli/1.1.0 zstd/1.5.5 libidn2/2.3.7 libpsl/0.21.2 (+libidn2/2.3.7) libssh/0.10.6/openssl/zlib nghttp2/1.59.0 librtmp/2.3 OpenLDAP/2.6.10
```

### Comando: `python3 scripts/spike_ocr_confidence.py`

```text
# Tesseract confidence experiment
tesseract_version:
5.3.4

## Fixture
tests/fixtures/ocr/clear_text.png
words_counted: 9
avg_confidence_words: 90.33333333333333
rows_json:
[
  {
    "idx": 0,
    "level": 1,
    "page_num": 1,
    "block_num": 0,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 300,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 1,
    "level": 2,
    "page_num": 1,
    "block_num": 1,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 50,
    "top": 112,
    "width": 1550,
    "height": 61,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 2,
    "level": 3,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 0,
    "word_num": 0,
    "left": 50,
    "top": 112,
    "width": 1550,
    "height": 61,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 3,
    "level": 4,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 0,
    "left": 50,
    "top": 112,
    "width": 1550,
    "height": 61,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 4,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 1,
    "left": 50,
    "top": 113,
    "width": 123,
    "height": 47,
    "conf": 96.0,
    "text": "THE"
  },
  {
    "idx": 5,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 2,
    "left": 202,
    "top": 112,
    "width": 200,
    "height": 56,
    "conf": 96.0,
    "text": "QUICK"
  },
  {
    "idx": 6,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 3,
    "left": 427,
    "top": 112,
    "width": 238,
    "height": 49,
    "conf": 96.0,
    "text": "BROWN"
  },
  {
    "idx": 7,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 4,
    "left": 697,
    "top": 112,
    "width": 104,
    "height": 49,
    "conf": 95.0,
    "text": "FOX"
  },
  {
    "idx": 8,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 5,
    "left": 836,
    "top": 112,
    "width": 190,
    "height": 61,
    "conf": 95.0,
    "text": "JUMPS"
  },
  {
    "idx": 9,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 6,
    "left": 1063,
    "top": 112,
    "width": 172,
    "height": 49,
    "conf": 96.0,
    "text": "OVER"
  },
  {
    "idx": 10,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 7,
    "left": 1264,
    "top": 112,
    "width": 70,
    "height": 49,
    "conf": 95.0,
    "text": "13"
  },
  {
    "idx": 11,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 8,
    "left": 1365,
    "top": 113,
    "width": 158,
    "height": 47,
    "conf": 92.0,
    "text": "LAZY"
  },
  {
    "idx": 12,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 9,
    "left": 1549,
    "top": 113,
    "width": 51,
    "height": 47,
    "conf": 52.0,
    "text": "D"
  }
]

## Fixture
tests/fixtures/ocr/degraded_text.png
words_counted: 9
avg_confidence_words: 94.0
rows_json:
[
  {
    "idx": 0,
    "level": 1,
    "page_num": 1,
    "block_num": 0,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 300,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 1,
    "level": 2,
    "page_num": 1,
    "block_num": 1,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 49,
    "top": 110,
    "width": 1551,
    "height": 64,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 2,
    "level": 3,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 0,
    "word_num": 0,
    "left": 49,
    "top": 110,
    "width": 1551,
    "height": 64,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 3,
    "level": 4,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 0,
    "left": 49,
    "top": 110,
    "width": 1551,
    "height": 64,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 4,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 1,
    "left": 49,
    "top": 111,
    "width": 125,
    "height": 51,
    "conf": 96.0,
    "text": "THE"
  },
  {
    "idx": 5,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 2,
    "left": 200,
    "top": 110,
    "width": 201,
    "height": 59,
    "conf": 95.0,
    "text": "QUICK"
  },
  {
    "idx": 6,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 3,
    "left": 425,
    "top": 110,
    "width": 242,
    "height": 53,
    "conf": 96.0,
    "text": "BROWN"
  },
  {
    "idx": 7,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 4,
    "left": 695,
    "top": 110,
    "width": 120,
    "height": 53,
    "conf": 95.0,
    "text": "FOX"
  },
  {
    "idx": 8,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 5,
    "left": 835,
    "top": 110,
    "width": 202,
    "height": 64,
    "conf": 95.0,
    "text": "JUMPS"
  },
  {
    "idx": 9,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 6,
    "left": 1061,
    "top": 110,
    "width": 174,
    "height": 53,
    "conf": 96.0,
    "text": "OVER"
  },
  {
    "idx": 10,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 7,
    "left": 1264,
    "top": 110,
    "width": 71,
    "height": 53,
    "conf": 95.0,
    "text": "13"
  },
  {
    "idx": 11,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 8,
    "left": 1363,
    "top": 111,
    "width": 159,
    "height": 51,
    "conf": 92.0,
    "text": "LAZY"
  },
  {
    "idx": 12,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 9,
    "left": 1547,
    "top": 111,
    "width": 53,
    "height": 51,
    "conf": 86.0,
    "text": "D"
  }
]

## Fixture
tests/fixtures/ocr/very_degraded_text.png
words_counted: 0
avg_confidence_words: 0.0
rows_json:
[
  {
    "idx": 0,
    "level": 1,
    "page_num": 1,
    "block_num": 0,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 300,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 1,
    "level": 2,
    "page_num": 1,
    "block_num": 1,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 300,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 2,
    "level": 3,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 0,
    "word_num": 0,
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 300,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 3,
    "level": 4,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 0,
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 300,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 4,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 1,
    "left": 0,
    "top": 0,
    "width": 1600,
    "height": 300,
    "conf": 95.0,
    "text": ""
  }
]

## Fixture
tests/fixtures/ocr/native_pdf_rendered.png
words_counted: 8
avg_confidence_words: 96.0
rows_json:
[
  {
    "idx": 0,
    "level": 1,
    "page_num": 1,
    "block_num": 0,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 0,
    "top": 0,
    "width": 1190,
    "height": 1684,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 1,
    "level": 2,
    "page_num": 1,
    "block_num": 1,
    "par_num": 0,
    "line_num": 0,
    "word_num": 0,
    "left": 102,
    "top": 82,
    "width": 368,
    "height": 21,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 2,
    "level": 3,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 0,
    "word_num": 0,
    "left": 102,
    "top": 82,
    "width": 368,
    "height": 21,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 3,
    "level": 4,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 0,
    "left": 102,
    "top": 82,
    "width": 368,
    "height": 21,
    "conf": -1.0,
    "text": ""
  },
  {
    "idx": 4,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 1,
    "left": 102,
    "top": 82,
    "width": 57,
    "height": 21,
    "conf": 96.0,
    "text": "Hello,"
  },
  {
    "idx": 5,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 2,
    "left": 168,
    "top": 82,
    "width": 37,
    "height": 19,
    "conf": 96.0,
    "text": "this"
  },
  {
    "idx": 6,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 3,
    "left": 213,
    "top": 82,
    "width": 16,
    "height": 19,
    "conf": 96.0,
    "text": "is"
  },
  {
    "idx": 7,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 4,
    "left": 238,
    "top": 82,
    "width": 61,
    "height": 19,
    "conf": 96.0,
    "text": "native"
  },
  {
    "idx": 8,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 5,
    "left": 307,
    "top": 84,
    "width": 38,
    "height": 17,
    "conf": 96.0,
    "text": "text"
  },
  {
    "idx": 9,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 6,
    "left": 353,
    "top": 82,
    "width": 16,
    "height": 18,
    "conf": 96.0,
    "text": "in"
  },
  {
    "idx": 10,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 7,
    "left": 378,
    "top": 82,
    "width": 32,
    "height": 19,
    "conf": 96.0,
    "text": "the"
  },
  {
    "idx": 11,
    "level": 5,
    "page_num": 1,
    "block_num": 1,
    "par_num": 1,
    "line_num": 1,
    "word_num": 8,
    "left": 420,
    "top": 82,
    "width": 50,
    "height": 18,
    "conf": 96.0,
    "text": "PDF."
  }
]

# Summary
[
  {
    "fixture": "tests/fixtures/ocr/clear_text.png",
    "words_counted": 9,
    "avg_confidence_words": 90.33333333333333
  },
  {
    "fixture": "tests/fixtures/ocr/degraded_text.png",
    "words_counted": 9,
    "avg_confidence_words": 94.0
  },
  {
    "fixture": "tests/fixtures/ocr/very_degraded_text.png",
    "words_counted": 0,
    "avg_confidence_words": 0.0
  },
  {
    "fixture": "tests/fixtures/ocr/native_pdf_rendered.png",
    "words_counted": 8,
    "avg_confidence_words": 96.0
  }
]
```

## 6. Recomendacao tecnica (proposta, nao decisao final)

### 6.1 Threshold concreto proposto

Proposta para "confianca baixa" no pipeline:

- `avg_confidence_words_normalized < 0.85` **ou**
- `words_counted == 0`

Nesses casos, cair para o proximo extractor da cadeia:

`PyMuPDFExtractor -> TesseractOCR -> PaddleOCR -> CloudOCRFallback`

### 6.2 Como preencher `ExtractedPage.confidence`

- **TesseractOCR** (proposto):
  - coletar `conf` por palavra via `image_to_data`
  - filtrar palavras com `text != ""` e `conf >= 0`
  - `confidence = mean(conf_filtrado) / 100.0`
  - se nao houver palavras validas: `confidence = 0.0`

- **PaddleOCR** (proposto, documental):
  - usar `rec_score` por item reconhecido (ou `rec_scores` no pipeline OCR)
  - `confidence = mean(rec_scores_da_pagina)`
  - se nao houver itens reconhecidos: `confidence = 0.0`

## 7. Desvios do escopo original

Nenhum desvio funcional. A OS permaneceu em modo spike/pesquisa, sem implementar OCR de producao.

## 8. Bloqueios

Sem bloqueio ativo nesta retomada.

## 9. Link do PR

N/A nesta execucao.
