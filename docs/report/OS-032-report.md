# OS-032 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/032-preempcao-de-fila
**Commit(s) relevante(s):** bce6bd9 (test: Red), 6237028 (feat: Green), 087a6e6 (docs)

## 1. Resumo do que foi feito

Preempção de fila cooperativa: cada `Job` ganhou `priority: int = 0` (coluna `priority INTEGER NOT NULL DEFAULT 0` na tabela `jobs`), e `claim_next()` passou a ordenar por `priority DESC, rowid` — sem prioridade definida, o comportamento é idêntico ao FIFO de hoje. Dentro do `on_chunk` que já existia desde a OS-021, o worker consulta `queue.should_yield(job.id)` e, se existe um `Job` `queued` de prioridade maior, interrompe a síntese no fim do chunk corrente (exceção sentinela interna), devolve o próprio `Job` para `queued` via `requeue()` **preservando a prioridade** (não é falha) e marca o `Book` como `paused` — nada é apagado, a retomada continua de onde parou via `skip_sequences` (OS-022). Novo endpoint `POST /books/{id}/prioritize` coloca o `Job` do livro no topo (404 se o livro ou o `Job` dele não existir; 409 se `ready`/`error`); livro `paused` é deletável (não entra em `_BLOCKED_DELETE_STATUSES`) e continua tocável no player com o áudio já sintetizado, com o polling parado. UI ganhou o botão "Processar agora" em cada item de "Meus livros" (habilitado só para `uploaded`/`paused`).

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `bce6bd9` "Red" antes de `6237028` "Green")
- [x] Todos os testes da OS passam localmente — 156 pass, 0 fail
- [x] Nenhum teste existente quebrou (134 anteriores + 22 novos = 156)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `prioritize`/`should_yield`/`requeue`/`get_job_for_book` documentados na seção 4.3, `Job.priority` e `Book.status` `"paused"` na seção 5, atualizados no mesmo PR
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — FakeExtractor/FakeSpeaker/CountingSpeaker nos testes de worker/API
- [x] Type hints e docstring de uma linha em toda função pública nova/alterada
- [x] `PROJECT_STATE.md` atualizado (seções 2, 3, 4, 5 e 6)
- [x] Relatório criado em `docs/report/OS-032-report.md`
- [x] PR aberto contra o branch principal, título `[OS-032] ...`

### DoD específico da OS (`docs/os/OS-032-preempcao-de-fila.md` seção 4)

- [x] Sem nenhuma prioridade definida, a ordem de atendimento da fila é idêntica à de hoje (FIFO por `rowid`) — `test_sqlite_queue_claim_next_keeps_fifo_when_no_priority_set` + toda a suíte antiga (OS-011/012/022) verde
- [x] `prioritize()` faz o `Job` alvo ser o próximo reivindicado por `claim_next()`, mesmo tendo entrado depois na fila — `test_sqlite_queue_prioritize_makes_job_claimed_first`
- [x] `should_yield()` devolve `True` só quando existe `Job` `queued` com prioridade **maior** que a do `Job` corrente — `test_sqlite_queue_should_yield_true_when_higher_priority_queued` / `test_sqlite_queue_should_yield_false_when_no_higher_priority` / `test_sqlite_queue_should_yield_false_for_unknown_job`
- [x] Com a síntese em andamento, priorizar outro livro faz o worker parar no fim do chunk corrente, devolver o `Job` para `queued` (não `failed`) e marcar o `Book` como `paused` — `test_worker_process_job_yields_when_higher_priority_arrives` + `test_worker_yield_requeues_job_without_marking_failed` + `test_worker_yield_sets_book_status_to_paused_and_keeps_chunks`
- [x] Nenhum `AudioChunk` já persistido é apagado ao pausar — `test_worker_yield_sets_book_status_to_paused_and_keeps_chunks` (chunk 0 persistido e existente em disco após o yield)
- [x] Retomar um livro pausado continua de onde parou, sem re-sintetizar o que já existe (reaproveita a OS-022) — verificado por contagem de chamadas ao dublê de `Speaker`: `test_worker_resumes_paused_book_without_resynthesizing` (`[texto[0] for ...] == ["A", "B", "C"]`, chunk "A" sintetizado só na primeira tentativa)
- [x] Um livro `paused` pode ser deletado (não entra em `_BLOCKED_DELETE_STATUSES`) — `test_delete_book_allowed_when_paused`
- [x] O áudio já sintetizado de um livro `paused` continua tocável no player, e o polling para — implementado em `player/app.js` (`pollBook` para em `ready`/`error`/`paused`; `statusMessage` mostra "Pausado — tocando o que já foi sintetizado." quando há chunks); coberto por revisão de código, verificação manual pendente (seção 6)
- [x] `RUNBOOK.md` avisa sobre a coluna `priority` exigindo `ALTER TABLE`/recriar o `books.db` local — seção 8

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_sqlite_queue_claim_next_keeps_fifo_when_no_priority_set` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_prioritize_makes_job_claimed_first` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_prioritize_priority_strictly_greater_than_running` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_should_yield_true_when_higher_priority_queued` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_should_yield_false_when_no_higher_priority` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_should_yield_false_for_unknown_job` (extra) | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_get_job_returns_priority` (extra) | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_requeue_preserves_priority` (extra) | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_requeue_does_not_affect_other_jobs` (extra) | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_get_job_for_book_returns_most_recent_job` (extra) | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_get_job_for_book_returns_none_for_unknown_book` (extra) | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_worker_process_job_yields_when_higher_priority_arrives` | `tests/unit/test_worker.py` | Sim |
| `test_worker_yield_requeues_job_without_marking_failed` | `tests/unit/test_worker.py` | Sim |
| `test_worker_yield_sets_book_status_to_paused_and_keeps_chunks` | `tests/unit/test_worker.py` | Sim |
| `test_worker_resumes_paused_book_without_resynthesizing` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_completes_when_no_higher_priority_job` (extra, controle positivo) | `tests/unit/test_worker.py` | Sim |
| `test_post_books_prioritize_returns_404_for_unknown_book` | `tests/integration/test_api_books.py` | Sim |
| `test_post_books_prioritize_makes_queued_book_claimed_next` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_post_books_prioritize_returns_409_for_ready_book` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_post_books_prioritize_returns_404_when_book_has_no_job` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_post_books_prioritize_pushes_paused_book_to_front` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_delete_book_allowed_when_paused` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `bce6bd9` (20 falhas: `AttributeError: 'SQLiteJobQueue' object has no attribute 'prioritize'` / `should_yield` / `requeue` / `get_job_for_book`, `OperationalError: no such column: priority` na tabela `jobs`, `404 Not Found` no endpoint `prioritize`, `AssertionError` no yield do worker) antes de `6237028`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação):
```
20 failed, 50 passed, 1 warning in 8.72s
```

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
156 passed, 1 warning in 8.81s
```

