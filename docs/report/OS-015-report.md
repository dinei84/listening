# OS-015 — Relatório de entrega

**Data:** 2026-08-04
**Branch:** os/015-listagem-livros
**Commit(s) relevante(s):** ecb9d50 (testes, Red), f354a9c (implementação, Green)

## 1. Resumo do que foi feito

Adicionado `list_books()` em `storage/db.py` (todos os livros, ordenados por `created_at` decrescente) e o endpoint `GET /books` em `api/routes_books.py`, devolvendo `id`, `title`, `status`, `created_at` de cada livro (`[]` quando não há nenhum). Nenhuma mudança em `player/` ou nos demais endpoints.

## 2. Checklist de DoD

**Padrão (`AGENTS.md` seção 4):**
- [x] Testes escritos antes da implementação (commit `ecb9d50` com os 4 testes falhando existe antes de `f354a9c`)
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (82 passed, suíte completa)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (usa `Book` já existente, mesmo padrão de `storage/db.py` para as demais funções)
- [x] Nenhuma chamada real a API paga dentro dos testes — `list_books()`/`GET /books` só tocam SQLite local
- [x] Type hints e docstring de uma linha em `list_books()` e no handler `list_books` (rota)
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4 e 5)
- [x] Relatório criado em `docs/report/OS-015-report.md`
- [x] PR aberto (https://github.com/dinei84/listening/pull/13)

**Específico da OS (`docs/os/OS-015-listagem-livros.md` seção 4):**
- [x] `storage/db.py` tem `list_books()` que devolve todos os livros, ordenados por `created_at` decrescente
- [x] `GET /books` devolve a lista de livros com `id`, `title`, `status`, `created_at`
- [x] Sem nenhum livro cadastrado, `GET /books` devolve `[]`, não erro
- [x] Testes usam banco temporário (`tmp_path`) — nenhum lixo no repositório
- [x] Nenhuma chamada de rede ou API paga

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_list_books_returns_empty_list_when_no_books` | `tests/unit/test_db.py` | Sim |
| `test_list_books_returns_books_ordered_by_created_at_desc` | `tests/unit/test_db.py` | Sim |
| `test_get_books_endpoint_returns_list_of_books` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_endpoint_returns_empty_list_when_no_books` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim — `ecb9d50` (4 testes falhando, `AttributeError`/404) antes de `f354a9c` (implementação).

## 4. Saída de comandos relevantes

Rodada de confirmação Red (antes da implementação):

```
FAILED tests/unit/test_db.py::test_list_books_returns_empty_list_when_no_books
FAILED tests/unit/test_db.py::test_list_books_returns_books_ordered_by_created_at_desc
FAILED tests/integration/test_api_books.py::test_get_books_endpoint_returns_list_of_books
FAILED tests/integration/test_api_books.py::test_get_books_endpoint_returns_empty_list_when_no_books
4 failed, 12 deselected, 1 warning in 5.89s
```

Suíte completa após a implementação (Green):

```
======================== 82 passed, 1 warning in 5.92s =========================
```

`black --check --diff` e `ruff check` nos arquivos alterados: sem alterações necessárias, "All checks passed!".

## 5. Desvios do escopo original

Nenhum.

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

https://github.com/dinei84/listening/pull/13
