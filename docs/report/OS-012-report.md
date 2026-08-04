# OS-012 — Relatório de entrega

**Data:** 2026-08-04
**Branch:** os/012-worker-async-books
**Commit(s) relevante(s):** 1a7a4e1 (test: Red), 88487c8 (feat: Green)

## 1. Resumo do que foi feito

`POST /books` agora salva o PDF, cria o `Book` e **enfileira** um `Job` (`stage="process"`) via `JobQueue`, respondendo imediatamente com o status inicial (`uploaded`) — sem rodar `core.pipeline` na requisição. `worker/tasks.py` ganhou `process_job(job)` (roda o pipeline de ponta a ponta e marca `Book`/`Job` como concluído ou falho) e `run_worker(poll_interval, max_iterations)` (loop de polling, testável via `max_iterations`, com `python -m worker.tasks` para rodar manualmente). Novo `storage/uploads.py` centraliza `UPLOAD_DIR`/`pdf_path_for(book_id)`, usado tanto por `api/routes_books.py` quanto por `worker/tasks.py`.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `1a7a4e1` "Red" existe antes de `88487c8` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (69 testes no total, todos passando — ver seção 5 sobre os 2 testes da OS-010 que foram substituídos, não deixados quebrados)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (`worker/tasks.py` resolve `JobQueue` só por nome via `registry`/`config`, nunca importa `SQLiteJobQueue` diretamente — mesma regra da OS-007 aplicada a extractor/speaker)
- [x] Nenhuma chamada real a API paga dentro dos testes — dublês fake de `Extractor`/`Speaker`; `SQLiteJobQueue` real, mas local e sem custo (mesmo padrão da OS-011)
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2)
- [x] Relatório criado em `docs/report/OS-012-report.md`
- [x] PR aberto contra o branch principal, com título `[OS-012] Liga JobQueue em worker/tasks.py e na API`

### DoD específico da OS (seção 4 de `docs/os/OS-012-worker-async-books.md`)

- [x] `storage/uploads.py` centraliza o caminho do PDF enviado; `api/routes_books.py` e `worker/tasks.py` usam a mesma função (`uploads.pdf_path_for`), sem literais duplicados
- [x] `POST /books` enfileira um `Job` e devolve a resposta sem rodar `core.pipeline` na requisição
- [x] O `status` devolvido por `POST /books` nunca é `ready`/`error` — é sempre `uploaded` (status inicial do `Book`)
- [x] `worker.process_job(job)` roda o pipeline, atualiza `Book.status` para `ready`/`error`, e chama `mark_done`/`mark_failed` no `JobQueue` correspondente
- [x] `worker.run_worker()` aceita `max_iterations` para ser testável sem loop infinito
- [x] Testes da OS-010 que assumiam resposta síncrona foram atualizados para o novo contrato (ver seção 5 — substituídos, não deixados quebrados)
- [x] Um teste de ponta a ponta cobre o fluxo completo: `POST /books` → `worker.process_job` chamado diretamente no teste → `GET /books/{id}/status` reflete `ready` (`test_end_to_end_post_then_process_job_then_status_reflects_ready`)
- [x] Um teste equivalente cobre o caminho de falha (`test_worker_process_job_marks_book_error_and_job_failed_on_pipeline_failure`)
- [x] Testes usam dublês fake de `Extractor`/`Speaker` — nenhuma chamada real a Tesseract/Kokoro
- [x] Nenhuma chamada de rede ou API paga

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_pdf_path_for_returns_same_path_for_api_and_worker` | `tests/unit/test_uploads.py` | Sim |
| `test_worker_process_job_marks_book_ready_on_success` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_marks_book_error_and_job_failed_on_pipeline_failure` | `tests/unit/test_worker.py` | Sim |
| `test_worker_run_worker_stops_after_max_iterations` | `tests/unit/test_worker.py` | Sim |
| `test_post_books_returns_immediately_without_running_pipeline` | `tests/integration/test_api_books.py` | Sim |
| `test_post_books_enqueues_a_job_for_the_created_book` | `tests/integration/test_api_books.py` | Sim |
| `test_end_to_end_post_then_process_job_then_status_reflects_ready` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Testes falhando antes da implementação (commit Red, `1a7a4e1`):

