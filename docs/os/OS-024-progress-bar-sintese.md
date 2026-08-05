# OS-024 — Progress bar real de síntese

## 1. Objetivo

Achado em uso real: o player só mostra o texto cru do `status` ("Status: synthesizing") enquanto um livro sintetiza, sem noção de quanto falta. Como `pipeline.count_text_chunks()` já existe desde a OS-022 (usado internamente na checagem de consistência do resume), esta OS expõe esse total pela API e troca o texto solto por uma barra de progresso real no player.

## 2. Escopo

**Dentro do escopo:**
- `core/models.py`: `Book` ganha `chunk_total: int | None = None` (default `None` — livro que ainda não começou a sintetizar, ou processado antes desta OS).
- `storage/db.py`: coluna `chunk_total INTEGER` na tabela `books`; `create_book`/`get_book`/`list_books` passam a ler/escrever essa coluna; função nova `set_book_chunk_total(book_id, chunk_total, db_path=None) -> None`.
- `worker/tasks.py::process_job()`: já calcula `chunk_count = pipeline.count_text_chunks(text)` para a checagem de consistência da OS-022 — reaproveitar esse valor, chamando `db.set_book_chunk_total(job.book_id, chunk_count)` logo depois (antes de `db.update_book_status(..., "synthesizing")`).
- `api/routes_books.py::get_book_status`: resposta ganha `chunks_total` (de `book.chunk_total`, pode ser `None`) e `chunks_done` (`len(audio_store.list_chunks(book_id))`).
- `player/index.html`: elemento `<progress>` no lugar do texto solto de status (manter `#player-status` como texto secundário/fallback quando `chunks_total` for `null`, ex: durante `extracting`/`uploaded`, antes do total ser conhecido).
- `player/app.js`: `pollUntilReady`/`check()` atualiza o `<progress value max>` a cada poll.

**Fora do escopo:**
- Progresso da fase de extração/OCR (só cobre a fase de síntese, que é a mais longa e visível hoje).
- Estimativa de tempo restante (ETA) — só contagem de chunks feitos/total.

**Nota de risco, documentar explicitamente no relatório:** igual ao que já aconteceu na OS-018 com `error_message` (`PROJECT_STATE.md` seção 6 — "Dívida técnica: não existe migração de schema no SQLite"), um `books.db` local criado antes desta OS quebra com `sqlite3.OperationalError: table books has no column named chunk_total` no primeiro `POST /books` depois de atualizar o código. Avisar no `RUNBOOK.md`, na mesma seção que já avisa isso pra `error_message`.

## 3. Contratos envolvidos

Nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda. `Book` (`ARQUITETURA.md` seção 5) ganha um campo novo opcional — atualizar a seção 5 com `chunk_total`.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `Book.chunk_total` é `None` até a síntese começar; passa a ter o total real assim que `process_job()` calcula `count_text_chunks()`
- [ ] `GET /books/{id}/status` devolve `chunks_done` e `chunks_total` (`chunks_total` pode ser `null`)
- [ ] `chunks_done` sempre reflete `len(list_chunks(book_id))` em tempo real, inclusive com o livro ainda `synthesizing` (mesma mecânica de persistência incremental da OS-021)
- [ ] Player mostra uma barra de progresso (`<progress>`) durante a síntese, com fallback pro texto de status quando `chunks_total` é `null`
- [ ] `RUNBOOK.md` avisa sobre a coluna nova exigindo apagar `books.db` local (mesmo padrão já usado pela OS-018)

## 5. Testes exigidos (mínimo)

- `test_worker_process_job_sets_book_chunk_total_before_synthesizing`
- `test_get_books_status_returns_chunks_done_and_chunks_total`
- `test_get_books_status_chunks_total_is_none_before_synthesis_starts`

Local sugerido: `tests/unit/test_worker.py`, `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-024-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
