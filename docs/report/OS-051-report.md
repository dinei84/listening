# OS-051 — Relatório de entrega

**Data:** 11/08/2026
**Branch:** `os/051-sinal-de-worker-ativo`
**Commit(s) relevante(s):** `f4dcffc` (Red), `f7c39cf` (Green)

## 1. Resumo do que foi feito

O worker passou a registrar batimento numa tabela própria, a API a expô-lo em `GET /worker`, e o player a avisar quando há livro esperando e nenhum worker de pé. O estado que antes era invisível — "na fila, ninguém escutando" — agora é dito na tela.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `f4dcffc` com 10 falhas antes de `f7c39cf`
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou (321 → 331)
- [x] Contratos de `ARQUITETURA.md` respeitados — nenhum contrato de plugin tocado
- [x] Nenhuma chamada a API paga nos testes
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-051-report.md`
- [x] PR aberto — https://github.com/dinei84/listening/pull/47

Específico (seção 6 da OS):

- [x] Batimento ao iniciar, antes do primeiro job — `test_worker_records_heartbeat_on_startup`
- [x] Batimento a cada ciclo do laço de polling
- [x] Batimento **durante a síntese** — `test_worker_records_heartbeat_while_synthesizing`
- [x] `db` expõe último batimento e se está no limiar — `last_worker_heartbeat`, `worker_is_alive`
- [x] Batimento antigo é worker parado — `test_heartbeat_older_than_threshold_reports_worker_stopped`
- [x] Banco sem batimento é worker parado, não erro — `test_heartbeat_absent_reports_worker_stopped`
- [x] API expõe o estado — `GET /worker`
- [x] Player avisa com livro esperando e sem worker — verificado no navegador real
- [x] Aviso não aparece com worker ativo — verificado no navegador real
- [x] `init_db()` cria a tabela em banco existente — `test_init_db_creates_heartbeat_table_on_existing_database`
- [x] Nenhum teste existente quebra

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_heartbeat_absent_reports_worker_stopped` | `tests/unit/test_db.py` | Sim |
| `test_heartbeat_recent_reports_worker_alive` | idem | Sim |
| `test_heartbeat_older_than_threshold_reports_worker_stopped` | idem | Sim |
| `test_heartbeat_keeps_a_single_row` | idem | Sim |
| `test_init_db_creates_heartbeat_table_on_existing_database` | idem | Sim |
| `test_worker_records_heartbeat_on_startup` | `tests/unit/test_worker.py` | Sim |
| `test_worker_records_heartbeat_while_synthesizing` | idem | Sim |
| `test_api_reports_worker_stopped_when_no_heartbeat` | `tests/integration/test_api_books.py` | Sim |
| `test_api_reports_worker_alive_after_heartbeat` | idem | Sim |
| `test_player_has_worker_warning_element` | `tests/integration/test_player.py` | Sim |

Commit "Red" antes do "Green"? [x] Sim.

## 4. Saída de comandos relevantes

Verificação manual em navegador real, com a API de pé e **sem worker**, reproduzindo o episódio que motivou a OS:

```json
{
  "aviso_existe": true,
  "aviso_visivel": true,
  "aviso_texto": "Nenhum worker ativo — os livros abaixo não vão processar. Suba o worker com: python -m worker.tasks",
  "livros": ["uploaded"],
  "worker": { "alive": false, "last_heartbeat_at": null }
}
```

Depois de um batimento, o aviso some:

```json
{
  "aviso_visivel": false,
  "worker": { "alive": true, "last_heartbeat_at": "2026-08-12T01:16:20.866266+00:00" }
}
```

Suíte: `331 passed`. `ruff check`: `All checks passed!`

## 5. Desvios do escopo original

**Uma correção fora do escopo declarado, que a OS revelou.** `run_worker` passou a chamar `db.init_db()`. O worker roda em processo separado do `uvicorn`, mas **nunca inicializava o banco** — só `api/main.py` fazia isso. Na prática o worker dependia de a API ter subido antes para as tabelas existirem.

Isso apareceu porque a tabela de heartbeat é a primeira que o worker precisa **antes** de tocar em qualquer livro: nos testes, `run_worker` quebrou com `no such table: worker_heartbeat`. Em produção o sintoma estava mascarado porque, na prática, a API sempre subia primeiro.

Foi corrigido em vez de contornado no teste: `init_db` é idempotente, e um processo que depende de tabelas deve garanti-las. Cabe na regra de ~3 arquivos fora do escopo do `AGENTS.md` seção 3 (é uma linha em um arquivo já no escopo).

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Três observações registradas:

**O limiar de 120s não foi validado com Speaker lento.** Foi escolhido para acomodar o chunk mais demorado, mas o único motor em produção é o Kokoro, que fecha um chunk em segundos. Se um dia entrar um Speaker remoto — ou o Chatterbox, medido a 7,6 h por livro — um único chunk pode passar de 120s e o worker apareceria como morto **enquanto trabalha**. A constante `WORKER_HEARTBEAT_TIMEOUT_SECONDS` existe para essa calibração.

**Detecção de `Job` órfão continua como estava.** A decisão #15 registra que `requeue_orphaned()` devolve à fila todo `Job` em `running` sem distinguir "worker morreu" de "outro worker está processando", justamente por não existir heartbeat. Esta OS **cria** o heartbeat que resolveria isso, mas usá-lo mexe no contrato `JobQueue` e é outra responsabilidade. Continuação natural, agora desbloqueada.

**O aviso é passivo.** Ele diz o que houve e qual comando resolve, mas não sobe o worker. Foi decisão de escopo: informar, não agir.

## 7. Link do PR

https://github.com/dinei84/listening/pull/47
