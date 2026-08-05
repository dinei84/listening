# OS-026 — Nome amigável em vez de UUID na UI

## 1. Objetivo

Achado em uso real: o player mostra `Livro: <uuid>` no cabeçalho, e o `localStorage` guarda só o `book_id` — ao reabrir um livro pelo campo manual ou ao voltar numa sessão salva, não há nenhum jeito visual de saber qual livro é aquele sem decorar o UUID. Esta OS troca a exibição pelo título do livro (`Book.title`), mantendo o `book_id` só como identificador técnico interno.

## 2. Escopo

**Dentro do escopo:**
- `api/routes_books.py::get_book_status`: resposta ganha `title` (de `book.title`) — hoje só devolve `id`/`status`/`error_message`.
- `player/app.js`:
  - `openBook()` usa o `title` devolvido por `fetchStatus()` (ou recebido diretamente de `renderBooksList` quando a abertura vem de um clique na lista, evitando esperar o primeiro poll) pra preencher `playerTitle.textContent`, em vez do `bookId` cru.
  - `saveState()`/`loadSavedState()` (`localStorage`) passam a guardar também o `title`, pra mostrar sem precisar de uma chamada de rede extra ao restaurar a sessão salva.
  - Campo "Abrir livro existente" continua aceitando o `book_id` (é a forma de digitar manualmente — não dá pra digitar um título ambíguo), mas o resultado exibido no player usa o título assim que carregado.

**Fora do escopo:**
- Editar/renomear o título de um livro depois do upload.
- Mudar o formato do `book_id` — continua UUID internamente, isso é só sobre exibição.

## 3. Contratos envolvidos

Nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda. Mudança aditiva na resposta de `GET /books/{id}/status` (campo novo, nenhum campo existente removido ou renomeado — chamadores atuais não quebram).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `GET /books/{id}/status` devolve `title` junto com `id`/`status`
- [ ] Cabeçalho do player mostra o título do livro, não o UUID
- [ ] Reabrir uma sessão salva (`localStorage`) via refresh da página mostra o título, não o UUID, mesmo antes do primeiro poll de status completar (se o título já estava salvo)
- [ ] Campo "Abrir livro existente" continua funcional exatamente como hoje (aceita `book_id`)

## 5. Testes exigidos (mínimo)

- `test_get_books_status_returns_title`

Local sugerido: `tests/integration/test_api_books.py`. Verificação da UI é manual em navegador, mesmo padrão já usado nas OS-014/016 — registrar no relatório.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-026-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
