# OS-006 — TesseractOCR (fallback de OCR local)

## 1. Objetivo

Implementar `TesseractOCR`, o segundo elo da cadeia de extração (`PyMuPDFExtractor` → `TesseractOCR` → `PaddleOCR` → `CloudOCRFallback`), usando a heurística de confidence já aprovada em `ARQUITETURA.md` seção 4.1 (decisão #9 em `PROJECT_STATE.md`).

## 2. Escopo

**Dentro do escopo:**
- `plugins/extractors/tesseract_ocr.py` — `TesseractOCR(Extractor)`:
  - `supports(pdf_path)`: `True` se o arquivo abre como PDF válido com pelo menos uma página, `False` se o caminho não existir ou o arquivo estiver corrompido. Diferente do `PyMuPDFExtractor`, **não** precisa checar camada de texto nativa — Tesseract é o fallback justamente para quando isso falta; essa decisão é do pipeline, não deste plugin.
  - `extract(pdf_path, page_range=None)`: para cada página no intervalo, renderizar a página como imagem (via `pymupdf`/`fitz`, já usado no projeto) e rodar `pytesseract.image_to_data()` sobre a imagem renderizada. Retornar uma `ExtractedPage` por página, com `source="tesseract"`.
  - `ExtractedPage.confidence` calculado **exatamente** pela fórmula aprovada: coletar `conf` por palavra, filtrar entradas com `text != ""` e `conf >= 0`, `confidence = mean(conf_filtrado) / 100.0`. Sem palavras válidas → `confidence = 0.0`.
- Fixtures novas de **PDF** (não PNG solto) com imagem de texto embutida, para testar de ponta a ponta pelo caminho real do contrato (`extract(pdf_path)`). As fixtures PNG já existentes em `tests/fixtures/ocr/` (da OS-005) podem servir de base visual, mas precisam ser encapsuladas em PDF (ex: inserir a imagem numa página nova via `fitz`), já que o `Extractor.extract()` recebe `pdf_path`, não caminho de imagem.

**Fora do escopo:**
- `PaddleOCR`, `CloudOCRFallback` — OS's futuras.
- `plugins/registry.py` — wiring do registry é de OS futura.
- `core/pipeline.py` — a lógica de **quando** chamar `TesseractOCR` (depois de `PyMuPDFExtractor` falhar/ter confiança baixa) é do pipeline, que ainda não existe. Esta OS só entrega o plugin isolado, funcional e testável sozinho.
- Qualquer chamada de rede ou API paga.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.1 (Extractor), incluindo a heurística de confidence aprovada na decisão #9. Esta OS implementa o contrato e a fórmula já definidos — não propõe nada novo. Se a fórmula precisar mudar durante a implementação, isso exige voltar para o dono do projeto, não decidir sozinho (mesma regra já aplicada na OS-005).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `TesseractOCR.supports()` retorna `True` para um PDF válido com pelo menos uma página
- [ ] `TesseractOCR.supports()` retorna `False` para um caminho inexistente ou arquivo corrompido
- [ ] `TesseractOCR.extract()` retorna uma `ExtractedPage` por página, na ordem do PDF
- [ ] Cada `ExtractedPage` retornada tem `source == "tesseract"`
- [ ] `ExtractedPage.confidence` segue exatamente a fórmula aprovada (não uma aproximação)
- [ ] Para um PDF com imagem de texto legível, `ExtractedPage.text` não é vazio e `confidence >= 0.85` (consistente com o observado no spike da OS-005 para texto legível)
- [ ] Para um PDF com imagem sem texto reconhecível (ruído pesado, sem palavras válidas), `confidence == 0.0`
- [ ] Nenhuma chamada de rede ou API paga
- [ ] Nenhum teste depende de arquivo externo baixado — fixtures de PDF geradas localmente e commitadas em `tests/fixtures/`

## 5. Testes exigidos (mínimo)

- `test_tesseract_supports_returns_true_for_valid_pdf`
- `test_tesseract_supports_returns_false_for_nonexistent_path`
- `test_tesseract_extract_returns_one_page_per_pdf_page`
- `test_tesseract_extract_sets_source_to_tesseract`
- `test_tesseract_extract_confidence_matches_approved_formula_for_legible_text`
- `test_tesseract_extract_confidence_is_zero_for_unreadable_image`

Local sugerido: `tests/unit/extractors/test_tesseract_ocr.py` (diretório já existe).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-006-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
