# OS-012 — Liga JobQueue em worker/tasks.py e na API

## 1. Objetivo

Fechar o ciclo da decisão #11: `POST /books` passa a **enfileirar** um `Job` e responder na hora, em vez de rodar o pipeline dentro da requisição. `worker/tasks.py` ganha um loop de polling que consome a fila (`JobQueue`, resolvida via `registry`/`config` — hoje `SQLiteJobQueue`) e processa os livros de verdade.

## 2. Escopo

**Dentro do escopo:**
- Um helper compartilhado para o caminho do PDF enviado (ex: `storage/uploads.py`, com `UPLOAD_DIR` e uma função `pdf_path_for(book_id) -> Path`), usado tanto por `api/routes_books.py` quanto por `worker/tasks.py`. Isso evita repetir o mesmo problema já registrado no relatório da OS-011 (`plugins/queues/sqlite_queue.py` duplicando `DEFAULT_DB_PATH` de `storage/db.py`) — aqui não tem desculpa de desacoplamento, os dois módulos **precisam** concordar no mesmo caminho pro mesmo `book_id`.
- `worker/tasks.py`:
  - `process_job(job: Job) -> None`: busca o `Book` do job, roda o pipeline (`extract_clean_text` → um `Chapter` sintético → `synthesize_text`, mesma lógica que hoje está em `api/routes_books.py`), atualiza `Book.status` para `ready` ou `error`, e chama `queue.mark_done(job.id)` ou `queue.mark_failed(job.id, error_message)` de acordo.
  - `run_worker(poll_interval: float = 1.0, max_iterations: int | None = None) -> None`: loop que chama `queue.claim_next()`; se vier um `Job`, processa; se não, dorme `poll_interval` segundos. `max_iterations` existe **só para testabilidade** (parar o loop depois de N voltas em vez de rodar para sempre) — em produção roda com `max_iterations=None`.
  - Um bloco `if __name__ == "__main__": run_worker()` para o dono do projeto rodar `python -m worker.tasks` manualmente numa segunda janela de terminal.
- `api/routes_books.py`:
  - `POST /books` passa a: salvar o PDF, criar o `Book` (status `uploaded`), criar e enfileirar um `Job` (`stage="process"` — ver nota abaixo sobre essa simplificação), e **devolver a resposta imediatamente**, sem chamar `core.pipeline`. O `status` devolvido nunca é `ready`/`error` nesta resposta — é sempre o status inicial do `Book` (`uploaded`).
- Atualizar os testes da OS-010 que assumiam resposta síncrona (`test_post_books_creates_book_and_returns_ready_status`, `test_post_books_returns_error_status_when_pipeline_fails`) para o novo contrato assíncrono — não deixar quebrados.

**Nota sobre `Job.stage`:** o modelo `Job` (`core/models.py`, OS-002) tem `stage: Literal["extract", "process", "synthesize"]`, pensado para jobs por etapa. Esta OS usa **um `Job` só por livro**, cobrindo o pipeline inteiro (extração + síntese), com `stage="process"` como valor pragmático — não é uma granularidade fina por etapa, é uma simplificação deliberada para não construir encadeamento de jobs (job de extração que dispara job de síntese) sem necessidade comprovada. Documentar isso no relatório, não mudar o `Literal` de `Job.stage` nesta OS.

**Fora de escopo:**
- Gerenciamento do processo do worker (systemd, supervisor, Docker) — o dono do projeto roda `python -m worker.tasks` manualmente.
- Retry automático de `Job` que falhou.
- Jobs por etapa encadeados (extract → process → synthesize como jobs separados).
- Qualquer mudança em `plugins/queues/`, `storage/db.py` ou nos contratos de `Extractor`/`Speaker`.
- Qualquer chamada de rede ou API paga.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.3 (`JobQueue`, já implementado na OS-011 — esta OS só consome, não altera o contrato) e seção 4.4 (`registry`). `worker/tasks.py` resolve a fila só por nome via `registry`/`config`, nunca importa `SQLiteJobQueue` diretamente — mesma regra já aplicada a `core/pipeline.py` desde a OS-007.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `storage/uploads.py` (ou nome equivalente) centraliza o caminho do PDF enviado; `api/routes_books.py` e `worker/tasks.py` usam a mesma função, não literais duplicados
- [ ] `POST /books` enfileira um `Job` e devolve a resposta **sem** rodar `core.pipeline` na requisição
- [ ] O `status` devolvido por `POST /books` nunca é `ready`/`error` — é sempre o status inicial do `Book`
- [ ] `worker.process_job(job)` roda o pipeline, atualiza `Book.status` para `ready` (sucesso) ou `error` (falha), e chama `mark_done`/`mark_failed` no `JobQueue` correspondente
- [ ] `worker.run_worker()` aceita `max_iterations` para ser testável sem loop infinito
- [ ] Testes da OS-010 que assumiam resposta síncrona foram atualizados para o novo contrato, não deixados quebrados
- [ ] Um teste de ponta a ponta cobre o fluxo completo: `POST /books` → `worker.process_job` chamado diretamente no teste (sem precisar de thread/processo real) → `GET /books/{id}/status` reflete `ready`
- [ ] Um teste equivalente cobre o caminho de falha (pipeline lança exceção → `Book.status == "error"` → `Job` marcado `failed` com `error_message`)
- [ ] Testes usam dublês fake de `Extractor`/`Speaker` (mesmo padrão desde a OS-007) — nenhuma chamada real a Tesseract/Kokoro
- [ ] Nenhuma chamada de rede ou API paga

## 5. Testes exigidos (mínimo)

- `test_pdf_path_for_returns_same_path_for_api_and_worker`
- `test_post_books_returns_immediately_without_running_pipeline`
- `test_post_books_enqueues_a_job_for_the_created_book`
- `test_worker_process_job_marks_book_ready_on_success`
- `test_worker_process_job_marks_book_error_and_job_failed_on_pipeline_failure`
- `test_worker_run_worker_stops_after_max_iterations`
- `test_end_to_end_post_then_process_job_then_status_reflects_ready`

Local sugerido: `tests/unit/test_worker.py` (ou `tests/integration/`, dado que mistura `pipeline`+`queue`+`db`) e atualização de `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-012-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
