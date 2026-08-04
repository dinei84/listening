# OS-015 — GET /books (listagem de livros)

## 1. Objetivo

Adicionar o endpoint de listagem que ficou explicitamente fora de escopo desde a OS-010 e a OS-014 ("o player só sabe de um livro pelo id — de upload recém-feito ou digitado manualmente"). Esta OS é só o endpoint de backend; ligar isso na UI do player (trocar o campo manual de `book_id` por uma lista de livros) fica pra uma OS seguinte.

## 2. Escopo

**Dentro do escopo:**
- `storage/db.py`: uma função `list_books()` que devolve todos os livros persistidos, ordenados por `created_at` decrescente (mais recente primeiro).
- `api/routes_books.py`: `GET /books` devolve a lista (`id`, `title`, `status`, `created_at` de cada livro). Lista vazia (nenhum livro ainda) devolve `[]`, não erro.
- Sem paginação — para o volume de uso de um projeto pessoal, devolver tudo de uma vez é suficiente. Se isso um dia virar problema real de volume, resolver então.

**Fora de escopo:**
- Qualquer mudança em `player/` (UI) para consumir esse endpoint — próxima OS, se fizer sentido.
- Filtros, busca, ordenação configurável, paginação.
- Qualquer mudança nos outros endpoints já existentes (`POST /books`, `GET /books/{id}/status`, `GET /books/{id}/audio`, `GET /books/{id}/audio/{sequence}`).

## 3. Contratos envolvidos

Nenhum contrato de plugin muda. Usa o modelo `Book` já existente (`core/models.py`, OS-002).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `storage/db.py` tem `list_books()` que devolve todos os livros, ordenados por `created_at` decrescente
- [ ] `GET /books` devolve a lista de livros com `id`, `title`, `status`, `created_at`
- [ ] Sem nenhum livro cadastrado, `GET /books` devolve `[]`, não erro
- [ ] Testes usam banco temporário (`tmp_path`, mesmo padrão desde a OS-010) — nenhum lixo no repositório
- [ ] Nenhuma chamada de rede ou API paga

## 5. Testes exigidos (mínimo)

- `test_list_books_returns_empty_list_when_no_books`
- `test_list_books_returns_books_ordered_by_created_at_desc`
- `test_get_books_endpoint_returns_list_of_books`
- `test_get_books_endpoint_returns_empty_list_when_no_books`

Local sugerido: `tests/unit/test_db.py` (adicionar casos) e `tests/integration/test_api_books.py` (adicionar casos).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-015-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
