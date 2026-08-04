# OS-009 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** os/009-pipeline-cleaner-chunker
**Commit(s) relevante(s):** 831edc7 (test: Red), 258fdc5 (feat: Green)

## 1. Resumo do que foi feito

`core/pipeline.py` agora usa `processing/cleaner.py` e `processing/chunker.py`: nova função `extract_clean_text(pdf_path)` combina `extract_with_fallback()` com `clean_text()`, e `synthesize_text()` passou a dividir o texto em chunks via `chunk_text()` e chamar o Speaker uma vez por chunk, com `sequence` incremental, `chapter_id` em todos os `AudioChunk`s e nenhuma chamada ao Speaker para texto vazio.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `831edc7` "Red" existe antes de `258fdc5` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (47 testes no total, todos passando — 42 anteriores + 6 novos/atualizados, líquido de 5 porque um teste da OS-007 foi atualizado no lugar em vez de duplicado)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (nenhum contrato de `Extractor`/`Speaker` mudou; `core/pipeline.py` continua resolvendo plugins só por nome via `registry`/`config`, seção 4.3; `cleaner`/`chunker` são importados diretamente por não serem plugins, conforme seção 1)
- [x] Nenhuma chamada real a API paga dentro dos testes — tudo com dublês fake de `Extractor`/`Speaker`
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2)
- [x] Relatório criado em `docs/report/OS-009-report.md`
- [ ] PR aberto contra o branch principal, com título `[OS-009] liga cleaner/chunker em core/pipeline.py` — a abrir na próxima etapa deste fluxo

### DoD específico da OS (seção 4 de `docs/os/OS-009-pipeline-cleaner-chunker.md`)

- [x] `extract_clean_text(pdf_path)` combina extração + limpeza e devolve uma única string
- [x] `synthesize_text()` divide o texto em chunks antes de sintetizar, chamando o Speaker uma vez por chunk
- [x] Cada `AudioChunk` retornado tem `sequence` incremental começando em `0`, na ordem dos chunks
- [x] Cada `AudioChunk` retornado tem `chapter_id` igual ao parâmetro passado pelo chamador
- [x] Texto vazio/só espaços não chama `speaker.synthesize()` nenhuma vez — retorna lista vazia
- [x] `synthesize_text()` aceita `max_chars` opcional, repassado para `chunk_text()`
- [x] O teste de integração da OS-007 que checava síntese com texto único foi atualizado para o novo comportamento (`test_pipeline_synthesizes_extracted_text_with_configured_speaker` agora usa texto multi-sentença e `max_chars=20`, esperando 3 chunks)
- [x] Testes usam dublês fake (`Extractor`/`Speaker`) — nenhuma chamada real a Tesseract/Kokoro
- [x] Nenhuma chamada de rede ou API paga

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_pipeline_synthesizes_extracted_text_with_configured_speaker` (atualizado) | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_extract_clean_text_combines_extraction_and_cleaning` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_synthesize_text_calls_speaker_once_per_chunk` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_synthesize_text_assigns_incrementing_sequence_per_chunk` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_synthesize_text_sets_chapter_id_on_every_chunk` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_synthesize_text_returns_empty_list_for_empty_text_without_calling_speaker` | `tests/integration/test_pipeline_end_to_end.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Testes falhando antes da implementação (commit Red, `831edc7`):

```
tests/integration/test_pipeline_end_to_end.py::test_pipeline_synthesizes_extracted_text_with_configured_speaker
  TypeError: synthesize_text() got an unexpected keyword argument 'max_chars'
tests/integration/test_pipeline_end_to_end.py::test_extract_clean_text_combines_extraction_and_cleaning
  AttributeError: module 'core.pipeline' has no attribute 'extract_clean_text'
tests/integration/test_pipeline_end_to_end.py::test_synthesize_text_calls_speaker_once_per_chunk
  TypeError: synthesize_text() got an unexpected keyword argument 'max_chars'
tests/integration/test_pipeline_end_to_end.py::test_synthesize_text_assigns_incrementing_sequence_per_chunk
  TypeError: synthesize_text() got an unexpected keyword argument 'max_chars'
tests/integration/test_pipeline_end_to_end.py::test_synthesize_text_sets_chapter_id_on_every_chunk
  TypeError: synthesize_text() got an unexpected keyword argument 'max_chars'
tests/integration/test_pipeline_end_to_end.py::test_synthesize_text_returns_empty_list_for_empty_text_without_calling_speaker
  AssertionError: assert [AudioChunk(...)] == []
6 failed, 3 passed in 4.21s
```

Suíte completa após a implementação (commit Green, `258fdc5`):

```
$ python -m pytest -q
...............................................                          [100%]
47 passed in 5.88s
```

`black --check` e `ruff check` nos arquivos tocados por esta OS: sem alterações pendentes, todos os checks passaram.

## 5. Desvios do escopo original

Nenhum. Escopo declarado (nova `extract_clean_text()`, `synthesize_text()` com chunking/`max_chars`, atualização do teste da OS-007) implementado sem tocar em `Extractor`/`Speaker`, detecção de capítulos, `storage/`, `worker/` ou `api/`.

Uma decisão de implementação dentro do espaço deixado em aberto: além de atualizar o teste da OS-007 (`test_pipeline_synthesizes_extracted_text_with_configured_speaker`) para o novo comportamento multi-chunk, também dei ao `FakeSpeaker` de teste um contador de chamadas (`call_count`) e um `file_path` único por chamada — necessário para os novos testes que verificam "uma chamada por chunk" e "nenhuma chamada para texto vazio", sem mudar o comportamento dos testes que já usavam esse dublê.

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

A preencher após abertura do PR na próxima etapa.
