# OS-017 — EasyOCRExtractor (terceiro elo da cadeia de OCR)

## 1. Objetivo

Implementar `EasyOCRExtractor`, o terceiro elo da cadeia de extração (`PyMuPDFExtractor` → `TesseractOCR` → `EasyOCRExtractor` → `CloudOCRFallback`) — decisão #13 em `PROJECT_STATE.md`, que substitui o `PaddleOCR` do roadmap original por reaproveitar o `torch` já instalado via Kokoro em vez de trazer o `paddlepaddle` (~195MB, framework de deep learning novo) para o projeto.

## 2. Escopo

**Dentro do escopo:**
- `plugins/extractors/easyocr_extractor.py` — `EasyOCRExtractor(Extractor)`:
  - `supports(pdf_path)`: mesma lógica de `TesseractOCR` — `True` se o arquivo abre como PDF válido com pelo menos uma página, `False` para caminho inexistente ou arquivo corrompido.
  - `extract(pdf_path, page_range=None)`: renderizar cada página como imagem (via `fitz`, mesmo padrão de `TesseractOCR`), rodar `reader.readtext()` do EasyOCR sobre a imagem renderizada. Retornar uma `ExtractedPage` por página, `source="easyocr"`.
  - `ExtractedPage.confidence`: coletar o `confidence` (0.0–1.0) de cada região de texto devolvida por `readtext()`, `confidence = mean(confidences_da_página)`. Sem regiões reconhecidas → `confidence = 0.0`. (Fórmula já registrada em `ARQUITETURA.md` seção 4.1 — decisão #13.)
- `plugins/registry.py` ganha `EXTRACTORS["easyocr"] = EasyOCRExtractor`.
- `easyocr` adicionado a `requirements.txt`, com a versão real conferida no PyPI (mesma prática desde a OS-001).
- **Validação empírica da fórmula de confidence, documentada no relatório** — mesmo espírito da OS-006 (`TesseractOCR`): rodar o EasyOCR de verdade sobre pelo menos duas fixtures de qualidade diferente (uma legível, uma ilegível/ruído pesado) e colar os números reais observados no relatório. Se os valores observados não baterem razoavelmente com o threshold `0.85` já aprovado (decisão #9, reaproveitado por analogia na decisão #13), **registrar isso explicitamente como achado, não forçar a fórmula a caber** — a decisão #13 já deixa claro que o threshold reaproveitado não é uma validação empírica própria.
- **Atenção ao mesmo problema já encontrado na OS-004 (`KokoroSpeaker`):** construir um `easyocr.Reader(...)` de verdade baixa modelos de um servidor externo na primeira vez que roda, se não estiverem em cache local — isso é uma chamada de rede real escondida atrás de algo que parece "engine local". Os testes **não podem depender disso**. Mockar a construção do `Reader` inteira (não só a chamada de leitura), do mesmo jeito que `KokoroSpeaker._get_pipeline` foi mockado na correção da OS-004 — não bastar mockar só o método de leitura e deixar o `Reader()` real ser instanciado.

**Fora de escopo:**
- `CloudOCRFallback` — OS futura.
- Ligar `EasyOCRExtractor` na cadeia de fallback de `core/pipeline.py` (hoje `extract_with_fallback()` só conhece dois elos, pymupdf→tesseract) — OS seguinte, muda o comportamento público do pipeline.
- `plugins/registry.py` ganhar wiring em `core/pipeline.py` — só a entrada no dict `EXTRACTORS`.
- Qualquer chamada de rede real durante os testes (nem para baixar modelo do EasyOCR).

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.1 (Extractor, incluindo a fórmula de confidence do `EasyOCRExtractor` já registrada na decisão #13) e seção 4.4 (registry). Esta OS implementa o contrato já definido — não propõe nada novo.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `EasyOCRExtractor.supports()` retorna `True` para um PDF válido com pelo menos uma página, `False` para caminho inexistente ou arquivo corrompido
- [ ] `EasyOCRExtractor.extract()` retorna uma `ExtractedPage` por página, na ordem do PDF
- [ ] Cada `ExtractedPage` retornada tem `source == "easyocr"`
- [ ] `ExtractedPage.confidence` segue exatamente a fórmula registrada em `ARQUITETURA.md` seção 4.1
- [ ] Para um PDF com imagem de texto legível, `ExtractedPage.text` não é vazio
- [ ] Para um PDF com imagem sem texto reconhecível, `confidence == 0.0`
- [ ] Nenhum teste constrói um `easyocr.Reader` real — mockado por completo (não só o método de leitura), evitando o download de modelo/chamada de rede na primeira execução
- [ ] Validação empírica real (fora dos testes automatizados, documentada no relatório) rodando o EasyOCR de verdade sobre pelo menos 2 fixtures, com os números colados — não estimados
- [ ] `easyocr` em `requirements.txt` com versão real conferida no PyPI
- [ ] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 5. Testes exigidos (mínimo)

- `test_easyocr_supports_returns_true_for_valid_pdf`
- `test_easyocr_supports_returns_false_for_nonexistent_path`
- `test_easyocr_supports_returns_false_for_corrupted_file`
- `test_easyocr_extract_returns_one_page_per_pdf_page`
- `test_easyocr_extract_sets_source_to_easyocr`
- `test_easyocr_extract_confidence_matches_formula_for_legible_text`
- `test_easyocr_extract_confidence_is_zero_for_unreadable_image`
- `test_registry_extractors_contains_easyocr`

Local sugerido: `tests/unit/extractors/test_easyocr_extractor.py`. Pode reaproveitar as fixtures de PDF já existentes da OS-006 (`tests/fixtures/ocr/clear_text_pdf.pdf`, `tests/fixtures/ocr/unreadable_text_pdf.pdf`) em vez de criar fixtures novas, já que servem exatamente ao mesmo propósito.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-017-report.md` (template em `docs/report/REPORT_TEMPLATE.md`). Incluir a seção de validação empírica com os números reais observados, mesmo padrão da OS-006.*
