# OS-052 — Migração de schema no SQLite

## 1. Objetivo

Permitir que uma coluna nova apareça num banco já existente, sem apagar o `books.db`. Hoje isso é impossível, e a consequência já apareceu quatro vezes.

## 2. Motivação: uma dívida que já mordeu quatro vezes

O `PROJECT_STATE.md` registra desde 04/08/2026:

> **não existe migração de schema no SQLite.** Só `CREATE TABLE IF NOT EXISTS` — isso cria a tabela se ela não existe, mas **nunca adiciona coluna nova numa tabela que já existe.**

O padrão se repetiu:

| OS | Coluna adicionada | Erro no banco antigo |
|---|---|---|
| OS-018 | `books.error_message` | `table books has no column named error_message` |
| OS-032 | `jobs.priority` | `table jobs has no column named priority` |
| OS-042 | `books.estimated_cost` e mais duas | idem |
| OS-051 | *(evitada)* | usou tabela nova de propósito |

A saída documentada no `RUNBOOK.md` é **apagar o `books.db`** — o que descarta todos os livros já processados. A OS-051 escapou porque heartbeat cabia numa tabela nova; a escolha de voz (OS-053) precisa de coluna, e seria a quinta ocorrência.

Esta OS existe para que seja a última.

## 3. Escopo

Alterados:

- `storage/db.py` — helper de migração e uso nas tabelas próprias.
- `plugins/queues/sqlite_queue.py`, `storage/audio_store.py`, `storage/progress_store.py` — usar o mesmo helper.
- Testes correspondentes.

Fora de escopo:

- **Nenhuma coluna nova é adicionada nesta OS.** Ela entrega só a capacidade; quem usa é a OS-053.
- **Framework de migração versionada** (Alembic e afins). Seria uma segunda toolchain para um problema de dez linhas, contrariando as decisões #12 e #13, que já recusaram dependência pesada por ganho marginal.
- **Remover ou renomear coluna.** O SQLite só suporta bem `ADD COLUMN`; remoção exige recriar a tabela. Fora de escopo por não haver caso de uso.
- **Migração de dados** (preencher a coluna nova com valor derivado). `DEFAULT` cobre o que precisamos.

## 4. Contratos envolvidos

Nenhum contrato de interface alterado. O helper é interno da camada de armazenamento.

`JobQueue` não muda: `sqlite_queue.py` é uma implementação, e passar a usar o helper é detalhe interno dela.

## 5. Desenho proposto

Uma função em `storage/db.py`:

```python
def ensure_column(conn, table: str, column: str, ddl: str) -> None
```

Consulta `PRAGMA table_info(table)`; se a coluna não estiver lá, executa `ALTER TABLE ... ADD COLUMN`. Idempotente, chamada logo após o `CREATE TABLE IF NOT EXISTS` correspondente.

**Por que `PRAGMA` e não `try/except`:** capturar `OperationalError` funcionaria, mas engoliria também erros de digitação no DDL — o mesmo tipo de falha silenciosa que o `perth` nos deu ao converter `ImportError` em `None`. A consulta explícita falha alto quando o DDL está errado.

**Restrição do SQLite a respeitar:** `ADD COLUMN` recusa `NOT NULL` sem `DEFAULT`. O helper não pode disfarçar isso — deve deixar o erro subir, para o autor da coluna descobrir na hora e não em produção.

## 6. Critérios de aceite

- [ ] Coluna nova aparece em tabela existente sem apagar o banco
- [ ] Chamar duas vezes não quebra nem duplica (idempotente)
- [ ] Coluna que já existe é deixada como está, sem perder dados
- [ ] Dados pré-existentes sobrevivem à migração
- [ ] A coluna nova recebe o `DEFAULT` declarado nas linhas antigas
- [ ] DDL inválido **falha**, em vez de ser engolido
- [ ] `books`, `jobs`, `audio_chunks`, `reading_progress` e `worker_heartbeat` passam pelo mesmo caminho
- [ ] Um `books.db` no formato da OS-017 (sem `error_message`, sem `priority`) é aberto sem erro depois desta OS
- [ ] Nenhum teste existente quebra (331 hoje)

## 7. Testes exigidos (mínimo)

- `test_ensure_column_adds_missing_column_to_existing_table`
- `test_ensure_column_is_idempotent`
- `test_ensure_column_preserves_existing_rows`
- `test_ensure_column_applies_default_to_old_rows`
- `test_ensure_column_raises_on_invalid_ddl`
- `test_init_db_upgrades_legacy_books_table`
- `test_init_db_upgrades_legacy_jobs_table`

## 8. Relatório

Ver `docs/report/OS-052-report.md`.
