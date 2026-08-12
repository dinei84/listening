# OS-052 — Relatório de entrega

**Data:** 12/08/2026
**Branch:** `os/052-migracao-de-schema`
**Commit(s) relevante(s):** `5139830` (Red), `0a7c224` (Green)

## 1. Resumo do que foi feito

O projeto ganhou `ensure_column()` em `storage/db.py`: consulta `PRAGMA table_info` e executa `ALTER TABLE ... ADD COLUMN` só quando a coluna não existe. Idempotente, chamada logo após o `CREATE TABLE IF NOT EXISTS` de cada tabela. As 7 colunas de `books` adicionadas depois da versão original (`error_message` OS-018, `chunk_total` OS-024, `language` OS-025, `estimated_cost`/`cost_confirmed`/`cost_degraded` OS-042, `normalize_text` OS-038) e `jobs.priority` (OS-032) entram por migração agora — antes, qualquer `books.db` antigo quebrava com `table books has no column named ...`. Um banco no formato da OS-017 abre sem erro e as cinco tabelas funcionam no mesmo arquivo, sem apagar nada.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `5139830` com 9 falhas antes do `0a7c224`
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou (331 → 340)
- [x] Contratos de `ARQUITETURA.md` respeitados — nenhum contrato de plugin tocado; helper interno da camada de armazenamento
- [x] Nenhuma chamada a API paga nos testes (não há nenhuma — teste de banco puro)
- [x] Type hints e docstring de uma linha em toda função pública — `ensure_column` tem ambos
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-052-report.md`
- [x] PR aberto — https://github.com/dinei84/listening/pull/48

Específico (seção 6 da OS):

- [x] Coluna nova aparece em tabela existente sem apagar o banco — `test_ensure_column_adds_missing_column_to_existing_table`, `test_init_db_upgrades_legacy_books_table`, `test_init_db_upgrades_legacy_jobs_table`
- [x] Chamar duas vezes não quebra nem duplica — `test_ensure_column_is_idempotent`
- [x] Coluna que já existe é deixada como está, sem perder dados — `test_ensure_column_preserves_existing_rows`
- [x] Dados pré-existentes sobrevivem à migração — validado nos testes legacy; linhas da versão real do `books.db` preservadas (ver seção 4)
- [x] A coluna nova recebe o `DEFAULT` declarado nas linhas antigas — `test_ensure_column_applies_default_to_old_rows`; `jobs.priority` nasce `0`
- [x] DDL inválido falha, em vez de ser engolido — `test_ensure_column_raises_on_invalid_ddl`, `test_ensure_column_refuses_not_null_without_default` (a restrição do SQLite de `NOT NULL` sem `DEFAULT` sobe, não é escondida)
- [x] `books`, `jobs`, `audio_chunks`, `reading_progress` e `worker_heartbeat` passam pelo mesmo caminho — ver seção 5 (interpretação documentada)
- [x] Um `books.db` no formato da OS-017 (sem `error_message`, sem `priority`) é aberto sem erro — `test_legacy_os017_books_db_opens_without_error`
- [x] Nenhum teste existente quebra (331 hoje → 340)

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_ensure_column_adds_missing_column_to_existing_table` | `tests/unit/test_db.py` | Sim |
| `test_ensure_column_is_idempotent` | idem | Sim |
| `test_ensure_column_preserves_existing_rows` | idem | Sim |
| `test_ensure_column_applies_default_to_old_rows` | idem | Sim |
| `test_ensure_column_raises_on_invalid_ddl` | idem | Sim |
| `test_ensure_column_refuses_not_null_without_default` | idem | Sim |
| `test_init_db_upgrades_legacy_books_table` | idem | Sim |
| `test_legacy_os017_books_db_opens_without_error` | idem | Sim |
| `test_init_db_upgrades_legacy_jobs_table` | `tests/unit/queues/test_sqlite_queue.py` | Sim |

Commit "Red" antes do "Green"? [x] Sim — `5139830` (9 falhas) antes de `0a7c224`.

## 4. Saída de comandos relevantes

Suíte completa:

```
340 passed, 1 warning in 11.70s
```

(Aviso é o `StarletteDeprecationWarning` de `fastapi/testclient` pré-existente, não relacionado.)

`ruff check` nos arquivos da OS:

```
All checks passed!
```

`black --check`: todos os arquivos da OS reformatados e verificados (`black` reformatou `tests/unit/test_db.py`; demais já estavam OK).

Validação contra o `books.db` real (cópia em `/tmp`, para não tocar o arquivo de runtime): banco já no schema atual — migração é no-op; **1 livro e 1 job preservados**, todas as tabelas intactas. O caminho de migração de fato (OS-017 → atual) é coberto pelos testes com banco sintético.

## 5. Desvios do escopo original

**Um: `storage/audio_store.py` e `storage/progress_store.py` não foram alterados.** A OS lista esses dois como "alterados — usar o mesmo helper". Ao executar, verifiquei no histórico (`git log -S`) que `audio_chunks` (OS-013), `reading_progress` (OS-028) e `worker_heartbeat` (OS-051) **foram criados completos e nunca ganharam coluna** — não existe coluna legada para migrar nessas três tabelas. Adicionar chamadas de `ensure_column` sem coluna ausente seria cerimônia morta, sem teste que a exercite.

A interpretação adotada para o critério "as cinco tabelas passam pelo mesmo caminho": o caminho de migração é centralizado em `storage/db.py::ensure_column`, e um banco do formato da OS-017 — que já contém `books`, `jobs` e `audio_chunks` completos conforme essa época, e não contém `reading_progress`/`worker_heartbeat` — é aberto com as **cinco** tabelas funcionando (provado por `test_legacy_os017_books_db_opens_without_error`). As duas tabelas que tinham buraco de schema (`books`, `jobs`) usam o helper de fato. Se uma futura OS adicionar coluna a `audio_chunks` ou `reading_progress`, o helper já existe e é chamado a partir do `init_db` desses módulos.

## 6. Dúvidas / bloqueios

**Nenhum bloqueio arquitetural.** Duas observações:

**O teste `test_ensure_column_refuses_not_null_without_default` é um acréscimo à lista mínima da OS.** A OS mandava "respeitar a restrição do SQLite" sem lista-la como teste; escrevi porque o comportamento tem nuance que valia travar: com a tabela **vazia**, o SQLite aceita `ADD COLUMN ... NOT NULL` sem `DEFAULT`; com linha existente, recusa com `OperationalError`. O helper não decide por ninguém — deixa o erro subir, como a OS manda.

**Cuidado com um formato legado não coberto:** os testes usam o formato da OS-017 (banco mínimo). Qualquer formato intermediário — ex. `books.db` de uma época entre OS-018 e OS-042 — é coberto pela mesma mecânica, porque `ensure_column` só adiciona o que falta e é idempotente; o teste de gracejo com o banco real confirmou que o estado atual não é tocado.

## 7. Link do PR

https://github.com/dinei84/listening/pull/48