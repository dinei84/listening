# OS-021 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/021-entrega-incremental-audio
**Commit(s) relevante(s):** f02845c (test: Red), f9dfdc4 (feat: Green)

## 1. Resumo do que foi feito

`core/pipeline.py::synthesize_text()` ganhou um parâmetro opcional `on_chunk: Callable[[AudioChunk], None] | None = None`, chamado imediatamente após cada chunk ser sintetizado. `worker/tasks.py::process_job()` passa um `on_chunk` que persiste cada `AudioChunk` via `persist_chunks(book_id, [chunk])` assim que ele fica pronto, e atualiza `Book.status` para `"synthesizing"` antes de começar a síntese. Comportamento existente inalterado quando `on_chunk` não é passado.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `f02845c` "Red" antes de `f9dfdc4` "Green")
- [x] Todos os testes da OS passam localmente — 99 pass, 0 fail
- [x] Nenhum teste existente quebrou (94 anteriores + 5 novos = 99)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `synthesize_text()` mantém assinatura original com parâmetro novo opcional, contratos de `Extractor`/`Speaker`/`JobQueue` inalterados
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — FakeSpeaker/FakeExtractor mockados em todos os testes
- [x] Type hints e docstring de uma linha em toda função pública — `Callable[[AudioChunk], None]` no parâmetro `on_chunk`, docstring atualizada em `synthesize_text`
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4, 5 e 7)
- [x] Relatório criado em `docs/report/OS-021-report.md`
- [x] PR aberto contra o branch principal, título `[OS-021] entrega incremental de áudio`

### DoD específico da OS (`docs/os/OS-021-entrega-incremental-audio.md` seção 4)

- [x] `synthesize_text()` aceita `on_chunk` opcional, chamado imediatamente após cada `AudioChunk` ser sintetizado
- [x] Sem `on_chunk`, `synthesize_text()` se comporta exatamente como antes (todos os testes da OS-009 continuam passando sem modificação)
- [x] `worker/tasks.py` persiste cada `AudioChunk` via `on_chunk`, não mais numa chamada só no final
- [x] `Book.status` vira `"synthesizing"` antes do primeiro chunk, `"ready"` só depois que todos terminarem com sucesso
- [x] Teste confirma que chunks já persistidos aparecem em `GET /books/{id}/audio` **antes** do job terminar (livro ainda `synthesizing`)
- [x] Teste confirma a persistência incremental de verdade — `RecordingSpeaker` registra quantos chunks já estão no banco a cada síntese (`[0, 1, 2]`), provando que o chunk 0 foi persistido antes do chunk 1 ser sintetizado
- [x] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_synthesize_text_calls_on_chunk_for_each_chunk` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_synthesize_text_returns_full_list_when_on_chunk_is_none` (regressão) | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_worker_process_job_persists_chunks_incrementally` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_sets_book_status_to_synthesizing_before_ready` | `tests/unit/test_worker.py` | Sim |
| `test_get_books_audio_returns_partial_chunks_while_synthesizing` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `f02845c` (4 falhas: `TypeError: on_chunk keyword`, `[0,0,0] != [0,1,2]`, status `uploaded != synthesizing`, API retorna 0 chunks parciais mid-synthesis) antes de `f9dfdc4`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação):
```
4 failed, 27 passed, 1 warning in 5.36s
```

Falhas: `test_synthesize_text_calls_on_chunk_for_each_chunk` (`TypeError: unexpected keyword argument 'on_chunk'`), `test_worker_process_job_persists_chunks_incrementally` (`[0,0,0]==[0,1,2]`), `test_worker_process_job_sets_book_status_to_synthesizing_before_ready` (status `uploaded != synthesizing`), `test_get_books_audio_returns_partial_chunks_while_synthesizing` (status `uploaded != synthesizing`).

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
99 passed, 1 warning in 7.42s
```

`black --check`: reformatou `worker/tasks.py` (1 arquivo). `ruff check` em `core/pipeline.py`, `worker/tasks.py` e `tests/`: sem achados.

## 5. Decisão de implementação documentada

A OS permite duas abordagens para persistir cada chunk: reutilizar `persist_chunks(book_id, [chunk])` (com lista de um elemento) ou criar uma função nova `persist_chunk(book_id, chunk)` singular. **Escolhido:** reutilizar `persist_chunks(book_id, [chunk])` — mudança mínima, nenhum novo contrato de armazenamento, reaproveita o caminho já testado.

## 6. Desvios do escopo original

Nenhum.

## 7. Dúvidas / bloqueios

Nenhuma.

## 8. Link do PR

https://github.com/dinei84/listening/pull/18
