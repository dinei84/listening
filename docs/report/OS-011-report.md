# OS-011 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** os/011-job-queue
**Commit(s) relevante(s):** b1ee3d1 (test: Red), 087876e (feat: Green)

## 1. Resumo do que foi feito

Implementado o contrato `JobQueue` (`plugins/queues/base.py`, copiado verbatim de `ARQUITETURA.md` seção 4.3) e sua primeira implementação, `SQLiteJobQueue` (`plugins/queues/sqlite_queue.py`), com `claim_next()` atomicamente seguro contra reivindicação dupla. `plugins/registry.py` ganhou `QUEUES = {"sqlite": SQLiteJobQueue}` e `core/config.py`/`config.yaml` ganharam o campo `queue`. Fila isolada e testada; nada foi ligado em `worker/tasks.py` ou `api/routes_books.py` (fora de escopo, próxima OS).

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `b1ee3d1` "Red" existe antes de `087876e` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (64 testes no total, todos passando)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (`JobQueue` copiado exatamente da seção 4.3, `QUEUES` no registry conforme seção 4.4)
- [x] Nenhuma chamada real a API paga dentro dos testes — `SQLiteJobQueue` só usa `sqlite3` local
- [x] Type hints e docstring de uma linha em toda função pública (exceção: `claim_next()` na classe base mantém o docstring multi-linha exatamente como especificado em `ARQUITETURA.md`, por ser cópia literal de um contrato já aprovado)
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2)
- [x] Relatório criado em `docs/report/OS-011-report.md`
- [ ] PR aberto contra o branch principal, com título `[OS-011] Contrato JobQueue + SQLiteJobQueue` — a abrir na próxima etapa deste fluxo

### DoD específico da OS (seção 4 de `docs/os/OS-011-job-queue.md`)

- [x] `JobQueue` não pode ser instanciada diretamente (ABC com os 5 métodos abstratos)
- [x] `SQLiteJobQueue.enqueue()` persiste um `Job` com status `queued`
- [x] `SQLiteJobQueue.claim_next()` devolve o próximo `Job` com status `queued` e marca como `running`
- [x] `SQLiteJobQueue.claim_next()` devolve `None` quando não há `Job` `queued`, inclusive depois que o único `Job` da fila já foi reivindicado (testado com duas chamadas sequenciais — `test_sqlite_queue_claim_next_does_not_return_same_job_twice`)
- [x] `SQLiteJobQueue.mark_done()` atualiza o status para `done`
- [x] `SQLiteJobQueue.mark_failed()` atualiza o status para `failed` e grava `error_message`
- [x] `SQLiteJobQueue.get_job()` devolve o `Job` pelo id, `None` se não existir
- [x] `plugins/registry.py` expõe `QUEUES["sqlite"] == SQLiteJobQueue`
- [x] `core/config.py` lê a chave `queue` de `config.yaml`
- [x] Testes usam banco SQLite temporário (`tmp_path`, mesmo padrão da OS-010) — nenhum lixo de teste no repositório (confirmado: sem `books.db`/`uploads/` no working tree após rodar a suíte)
- [x] Nenhuma chamada de rede ou API paga

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_job_queue_cannot_be_instantiated_directly` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_enqueue_sets_status_queued` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_claim_next_returns_and_marks_running` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_claim_next_returns_none_when_empty` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_claim_next_does_not_return_same_job_twice` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_mark_done_updates_status` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_mark_failed_updates_status_and_error_message` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_get_job_returns_none_for_unknown_id` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_registry_queues_contains_sqlite` | `tests/unit/test_registry.py` | Sim |
| `test_config_loads_queue_from_yaml` | `tests/unit/test_config.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Testes falhando antes da implementação (commit Red, `b1ee3d1`):

```
tests/unit/queues/test_sqlite_queue.py:4: in <module>
    from plugins.queues.base import JobQueue
E   ModuleNotFoundError: No module named 'plugins.queues.base'

tests/unit/test_registry.py:3: in <module>
    from plugins.queues.sqlite_queue import SQLiteJobQueue
E   ModuleNotFoundError: No module named 'plugins.queues.sqlite_queue'

tests/unit/test_config.py::test_config_loads_queue_from_yaml
  AttributeError: 'Config' object has no attribute 'queue'
```

Suíte completa após a implementação (commit Green, `087876e`, e após formatação):

```
$ python -m pytest -q
................................................................         [100%]
64 passed, 1 warning in 5.75s
```

O warning é o mesmo `StarletteDeprecationWarning` pré-existente já registrado no relatório da OS-010 (não introduzido por esta OS).

`black --check` e `ruff check` nos arquivos tocados por esta OS: sem alterações pendentes, todos os checks passaram.

## 5. Desvios do escopo original

Nenhum. Implementados somente `plugins/queues/base.py`, `plugins/queues/sqlite_queue.py`, a entrada `QUEUES` em `plugins/registry.py` e o campo `queue` em `core/config.py`/`config.yaml`. `worker/tasks.py` e `api/routes_books.py` não foram tocados, conforme declarado fora de escopo.

Decisão de implementação explicitamente deixada em aberto pela OS, a documentar aqui:

- **Tabela `jobs` no mesmo arquivo de banco de `storage/db.py`** (`books.db`, mesmo `DEFAULT_DB_PATH` — string duplicada intencionalmente entre os dois módulos, não importada de um para o outro, para manter `plugins/queues/sqlite_queue.py` desacoplado de `storage/db.py`; ver seção 6 abaixo). Optei por isso em vez de um arquivo separado porque é um projeto pessoal de baixa infraestrutura (`HANDOFF.md` seção 2) — um único arquivo SQLite para gerenciar/fazer backup é mais simples, e não há razão de performance ou concorrência para separar neste estágio. Se isso se tornar um problema (ex: contenção de lock entre `books` e `jobs`), trocar para um arquivo separado é uma mudança isolada em `plugins/queues/sqlite_queue.py`, sem tocar em `storage/db.py` nem em quem consome `JobQueue`.
- **Atomicidade de `claim_next()`:** implementada com uma transação explícita `BEGIN IMMEDIATE` (adquire lock de escrita do SQLite imediatamente, não de forma adiada) + `SELECT` do próximo job `queued` + `UPDATE ... WHERE id = ? AND status = 'queued'` + `COMMIT`. Isso é seguro tanto para chamadas sequenciais na mesma conexão quanto para múltiplas conexões/processos concorrentes apontando para o mesmo arquivo, porque o SQLite serializa escritores via lock de arquivo assim que `BEGIN IMMEDIATE` é executado — não depende de sorte de timing. Testado com duas chamadas sequenciais a `claim_next()` (única forma determinística de testar isso sem infra de concorrência real em processo único), conforme pedido explicitamente pela OS.

## 6. Dúvidas / bloqueios

Nenhuma. Um ponto que registro por transparência (não é um bloqueio, é uma decisão de implementação já justificada acima): `plugins/queues/sqlite_queue.py` define seu próprio `DEFAULT_DB_PATH = "books.db"`, com o mesmo valor literal que `storage/db.py` já usa, em vez de importar a constante de lá. Isso é intencional (evita acoplar o plugin de fila ao módulo de storage), mas significa que se alguém mudar o caminho do banco em um módulo sem mudar no outro, os dois arquivos podem divergir silenciosamente. Como ambos têm o mesmo valor hoje e nenhuma OS até agora tornou o caminho do banco configurável via `config.yaml`/env var, não vejo isso como um problema imediato — só registrando para o caso de uma OS futura mexer nisso.

## 7. Link do PR

A preencher após abertura do PR na próxima etapa.