```
$ venv/bin/ruff check core/ plugins/ worker/ api/ storage/ tests/
All checks passed!
$ venv/bin/black --check core/ plugins/ worker/ api/ storage/ tests/
58 files would be left unchanged.
```

`player/app.js` não passa pelo black (é JS; verificado com `node --check player/app.js`, OK).

## 5. Desvios do escopo original

**Um, documentado:** a OS define que o contrato `JobQueue` ganha **dois** métodos (`prioritize`, `should_yield`). A implementação precisou de **dois adicionais** na mesma extensão aditiva, no mesmo padrão das OS-022/023:

- `requeue(job_id)` — o caminho de yield manda o worker devolver o `Job` para `queued` preservando a prioridade, e não existe nenhum método do contrato que faça isso para um `Job` individual (`requeue_orphaned()` devolve *todos* os `running`, `mark_failed`/`mark_done` não servem). Sem ele o critério de aceite "devolver o `Job` para `queued` (não `failed`)" é impossível.
- `get_job_for_book(book_id)` — o endpoint `POST /books/{id}/prioritize` precisa localizar o `Job` de um livro para chamar `prioritize(job_id)`; o contrato não tinha nenhuma busca por `book_id` (só `delete_jobs_for_book`, que apaga, e `get_job`, que exige o `job_id`).

Ambos são puramente aditivos (nenhum comportamento existente muda) e foram espelhados em `ARQUITETURA.md` seção 4.3 no mesmo PR. Registrar no relatório por transparência, como pede o `AGENTS.md` seção 3.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Decisões de implementação que a OS deixou em aberto e como foram resolvidas (registradas também na decisão #21 do ADL):

1. **`prioritize()` usa `MAX(priority) + 1` sobre a tabela inteira de `jobs`** (não só sobre `queued`). Se fosse só sobre `queued`, priorizar um livro enquanto o `Job` corrente já tem prioridade alta (ex: 2, de uma priorização anterior) daria ao novo uma prioridade ≤ a do corrente e o `should_yield` do corrente nunca dispararia — a preempção não funcionaria. `MAX` global garante estritamente maior que qualquer pendente (`queued` ou `running`).
2. **`POST /books/{id}/prioritize` responde 409 para `ready` **e** `error`.** A OS sugere 409 para `ready` ("não há o que processar"); estendi ao `error` pelo mesmo motivo — o `Job` de um livro `error` está `failed`, priorizá-lo seria um no-op silencioso (`claim_next()` só enxerga `queued`), e uma resposta 200 mentiria que algo aconteceu.
3. **Granularidade do yield:** a checagem é feita após cada chunk persistido no `on_chunk` (inclusive o último). Se um livro terminar exatamente quando um concorrente for priorizado, ele pode ser marcado `paused` com todos os chunks prontos — caso raro e auto-curável: ao ser re-priorizado, o worker re-claima, encontra tudo persistido (OS-022) e marca `ready`.
4. **Verificação manual em navegador real do botão "Processar agora" segue pendente** (mesmo padrão do seletor de idioma da OS-025): envolve esperar síntese real (~1s/chunk) e o polling do player. Registrado em `PROJECT_STATE.md` seção 6.

## 7. Link do PR

A preencher após abertura do PR.
