# OS-007 — core/pipeline.py (orquestração síncrona mínima)

## 1. Objetivo

Ligar os plugins que já existem (`PyMuPDFExtractor`, `TesseractOCR`, `KokoroSpeaker`) numa orquestração síncrona mínima: dado um PDF, extrair texto usando a cadeia de fallback já aprovada (decisão #9) e sintetizar o texto extraído com o Speaker configurado. Esta OS também finalmente preenche `plugins/registry.py` e `core/config.py`, que até agora ficaram vazios porque não havia mais de um plugin por categoria para justificar o registry — agora há.

## 2. Escopo

**Dentro do escopo:**
- `plugins/registry.py` — preencher `EXTRACTORS` e `SPEAKERS` exatamente como o contrato já definido em `ARQUITETURA.md` seção 4.3: `EXTRACTORS = {"pymupdf": PyMuPDFExtractor, "tesseract": TesseractOCR}`, `SPEAKERS = {"kokoro": KokoroSpeaker}`. (`paddleocr`, `cloud_ocr`, `piper`, `cloud_tts` ficam de fora — as classes ainda não existem.)
- `core/config.py` — carregar `config.yaml` (já existe, com `extractor: pymupdf` e `speaker: kokoro`) e expor os nomes configurados para quem for resolver plugins via `registry.py`.
- `core/pipeline.py`:
  - Uma função de **extração com fallback**: recebe um `pdf_path`, tenta o extractor primário resolvido via `registry`/`config` (hoje `pymupdf`); se `supports()` retornar `False`, cai para `tesseract`. Usa a heurística já aprovada em `ARQUITETURA.md` seção 4.1 — mas note que `PyMuPDFExtractor` sempre retorna `confidence=1.0` quando extrai, então na prática o único gatilho de fallback vindo dele é `supports() == False`; o threshold de confidence baixa (`< 0.85` ou `words_counted == 0`) é o que decide se o resultado do **Tesseract** deve ser aceito como está — como não existe mais nenhum extractor depois do Tesseract nesta OS (PaddleOCR/CloudOCR não existem ainda), o resultado do Tesseract é sempre usado como "melhor esforço" mesmo com confiança baixa, mas a confiança deve continuar visível no `ExtractedPage` retornado (não silenciar/descartar essa informação).
  - Uma função de **síntese**: recebe o texto extraído (concatenação simples das páginas — sem limpeza, sem chunking, isso é escopo de OS futura) e um `chapter_id` fornecido por quem chama (esta OS não faz detecção de capítulo), chama o Speaker resolvido via `registry`/`config` (hoje `kokoro`) e retorna o(s) `AudioChunk` gerado(s).
  - Nenhuma classe concreta de plugin é importada fora de `plugins/registry.py` — inclusive `core/pipeline.py` só conhece os plugins pelo nome, via registry, conforme a regra já definida em `ARQUITETURA.md` seção 4.3 ("nenhum outro módulo deve importar uma classe concreta de plugin diretamente").

**Fora do escopo:**
- `processing/cleaner.py` e `processing/chunker.py` — o texto extraído vai direto para o Speaker sem limpeza nem divisão em pedaços menores. Isso é uma limitação conhecida e aceitável nesta OS (textos longos podem falhar ou demorar) — próxima OS do backlog resolve isso.
- Detecção de capítulos (`processing/chapter_detector.py`), persistência (`storage/`), fila de jobs (`worker/`) e API (`api/`) — nenhuma dessas existe ainda; o pipeline desta OS roda em memória, de ponta a ponta, sem salvar nada.
- `PaddleOCR`, `CloudOCRFallback`, `PiperSpeaker`, `CloudSpeaker` — não existem, não entram no registry ainda.
- Qualquer chamada de rede ou API paga.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.1 (Extractor, incluindo a heurística aprovada), 4.2 (Speaker) e 4.3 (Registro de plugins — contrato já definido, esta OS só o preenche pela primeira vez com conteúdo real). Nenhum contrato novo é proposto.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `plugins/registry.py` expõe `EXTRACTORS` com `"pymupdf"` e `"tesseract"`, e `SPEAKERS` com `"kokoro"`
- [ ] `core/config.py` lê `config.yaml` e retorna os nomes de extractor/speaker configurados
- [ ] A função de extração do pipeline usa `PyMuPDFExtractor` quando `supports()` é `True`
- [ ] A função de extração cai para `TesseractOCR` quando `PyMuPDFExtractor.supports()` é `False`
- [ ] O `ExtractedPage.confidence` do resultado final continua acessível para quem chamar o pipeline, mesmo quando baixo (não é descartado silenciosamente)
- [ ] A função de síntese chama o Speaker configurado e retorna `AudioChunk`(s) válidos
- [ ] Nenhum módulo (incluindo `core/pipeline.py`) importa uma classe concreta de plugin fora de `plugins/registry.py`
- [ ] Testes usam extractors/speaker fake (dublês que implementam `Extractor`/`Speaker`) para isolar a lógica de orquestração — não dependem de rodar Tesseract/Kokoro de verdade (isso já foi coberto nas OS's dos plugins individuais)
- [ ] Nenhuma chamada de rede ou API paga

## 5. Testes exigidos (mínimo)

- `test_registry_extractors_contains_pymupdf_and_tesseract`
- `test_registry_speakers_contains_kokoro`
- `test_config_loads_extractor_and_speaker_from_yaml`
- `test_pipeline_uses_primary_extractor_when_supports_true`
- `test_pipeline_falls_back_to_tesseract_when_primary_supports_false`
- `test_pipeline_exposes_confidence_even_when_low`
- `test_pipeline_synthesizes_extracted_text_with_configured_speaker`

Local sugerido: `tests/integration/test_pipeline_end_to_end.py` para os testes de orquestração (conforme estrutura já prevista em `TDD.md` seção 2, usando plugins fake — não é "integração" com engines reais) e `tests/unit/` para `registry.py`/`config.py` isoladamente.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-007-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