```
tests/unit/test_uploads.py:1: in <module>
    from storage import uploads
E   ImportError: cannot import name 'uploads' from 'storage'

tests/unit/test_worker.py:12: in <module>
    from storage import uploads as uploads_module
E   ImportError: cannot import name 'uploads' from 'storage'

tests/integration/test_api_books.py:14: in <module>
    from storage import uploads as uploads_module
E   ImportError: cannot import name 'uploads' from 'storage'
```

Suíte completa após a implementação (commit Green, `88487c8`, e após ajustes de import/lint):

```
$ python -m pytest -q
.....................................................................    [100%]
69 passed, 1 warning in 5.76s
```

O warning é o mesmo `StarletteDeprecationWarning` pré-existente já registrado nos relatórios da OS-010/OS-011 (não introduzido por esta OS).

`black --check` e `ruff check` nos arquivos tocados por esta OS: sem alterações pendentes, todos os checks passaram (um `I001` de import não ordenado em `worker/tasks.py` foi corrigido — `from storage import db, uploads` numa linha só).

## 5. Desvios do escopo original

Nenhum desvio de escopo. Implementados apenas `storage/uploads.py`, `worker/tasks.py` e a mudança de `api/routes_books.py` (`POST /books` passa a enfileirar). `plugins/queues/`, `storage/db.py` e os contratos de `Extractor`/`Speaker` não foram tocados, conforme declarado fora de escopo.

Sobre a exigência explícita da OS de "atualizar os testes da OS-010 que assumiam resposta síncrona": os dois testes originais (`test_post_books_creates_book_and_returns_ready_status`, `test_post_books_returns_error_status_when_pipeline_fails`) tinham premissas que deixaram de fazer sentido sob o novo contrato assíncrono — o primeiro assumia que a resposta trazia `status="ready"` (agora é sempre `"uploaded"`), o segundo testava uma falha de pipeline acontecendo *durante a requisição* (agora o pipeline nunca roda na requisição, então esse cenário não existe mais nesta camada). Em vez de forçar essas duas funções a continuarem existindo com o mesmo nome mas semântica reescrita, eu:
- Substituí `test_post_books_creates_book_and_returns_ready_status` por `test_post_books_returns_immediately_without_running_pipeline` (mesmo papel: valida o que `POST /books` devolve, mas para o comportamento correto agora).
- Removi `test_post_books_returns_error_status_when_pipeline_fails` da camada de API — o cenário de "pipeline falha" continua coberto, só que no nível certo agora: `test_worker_process_job_marks_book_error_and_job_failed_on_pipeline_failure`, em `tests/unit/test_worker.py`, testando `worker.process_job()` diretamente, que é onde o pipeline de fato roda agora.

Nenhuma cobertura foi perdida — o comportamento de "requisição nunca quebra, falha vira status persistido" continua testado, só mudou de camada (API → worker), o que é exatamente o que a OS pede ao mover a execução do pipeline para fora da requisição. Isso está sendo registrado explicitamente aqui porque é uma interpretação de "atualizar" como "substituir por teste equivalente na camada correta" em vez de "editar o corpo da função mantendo o nome".

## 6. Dúvidas / bloqueios

Nenhuma. Reforçando a nota já registrada no relatório da OS-011 (não é um bloqueio, só contexto): `plugins/queues/sqlite_queue.py` mantém seu próprio `DEFAULT_DB_PATH` (mesmo valor de `storage/db.py`, não importado de lá) — os testes desta OS precisam sincronizar os dois via `monkeypatch` (`db_module.DEFAULT_DB_PATH` e `sqlite_queue_module.DEFAULT_DB_PATH` apontando para o mesmo arquivo temporário) sempre que quiserem `Book`s e `Job`s no mesmo banco de teste. Isso funcionou sem atrito nesta OS, só documentando o padrão para quem for escrever testes parecidos depois.

## 7. Link do PR

https://github.com/dinei84/listening/pull/10
