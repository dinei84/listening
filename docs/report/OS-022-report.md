# OS-022 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/022-retomar-processamento (criado a partir de `os/021-entrega-incremental-audio`, já que a OS-022 depende da OS-021 e o PR #18 ainda não foi mergeado)
**Commit(s) relevante(s):** 2c10373 (test: Red), 5d4abe7 (feat: Green)

## 1. Resumo do que foi feito

`JobQueue` ganhou `requeue_orphaned() -> list[Job]` (extensão aditiva do contrato da OS-011, implementado em `SQLiteJobQueue`), chamado uma vez por `run_worker()` antes do loop de polling — todo `Job` preso em `running` volta para `queued` e é reprocessado. `process_job()` passou a consultar `audio_store.list_chunks(book_id)` antes de sintetizar e pular as `sequence`s já persistidas por uma tentativa anterior, com checagem explícita de consistência contra o texto re-extraído/re-chunkado.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `2c10373` "Red" antes de `5d4abe7` "Green")
- [x] Todos os testes da OS passam localmente — 107 pass, 0 fail
- [x] Nenhum teste existente quebrou (99 anteriores + 8 novos = 107)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `requeue_orphaned()` documentado na seção 4.3 antes da implementação; contratos `Extractor`/`Speaker` inalterados; `worker/tasks.py` continua resolvendo a fila via `registry`/`config`, sem importar `SQLiteJobQueue`
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — `FakeExtractor`/`MultiChunkExtractor` e `FakeSpeaker`/`CountingSpeaker` em todos os testes; nenhum teste toca rede
- [x] Type hints e docstring de uma linha em toda função pública — `requeue_orphaned() -> list[Job]`, `count_text_chunks(text, max_chars) -> int`, `skip_sequences: set[int] | None`, `_resume_inconsistency(...) -> str | None`
- [x] `PROJECT_STATE.md` atualizado (seções 2, 3 — decisões #15 e #16 —, 4, 5 e 6)
- [x] Relatório criado em `docs/report/OS-022-report.md`
- [x] PR aberto contra o branch principal, título `[OS-022] Retomar processamento interrompido` — **ressalva:** aberto contra `os/021-entrega-incremental-audio` (PR empilhado), não contra `main`, porque a OS-022 depende da OS-021 e o PR #18 dela ainda está aberto. Depois do merge do #18, o base deste PR deve ser trocado para `main` (o GitHub faz isso automaticamente ao mergear o PR de baixo)

### DoD específico da OS (`docs/os/OS-022-retomar-processamento.md` seção 4)

- [x] `JobQueue` (ABC) tem um método novo pra resetar `Job`s órfãos de `running` para `queued`, documentado em `ARQUITETURA.md` seção 4.3 — `requeue_orphaned() -> list[Job]`
- [x] `SQLiteJobQueue` implementa esse método — `SELECT` + `UPDATE` dentro da mesma transação `BEGIN IMMEDIATE` já usada por `claim_next()`
- [x] `run_worker()` chama esse método uma vez ao iniciar, antes do loop de polling — cada órfão encontrado é logado com `job.id` e `book_id`
- [x] `process_job()` pula a síntese de `sequence`s já persistidas pro `book_id`, sintetiza só o que falta
- [x] Existe uma checagem de consistência explícita (não silenciosa) entre o que foi recalculado e o que já estava persistido, com um caminho seguro definido pra quando não bater — `_resume_inconsistency()`, ver seção 5 abaixo (decisão #16)
- [x] Teste automatizado: simula um `Job` órfão com alguns `AudioChunk`s já persistidos, chama o sweep de retomada, confirma que só os chunks faltantes são sintetizados — `test_worker_process_job_skips_already_persisted_chunks` (o `CountingSpeaker` registra 1 chamada, com o texto do terceiro chunk)
- [x] Teste automatizado: simula uma inconsistência e confirma que o caminho seguro definido é seguido — `test_worker_process_job_handles_chunk_count_inconsistency_safely`
- [x] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_sqlite_queue_requeue_orphaned_resets_running_jobs_to_queued` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_requeue_orphaned_ignores_queued_and_done_jobs` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_requeue_orphaned_returns_empty_list_when_no_running_jobs` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_worker_run_worker_requeues_orphaned_jobs_on_startup` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_skips_already_persisted_chunks` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_handles_chunk_count_inconsistency_safely` | `tests/unit/test_worker.py` | Sim |
| `test_synthesize_text_skips_sequences_already_synthesized` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_count_text_chunks_matches_number_of_synthesized_chunks` | `tests/integration/test_pipeline_end_to_end.py` | Sim |

Os três últimos testes exigidos pela seção 5 da OS estão cobertos com os nomes acima; os dois de `test_pipeline_end_to_end.py` são adicionais (cobrem os dois pontos novos de `core/pipeline.py` descritos na seção 5 deste relatório).

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim — `2c10373`, com as 8 falhas pelos motivos certos (métodos/parâmetros ainda inexistentes e comportamento ainda não implementado), antes de `5d4abe7`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação), nos três arquivos tocados:

```
$ venv/bin/python -m pytest tests/unit/queues/test_sqlite_queue.py tests/unit/test_worker.py tests/integration/test_pipeline_end_to_end.py -q
8 failed, 25 passed in 4.77s
```

Motivos das falhas (todos "o código ainda não existe", nenhum erro de sintaxe no teste):

```
E       AttributeError: 'SQLiteJobQueue' object has no attribute 'requeue_orphaned'
E       AttributeError: module 'core.pipeline' has no attribute 'count_text_chunks'
E       TypeError: synthesize_text() got an unexpected keyword argument 'skip_sequences'
E       AssertionError: assert 'running' == 'done'            (run_worker não retomava o órfão)
E       AssertionError: assert ['AAAA...', 'BBBB...', 'CCCC...'] == []   (chunks já persistidos eram re-sintetizados)
```

Suíte completa após a implementação (Green):

```
$ venv/bin/python -m pytest -q
107 passed, 1 warning in 6.90s
```

`black`: reformatou `worker/tasks.py`, `tests/unit/test_worker.py` e `tests/unit/queues/test_sqlite_queue.py` (3 arquivos). `ruff check` em `core/pipeline.py`, `worker/tasks.py`, `plugins/queues/` e `tests/`: `All checks passed!`.

## 5. Decisões de implementação documentadas

**(a) Caminho seguro escolhido para inconsistência na retomada (decisão #16).** A OS deixava a escolha entre descartar os chunks já persistidos e recomeçar do zero, ou marcar `Book.status = "error"` pedindo reenvio manual. **Escolhido: marcar `error`, sem apagar nada.** Motivos: apagar áudio já gerado é destrutivo e irreversível (e `storage/audio_store.py` não tem função de remoção — criar uma ampliaria o escopo da OS para um arquivo fora dele); e uma inconsistência aqui significa que o PDF ou a lógica de limpeza/chunking mudou entre as duas tentativas, o que merece atenção humana em vez de reprocessamento silencioso. A mensagem gravada em `Book.error_message` (visível em `GET /books/{id}/status` desde a OS-018), logada em `logger.error` e repetida em `Job.error_message` diz exatamente isso e pede o reenvio. Registrado em `RUNBOOK.md` seção 8.

**Critério de detecção:** existe `AudioChunk` persistido com `sequence >= ` número de chunks produzido pelo texto re-extraído. É a inconsistência detectável descrita pela OS (chunks recalculados a menos que os já persistidos). Um chunk de mesmo índice cujo *conteúdo* mudou sem mudar a contagem não é detectável sem guardar um hash do texto de cada chunk — isso não está no escopo desta OS e não foi implementado.

**(b) Limitação de um worker só, explicitada em código e documentação.** `run_worker()` trata *todo* `Job` em `running` como órfão. Sem heartbeat/lease não há como distinguir um worker vivo de um morto — a OS coloca isso fora de escopo e pede que a limitação seja documentada, não escondida: está em comentário no próprio `run_worker()`, na docstring do contrato em `plugins/queues/base.py` e em `ARQUITETURA.md`, na decisão #15 e na seção 6 do `PROJECT_STATE.md`, e no `RUNBOOK.md` seção 4.

**(c) Logging.** O projeto não tinha nenhuma chamada de log até aqui. A OS exige "logar claramente" a inconsistência; foi usado o `logging` da stdlib (`logger = logging.getLogger(__name__)` em `worker/tasks.py`), sem nenhuma configuração global de handler/level — o worker roda no terminal e a configuração padrão do Python já mostra `ERROR`. Um setup de logging de verdade (formato, nível configurável, arquivo) não estava no escopo e não foi feito. As mensagens de `INFO` (órfão devolvido à fila, retomada de N de M chunks) só aparecem se o operador configurar o nível — candidato a OS futura se incomodar.

## 6. Desvios do escopo original

**Um desvio, em `core/pipeline.py`** — arquivo não listado na seção 2 da OS. A OS pede que `process_job()` "pule a síntese" das `sequence`s já persistidas, mas quem itera os chunks e chama o `Speaker` é `pipeline.synthesize_text()`; e a checagem de consistência exige saber em quantos chunks o texto re-extraído seria dividido. Para isso, `core/pipeline.py` recebeu duas adições, ambas **aditivas e opcionais** (nenhum chamador ou teste existente mudou, mesmo padrão aprovado na OS-021 para o `on_chunk`):

- `synthesize_text(..., skip_sequences: set[int] | None = None)` — as sequences informadas não são sintetizadas nem aparecem na lista devolvida; sem o parâmetro, o comportamento é idêntico ao de antes.
- `count_text_chunks(text, max_chars=None) -> int` — conta os chunks sem sintetizar nada.

As alternativas seriam piores: reimplementar a divisão em chunks dentro de `worker/tasks.py` (duplicaria a lógica de `synthesize_text()` e faria o worker chamar o `Speaker` direto, furando o papel de `core/pipeline.py`), ou chamar `synthesize_text()` uma vez por chunk faltante (recarregaria o modelo do Kokoro a cada chunk). Como efeito colateral positivo, `synthesize_text()` agora só instancia o `Speaker` se houver algo pendente — retomar um livro cujos chunks já estão todos persistidos não carrega o modelo do Kokoro à toa.

Fora isso, `RUNBOOK.md` (seções 4 e 8) também foi atualizado, para que o comportamento novo de retomada e a mensagem de inconsistência não fiquem só na documentação de arquitetura. Nenhum outro arquivo fora do escopo foi tocado.

## 7. Dúvidas / bloqueios

Nenhuma decisão de arquitetura foi tomada fora do que a OS já autorizava explicitamente. Dois pontos ficam registrados para o dono do projeto:

1. **O desvio da seção 6 (`core/pipeline.py`)** — feito por necessidade técnica, seguindo o padrão de parâmetro opcional já aprovado na OS-021; se a preferência for manter `core/pipeline.py` intocado, isso precisa de outra abordagem e de uma OS nova.
2. **PR empilhado** — este PR tem como base `os/021-entrega-incremental-audio` (PR #18, ainda aberto), não `main`. Mergear o #18 primeiro; o base deste vira `main` automaticamente.

## 8. Link do PR

[a preencher]
