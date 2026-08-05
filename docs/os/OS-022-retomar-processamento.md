# OS-022 — Retomar processamento interrompido

> **Depende da OS-021 (entrega incremental de áudio).** Sem persistência incremental não há como saber quais chunks de um `Job` interrompido já foram sintetizados — esta OS não faz sentido sem aquela primeiro.

## 1. Objetivo

Achado em uso real: ao interromper o worker no meio do processamento de um livro grande (Security Engineering, 1212 páginas), o `Job` ficou órfão em `status="running"` — o `SQLiteJobQueue.claim_next()` só busca `Job`s com `status="queued"`, então um `Job` "running" sem worker ativo fica invisível pra sempre, e todo o trabalho já feito se perde (seria preciso reenviar o livro do zero). Esta OS faz o worker detectar e retomar `Job`s órfãos ao iniciar, aproveitando os `AudioChunk`s já persistidos (OS-021) em vez de recomeçar do zero.

## 2. Escopo

**Dentro do escopo:**
- `plugins/queues/base.py` (`JobQueue`, ABC): adicionar um método novo — ex: `requeue_orphaned(self) -> list[Job]` — que encontra `Job`s com `status="running"` e os marca de volta como `queued`, devolvendo a lista dos que foram resetados. **Isso é uma extensão aditiva do contrato definido na OS-011** (`ARQUITETURA.md` seção 4.3): não muda nem remove nada que já existe, só adiciona um método novo que toda implementação de `JobQueue` precisa ter (hoje só `SQLiteJobQueue` existe). Atualizar `ARQUITETURA.md` seção 4.3 com a assinatura nova.
- `plugins/queues/sqlite_queue.py`: implementar `requeue_orphaned()`.
- `worker/tasks.py::run_worker()`: chamar `requeue_orphaned()` uma vez, **antes** de entrar no loop de polling — assume que só existe um worker rodando por vez (arquitetura atual, decisão #11), então qualquer `Job` encontrado em `running` na inicialização é necessariamente órfão (não tem como distinguir "outro worker ainda processando" de "worker anterior morreu no meio", porque não existe heartbeat/lease — documentar essa limitação explicitamente, não fingir que não existe).
- `worker/tasks.py::process_job()`: antes de começar a sintetizar, checar `storage.audio_store.list_chunks(book_id)` pra ver quais `sequence`s já foram persistidas (de uma tentativa anterior interrompida) e **pular a síntese dessas**, continuando só a partir do que falta.
- **Checagem de consistência, obrigatória:** re-extrair e re-chunkar o texto (`extract_clean_text()` + `chunk_text()`) numa retomada deve, em teoria, produzir os mesmos chunks de antes (determinístico, dado o mesmo PDF). Mas isso é uma suposição, não uma garantia absoluta (ex: se o código de `chunk_text()`/`clean_text()` mudou entre a tentativa original e a retomada). Se o número de chunks recalculado for menor que o maior `sequence` já persistido, ou qualquer outra inconsistência detectável, **não seguir em frente silenciosamente** — logar claramente e cair num caminho seguro definido (ex: descartar os chunks já persistidos pra esse livro e recomeçar do zero, ou marcar `Book.status="error"` pedindo reenvio manual — decisão de implementação, documentar a escolha e o porquê no relatório).

**Fora de escopo:**
- Múltiplos workers rodando ao mesmo tempo, heartbeat/lease de `Job` (saber se um "running" é de um worker vivo ou morto sem só assumir "só há um worker") — fora do escopo de um projeto pessoal com um worker só, mas documentar a limitação.
- Retomar automaticamente livros que já falharam com `status="error"` antes desta OS existir — a OS não faz retry automático de erros, só resume `Job`s que ficaram órfãos em `running`.
- Qualquer mudança em `plugins/extractors/`, `plugins/speakers/`, ou no contrato `Extractor`/`Speaker`.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.3 (`JobQueue`) ganha um método novo (`requeue_orphaned()` ou nome equivalente) — extensão aditiva, proposta nesta própria OS (documentar antes de implementar, mesmo processo já usado quando o contrato `JobQueue` foi criado na OS-011).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `JobQueue` (ABC) tem um método novo pra resetar `Job`s órfãos de `running` para `queued`, documentado em `ARQUITETURA.md` seção 4.3
- [ ] `SQLiteJobQueue` implementa esse método
- [ ] `run_worker()` chama esse método uma vez ao iniciar, antes do loop de polling
- [ ] `process_job()` pula a síntese de `sequence`s já persistidas pro `book_id`, sintetiza só o que falta
- [ ] Existe uma checagem de consistência explícita (não silenciosa) entre o que foi recalculado e o que já estava persistido, com um caminho seguro definido pra quando não bater
- [ ] Teste automatizado: simula um `Job` órfão com alguns `AudioChunk`s já persistidos, chama o sweep de retomada, confirma que só os chunks faltantes são sintetizados (dublê de `Speaker` conta quantas vezes foi chamado)
- [ ] Teste automatizado: simula uma inconsistência (ex: menos chunks recalculados que os já persistidos) e confirma que o caminho seguro definido é seguido, não um comportamento silencioso/indefinido
- [ ] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 5. Testes exigidos (mínimo)

- `test_sqlite_queue_requeue_orphaned_resets_running_jobs_to_queued`
- `test_sqlite_queue_requeue_orphaned_ignores_queued_and_done_jobs`
- `test_worker_run_worker_requeues_orphaned_jobs_on_startup`
- `test_worker_process_job_skips_already_persisted_chunks`
- `test_worker_process_job_handles_chunk_count_inconsistency_safely`

Local sugerido: `tests/unit/queues/test_sqlite_queue.py` e `tests/unit/test_worker.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-022-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
