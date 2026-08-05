# OS-032 — Preempção de fila: "Processar agora"

## 1. Objetivo

Achado em uso real: o worker processa **um `Job` por vez, em ordem FIFO**, sem nenhuma forma de mudar de ideia. Com o "Security Engineering" (3334 chunks, horas de síntese) na frente, dois livros enviados depois ficaram parados em `queued` indefinidamente — o dono do projeto não tinha como dizer "deixa esse pra depois, quero ouvir aquele agora". Esta OS adiciona um botão "Processar agora" por livro: pausa a síntese em andamento e coloca o livro escolhido na frente da fila.

**A parte difícil já está pronta e testada** — a OS-021 persiste cada `AudioChunk` assim que fica pronto, e a OS-022 já faz `process_job()` pular as `sequence`s já persistidas. Pausar é, portanto, "parar de sintetizar e devolver o `Job` para a fila": retomar depois continua exatamente de onde parou, reaproveitando o mecanismo de retomada que já existe.

## 2. Escopo

**Dentro do escopo:**

- **`Job.priority: int = 0`** (`core/models.py`) — maior número = atendido primeiro. Coluna nova `priority INTEGER NOT NULL DEFAULT 0` na tabela `jobs`.
  - **Nota de schema (obrigatória):** não existe migração automática de SQLite neste projeto (`PROJECT_STATE.md` seção 6). Um `books.db` local existente vai precisar de `ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 0` ou de ser recriado. Avisar no `RUNBOOK.md`, no mesmo lugar que já avisa sobre `error_message` (OS-018), `chunk_total` (OS-024) e `language` (OS-025).

- **`claim_next()` passa a ordenar por `priority DESC, rowid ASC`** (`plugins/queues/sqlite_queue.py`) — sem prioridade definida, o comportamento é idêntico ao de hoje (todos com `priority = 0` → FIFO puro por `rowid`). **Isso é essencial:** hoje `claim_next()` ordena só por `rowid`, então um `Job` pausado (o mais antigo da fila) seria reivindicado de novo imediatamente e a pausa não funcionaria.

- **Contrato `JobQueue` (ABC) ganha dois métodos** — extensão aditiva, mesmo padrão já usado na OS-022 (`requeue_orphaned()`) e OS-023 (`delete_jobs_for_book()`). Atualizar `ARQUITETURA.md` seção 4.3:
  - `prioritize(job_id: str) -> None` — dá ao `Job` uma prioridade maior que a de qualquer outro `Job` pendente.
  - `should_yield(job_id: str) -> bool` — devolve `True` se existe um `Job` **`queued` com prioridade maior** que a do `Job` informado. É a pergunta que o worker faz entre um chunk e outro; nenhum estado extra de "pedido de pausa" é necessário, a própria prioridade dirige a decisão.

- **`worker/tasks.py::process_job()`**: dentro do callback `on_chunk` que já existe (chamado após cada chunk desde a OS-021), consultar `queue.should_yield(job.id)`. Se `True`, interromper a síntese de forma cooperativa (ex: exceção sentinela interna, capturada logo acima) e:
  - devolver o `Job` para `queued` **preservando sua prioridade** (não é falha — não usar `mark_failed`);
  - marcar `Book.status = "paused"`;
  - **não apagar nada** — os `AudioChunk`s já persistidos são justamente o que permite retomar depois.
  - Granularidade aceita e documentada: a parada acontece no fim do chunk corrente (~1s), nunca no meio de um chunk — interromper no meio desperdiçaria aquele trecho.

