# OS-003 — Extractor base + PyMuPDFExtractor (extração nativa de PDF)

## 1. Objetivo

Implementar o contrato `Extractor` (hoje um stub vazio) e sua primeira implementação concreta, `PyMuPDFExtractor`, que extrai texto de PDFs com camada de texto nativa — o caminho mais barato e rápido do pipeline, conforme `ARQUITETURA.md` seção 4.1.

## 2. Escopo

**Dentro do escopo:**
- `plugins/extractors/base.py` — classe abstrata `Extractor` com os métodos `supports(pdf_path: str) -> bool` e `extract(pdf_path: str, page_range: tuple[int, int] | None = None) -> list[ExtractedPage]`, exatamente como especificado em `ARQUITETURA.md` seção 4.1.
- `plugins/extractors/pymupdf_extractor.py` — `PyMuPDFExtractor(Extractor)` usando a biblioteca `pymupdf` (já em `requirements.txt`):
  - `supports()` retorna `True` só se o PDF tiver camada de texto nativa extraível (não é imagem escaneada).
  - `extract()` retorna uma `ExtractedPage` por página, com `confidence=1.0` e `source="pymupdf"`.

**Fora do escopo:**
- `TesseractOCR`, `PaddleOCR`, `CloudOCRFallback` — OS's futuras (a cadeia de fallback por confiança ainda depende do spike da decisão #5 em `PROJECT_STATE.md`).
- `plugins/registry.py` — wiring do registry é de uma OS futura, quando houver mais de um extractor concreto para registrar.
- `core/pipeline.py` — nenhuma orquestração é chamada aqui, só a implementação isolada do plugin.
- Qualquer chamada de rede ou API paga.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.1 (Extractor). Esta OS implementa o contrato já definido — não propõe nenhum novo. Se durante a implementação a assinatura precisar mudar, isso exige atualizar `ARQUITETURA.md` primeiro (seção 7, regra de convenção), não decidir sozinho.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `Extractor` não pode ser instanciada diretamente (é uma ABC com métodos abstratos)
- [ ] `PyMuPDFExtractor.supports()` retorna `True` para um PDF com texto nativo
- [ ] `PyMuPDFExtractor.supports()` retorna `False` para um PDF sem camada de texto (ex: só imagem)
- [ ] `PyMuPDFExtractor.extract()` retorna uma lista de `ExtractedPage`, uma por página, na ordem do PDF
- [ ] Cada `ExtractedPage` retornada tem `confidence == 1.0` e `source == "pymupdf"`
- [ ] Nenhum teste depende de arquivo externo baixado ou de rede — fixtures de PDF geradas localmente (ex: com o próprio `pymupdf`) ou committadas em `tests/fixtures/`

## 5. Testes exigidos (mínimo)

- `test_extractor_cannot_be_instantiated_directly`
- `test_pymupdf_supports_returns_true_for_text_pdf`
- `test_pymupdf_supports_returns_false_for_image_only_pdf`
- `test_pymupdf_extract_returns_one_page_per_pdf_page`
- `test_pymupdf_extract_sets_confidence_and_source`

Local sugerido: `tests/unit/extractors/test_pymupdf_extractor.py` (diretório já existe).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-003-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
