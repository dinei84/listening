# OS-006 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** `main`
**Commit(s) relevante(s):** `e7dfa33` (test: add tests for TesseractOCR — Red), `a378d1e` (feat: implement TesseractOCR — Green)

## 1. Resumo do que foi feito

Implementação de `TesseractOCR` (`plugins/extractors/tesseract_ocr.py`), o segundo elo da cadeia de extração. Segue TDD: testes primeiro (Red), implementação depois (Green). `supports()` valida abertura de PDF com ≥1 página (retornando `False` para caminho inexistente/corrompido), e `extract()` renderiza cada página via `fitz` e roda `pytesseract.image_to_data()`, aplicando a fórmula de confidence aprovada na decisão #9.

## 2. Checklist de DoD

### Checklist padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit `e7dfa33` (Red) existe antes do commit `a378d1e` (Green)
- [x] Todos os testes da OS passam localmente — 7/7 passam
- [x] Nenhum teste existente quebrou — 26/26 passam (suite completa)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` seção 4.1 — `supports()`/`extract()` conforme interface e fórmula aprovada
- [x] Nenhuma chamada real a API paga dentro dos testes — todos usam fixtures locais
- [x] Type hints e docstring de uma linha em toda função pública — aplicado em `supports`, `extract`, `_ocr_page`
- [x] `PROJECT_STATE.md` atualizado — seções 2, 4 e 5 atualizadas
- [x] Relatório da OS preenchido em `docs/report/OS-006-report.md`
- [x] PR aberto contra o branch principal — N/A (OS-006 está no branch `main`)

### Checklist específica da OS-006 (seção 4 de `docs/os/OS-006-tesseract-ocr.md`)

- [x] `TesseractOCR.supports()` retorna `True` para um PDF válido com pelo menos uma página
- [x] `TesseractOCR.supports()` retorna `False` para um caminho inexistente ou arquivo corrompido
- [x] `TesseractOCR.extract()` retorna uma `ExtractedPage` por página, na ordem do PDF
- [x] Cada `ExtractedPage` retornada tem `source == "tesseract"`
- [x] `ExtractedPage.confidence` segue exatamente a fórmula aprovada (não uma aproximação)
- [x] Para um PDF com imagem de texto legível, `ExtractedPage.text` não é vazio e `confidence >= 0.85`
- [x] Para um PDF com imagem sem texto reconhecível, `confidence == 0.0`
- [x] Nenhuma chamada de rede ou API paga
- [x] Nenhum teste depende de arquivo externo baixado — fixtures de PDF geradas localmente e commitadas em `tests/fixtures/`

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_tesseract_supports_returns_true_for_valid_pdf` | `tests/unit/extractors/test_tesseract_ocr.py` | Sim |
| `test_tesseract_supports_returns_false_for_nonexistent_path` | `tests/unit/extractors/test_tesseract_ocr.py` | Sim |
| `test_tesseract_supports_returns_false_for_corrupted_file` | `tests/unit/extractors/test_tesseract_ocr.py` | Sim |
| `test_tesseract_extract_returns_one_page_per_pdf_page` | `tests/unit/extractors/test_tesseract_ocr.py` | Sim |
| `test_tesseract_extract_sets_source_to_tesseract` | `tests/unit/extractors/test_tesseract_ocr.py` | Sim |
| `test_tesseract_extract_confidence_matches_approved_formula_for_legible_text` | `tests/unit/extractors/test_tesseract_ocr.py` | Sim |
| `test_tesseract_extract_confidence_is_zero_for_unreadable_image` | `tests/unit/extractors/test_tesseract_ocr.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green"? [x] Sim — commit `e7dfa33` (Red) → commit `a378d1e` (Green)

## 4. Saída de comandos relevante

```
$ source venv/bin/activate && python3 -m pytest tests/unit/extractors/test_tesseract_ocr.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/dinei/DEV/listening/venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/dinei/DEV/listening
configfile: pytest.ini
plugins: mock-3.15.1, anyio-4.14.2
collecting ... collected 7 items

tests/unit/extractors/test_tesseract_ocr.py::test_tesseract_supports_returns_true_for_valid_pdf PASSED [ 14%]
tests/unit/extractors/test_tesseract_ocr.py::test_tesseract_supports_returns_false_for_nonexistent_path PASSED [ 28%]
tests/unit/extractors/test_tesseract_ocr.py::test_tesseract_supports_returns_false_for_corrupted_file PASSED [ 42%]
tests/unit/extractors/test_tesseract_ocr.py::test_tesseract_extract_returns_one_page_per_pdf_page PASSED [ 57%]
tests/unit/extractors/test_tesseract_ocr.py::test_tesseract_extract_sets_source_to_tesseract PASSED [ 71%]
tests/unit/extractors/test_tesseract_ocr.py::test_tesseract_extract_confidence_matches_approved_formula_for_legible_text PASSED [ 85%]
tests/unit/extractors/test_tesseract_ocr.py::test_tesseract_extract_confidence_is_zero_for_unreadable_image PASSED [100%]

============================== 7 passed in 1.53s ==============================
```

Validação empírica dos números (antes de escrever os testes):

```
clear_text_pdf.pdf: words=9 conf=0.932   (>= 0.85, esperado)
unreadable_text_pdf.pdf: words=0 conf=0.000  (esperado)
```

## 5. Desvios do escopo original

Nenhum. Alterações dentro do escopo da OS-006:
- `plugins/extractors/tesseract_ocr.py` — implementação do plugin
- `tests/unit/extractors/test_tesseract_ocr.py` — 7 testes
- `tests/fixtures/ocr/clear_text_pdf.pdf` — PDF com texto legível
- `tests/fixtures/ocr/unreadable_text_pdf.pdf` — PDF com imagem ilegível
- `tests/fixtures/ocr/corrupted.pdf` — PDF corrompido (para `supports()`)

Nota: adicionado 1 teste além do mínimo exigido (`test_tesseract_supports_returns_false_for_corrupted_file`), pois o critério de aceite pede `False` também para arquivo corrompido, não só caminho inexistente.

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

N/A — OS-006 está no branch `main`.
