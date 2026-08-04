# OS-009 — Ligar cleaner/chunker em core/pipeline.py

## 1. Objetivo

Substituir a síntese de "texto inteiro numa chamada só" (limitação conhecida deixada pela OS-007) por um fluxo que limpa o texto extraído (`processing/cleaner.py`) e o divide em chunks por sentença (`processing/chunker.py`) antes de sintetizar, gerando um `AudioChunk` por chunk com `sequence` correto.

## 2. Escopo

**Dentro do escopo:**
- Nova função em `core/pipeline.py`, ex: `extract_clean_text(pdf_path: str) -> str`, que combina `extract_with_fallback()` (já existe) com `processing.cleaner.clean_text()`: extrai as páginas, pega o texto de cada `ExtractedPage`, limpa (remove header/footer repetido, corrige hifenização) e devolve uma única string.
- Alterar `synthesize_text(text: str, chapter_id: str, max_chars: int | None = None) -> list[AudioChunk]` para:
  - Dividir `text` em chunks via `processing.chunker.chunk_text()` (repassando `max_chars` se fornecido, senão usa o padrão do chunker) antes de sintetizar.
  - Chamar o Speaker configurado **uma vez por chunk**, não mais uma única vez com o texto inteiro.
  - Devolver um `AudioChunk` por chunk, com `sequence` incremental começando em `0` (na ordem dos chunks) e `chapter_id` igual ao parâmetro recebido em todos eles.
  - Texto vazio (ou só espaços) **não deve gerar nenhuma chamada ao Speaker** — devolver lista vazia direto. Essa regra já está em `TDD.md` seção 4 ("Texto vazio não deve gerar chamada ao engine — deve ser validado antes"), mas nunca foi testada porque `synthesize_text` da OS-007 não tratava esse caso explicitamente.
- Atualizar o teste de integração já existente da OS-007 (`test_pipeline_synthesizes_extracted_text_with_configured_speaker`, em `tests/integration/test_pipeline_end_to_end.py`) para o novo comportamento — ele assumia um único `AudioChunk` de saída, isso muda.

**Fora do escopo:**
- Detecção de capítulos — `chapter_id` continua sendo passado por quem chama `synthesize_text`, não descoberto automaticamente.
- Persistência (`storage/`), fila (`worker/`), API (`api/`) — o pipeline continua rodando em memória, síncrono, sem salvar nada.
- Mudar `extract_with_fallback()` — seu contrato (retorna `list[ExtractedPage]`) fica como está; só ganha um novo consumidor (`extract_clean_text`).

## 3. Contratos envolvidos

Nenhum contrato de plugin (`Extractor`/`Speaker`) muda. `core/pipeline.py` continua resolvendo plugins só por nome via `registry`/`config` (regra da OS-007, `ARQUITETURA.md` seção 4.3) — nenhuma classe concreta de plugin é importada fora de `plugins/registry.py`.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `extract_clean_text(pdf_path)` combina extração + limpeza e devolve uma única string
- [ ] `synthesize_text()` divide o texto em chunks antes de sintetizar, chamando o Speaker uma vez por chunk
- [ ] Cada `AudioChunk` retornado tem `sequence` incremental começando em `0`, na ordem dos chunks
- [ ] Cada `AudioChunk` retornado tem `chapter_id` igual ao parâmetro passado pelo chamador
- [ ] Texto vazio/só espaços não chama `speaker.synthesize()` nenhuma vez — retorna lista vazia
- [ ] `synthesize_text()` aceita `max_chars` opcional, repassado para `chunk_text()`
- [ ] O teste de integração da OS-007 que checava síntese com texto único foi atualizado para o novo comportamento, não deixado quebrado
- [ ] Testes usam dublês fake (`Extractor`/`Speaker`) — nenhuma chamada real a Tesseract/Kokoro
- [ ] Nenhuma chamada de rede ou API paga

## 5. Testes exigidos (mínimo)

- `test_extract_clean_text_combines_extraction_and_cleaning`
- `test_synthesize_text_calls_speaker_once_per_chunk`
- `test_synthesize_text_assigns_incrementing_sequence_per_chunk`
- `test_synthesize_text_sets_chapter_id_on_every_chunk`
- `test_synthesize_text_returns_empty_list_for_empty_text_without_calling_speaker`

Local sugerido: `tests/integration/test_pipeline_end_to_end.py` (mesmo arquivo da OS-007).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-009-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
