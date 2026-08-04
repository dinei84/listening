# OS-011 — Contrato JobQueue + SQLiteJobQueue

## 1. Objetivo

Implementar o contrato `JobQueue` (novo, aprovado pelo dono do projeto — decisão #11 em `PROJECT_STATE.md`, incorporado em `ARQUITETURA.md` seção 4.3) e sua primeira implementação concreta, `SQLiteJobQueue`. Esta OS entrega a fila isolada e testada; **não** liga isso em `worker/tasks.py` nem muda `api/routes_books.py` — isso é a próxima OS.

## 2. Escopo

**Dentro do escopo:**
- `plugins/queues/base.py` — classe abstrata `JobQueue` exatamente como especificado em `ARQUITETURA.md` seção 4.3: `enqueue(job)`, `claim_next()`, `mark_done(job_id)`, `mark_failed(job_id, error_message)`, `get_job(job_id)`.
- `plugins/queues/sqlite_queue.py` — `SQLiteJobQueue(JobQueue)`, usando `sqlite3` da stdlib (mesmo padrão de `storage/db.py`, sem ORM):
  - Tabela `jobs` própria (pode ser no mesmo arquivo de banco de `storage/db.py` ou um arquivo separado — decisão de implementação, documentar a escolha no relatório).
  - `claim_next()` precisa ser atômico: se dois `SQLiteJobQueue` (ou duas chamadas concorrentes) tentarem reivindicar ao mesmo tempo, **nenhum Job pode ser devolvido duas vezes**. Testar isso de verdade (ex: duas chamadas sequenciais a `claim_next()` com só um Job na fila — a segunda deve devolver `None`), não só assumir que `UPDATE ... WHERE status = 'queued'` é suficiente sem verificar.
- `plugins/registry.py` ganha `QUEUES = {"sqlite": SQLiteJobQueue}`, conforme `ARQUITETURA.md` seção 4.4.
- `config.yaml` ganha a chave `queue: sqlite`; `core/config.py` (`Config`) ganha o campo `queue: str`.

**Fora do escopo:**
- `worker/tasks.py` — o loop de polling que efetivamente consome a fila é a OS seguinte.
- Mudar `api/routes_books.py` — `POST /books` continua processando síncrono por enquanto; passar a enfileirar é a OS seguinte.
- `RedisJobQueue` ou qualquer outra implementação além de SQLite.
- Qualquer chamada de rede ou API paga.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.3 (JobQueue, contrato novo já aprovado — esta OS implementa, não propõe alterações) e seção 4.4 (Registro de plugins, `QUEUES` já especificado). Usa o modelo `Job` já existente em `core/models.py` (definido desde a OS-002, nunca usado até agora).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `JobQueue` não pode ser instanciada diretamente (é uma ABC com os 5 métodos abstratos)
- [ ] `SQLiteJobQueue.enqueue()` persiste um `Job` com status `queued`
- [ ] `SQLiteJobQueue.claim_next()` devolve o próximo `Job` com status `queued` e marca como `running`
- [ ] `SQLiteJobQueue.claim_next()` devolve `None` quando não há `Job` `queued` — inclusive depois que o único `Job` da fila já foi reivindicado (testar reivindicação dupla)
- [ ] `SQLiteJobQueue.mark_done()` atualiza o status para `done`
- [ ] `SQLiteJobQueue.mark_failed()` atualiza o status para `failed` e grava `error_message`
- [ ] `SQLiteJobQueue.get_job()` devolve o `Job` pelo id, `None` se não existir
- [ ] `plugins/registry.py` expõe `QUEUES["sqlite"] == SQLiteJobQueue`
- [ ] `core/config.py` lê a chave `queue` de `config.yaml`
- [ ] Testes usam banco SQLite temporário (`tmp_path`, mesmo padrão da OS-010) — nenhum lixo de teste no repositório
- [ ] Nenhuma chamada de rede ou API paga

## 5. Testes exigidos (mínimo)

- `test_job_queue_cannot_be_instantiated_directly`
- `test_sqlite_queue_enqueue_sets_status_queued`
- `test_sqlite_queue_claim_next_returns_and_marks_running`
- `test_sqlite_queue_claim_next_returns_none_when_empty`
- `test_sqlite_queue_claim_next_does_not_return_same_job_twice`
- `test_sqlite_queue_mark_done_updates_status`
- `test_sqlite_queue_mark_failed_updates_status_and_error_message`
- `test_sqlite_queue_get_job_returns_none_for_unknown_id`
- `test_registry_queues_contains_sqlite`
- `test_config_loads_queue_from_yaml`

Local sugerido: `tests/unit/queues/test_sqlite_queue.py`, `tests/unit/test_registry.py` (adicionar caso), `tests/unit/test_config.py` (adicionar caso).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-011-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