- **`Book.status` ganha `"paused"`** no `Literal` de `core/models.py`. Não exige migração (a coluna `status` é `TEXT`), mas exige revisar quem lê status:
  - `api/routes_books.py`: **`"paused"` deve ser deletável** — `_BLOCKED_DELETE_STATUSES` (decisão #17) bloqueia exclusão porque o worker pode estar escrevendo; num livro pausado ninguém está escrevendo. Não adicionar `"paused"` à lista de bloqueio.
  - `player/app.js`: um livro `paused` **não é erro nem fim** — o polling deve parar (não há mais chunk novo vindo), mas o áudio já sintetizado continua tocável, mesmo espírito do tratamento de `error` da OS-030.

- **Endpoint novo:** `POST /books/{id}/prioritize` — chama `prioritize()` no `Job` daquele livro. Se o livro estiver `paused`, volta para a fila com a prioridade nova. 404 se o livro (ou o `Job` dele) não existir. Decisão de implementação a documentar: o que fazer se o livro já estiver `ready` (sugestão: 409, não há o que processar).

- **`player/index.html` + `player/app.js`**: botão "Processar agora" em cada item de "Meus livros", ao lado do "Deletar" (usar `event.stopPropagation()`, como o botão de deletar já faz, para não abrir o livro junto). Após sucesso, atualizar a lista.

**Fora do escopo:**
- Múltiplos workers em paralelo / processar dois livros ao mesmo tempo — continua um worker por vez (decisão #11). Esta OS muda **a ordem**, não o paralelismo.
- Prioridade automática (ex: priorizar sozinho o livro aberto no player) — a troca é sempre explícita, por botão.
- Reordenar a fila livremente (arrastar, definir posição N) — só "põe este na frente".
- Cancelar definitivamente um `Job` (diferente de pausar) — quem quiser descartar de vez usa `DELETE /books/{id}`.

## 3. Contratos envolvidos

`JobQueue` (`ARQUITETURA.md` seção 4.3) ganha `prioritize()` e `should_yield()` — extensão aditiva, nada existente muda de comportamento; toda implementação de `JobQueue` precisa passar a tê-los (hoje só `SQLiteJobQueue`). `Job` (seção 5) ganha `priority: int = 0`; `Book.status` (seção 5) ganha `"paused"`.

**Decisão de arquitetura a registrar no ADL:** a preempção é **cooperativa** (o worker checa entre chunks), não preemptiva de verdade (não há kill de processo nem thread interrompida). Isso é intencional: mantém a filosofia de baixa infraestrutura do projeto e reaproveita o `on_chunk` que já existe, ao custo de até ~1s de latência para a troca.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Sem nenhuma prioridade definida, a ordem de atendimento da fila é idêntica à de hoje (FIFO por `rowid`) — nenhum teste da OS-011/012/022 quebra
- [ ] `prioritize()` faz o `Job` alvo ser o próximo reivindicado por `claim_next()`, mesmo tendo entrado depois na fila
- [ ] `should_yield()` devolve `True` só quando existe `Job` `queued` com prioridade **maior** que a do `Job` corrente
- [ ] Com a síntese em andamento, priorizar outro livro faz o worker parar no fim do chunk corrente, devolver o `Job` para `queued` (não `failed`) e marcar o `Book` como `paused`
- [ ] Nenhum `AudioChunk` já persistido é apagado ao pausar
- [ ] Retomar um livro pausado continua de onde parou, sem re-sintetizar o que já existe (reaproveita a OS-022) — verificado por contagem de chamadas ao dublê de `Speaker`
- [ ] Um livro `paused` pode ser deletado (não entra em `_BLOCKED_DELETE_STATUSES`)
- [ ] O áudio já sintetizado de um livro `paused` continua tocável no player, e o polling para
- [ ] `RUNBOOK.md` avisa sobre a coluna `priority` exigindo `ALTER TABLE`/recriar o `books.db` local

## 5. Testes exigidos (mínimo)

- `test_sqlite_queue_claim_next_keeps_fifo_when_no_priority_set` (regressão)
- `test_sqlite_queue_prioritize_makes_job_claimed_first`
- `test_sqlite_queue_should_yield_true_when_higher_priority_queued`
- `test_sqlite_queue_should_yield_false_when_no_higher_priority`
- `test_worker_process_job_yields_when_higher_priority_arrives`
- `test_worker_yield_requeues_job_without_marking_failed`
- `test_worker_yield_sets_book_status_to_paused_and_keeps_chunks`
- `test_worker_resumes_paused_book_without_resynthesizing` (integra com a OS-022)
- `test_delete_book_allowed_when_paused`
- `test_post_books_prioritize_returns_404_for_unknown_book`

Local sugerido: `tests/unit/queues/test_sqlite_queue.py`, `tests/unit/test_worker.py`, `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-032-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
