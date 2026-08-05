# OS-023 — Deletar livro

## 1. Objetivo

Achado em uso real: não existe nenhuma forma de remover um livro (upload de teste, duplicado, ou processado com erro) — nem endpoint na API nem botão na UI. Esta OS adiciona `DELETE /books/{id}`, limpando todo o rastro do livro (banco, áudio, PDF), e um botão "Deletar" na lista "Meus livros".

## 2. Escopo

**Dentro do escopo:**
- `api/routes_books.py`: `DELETE /books/{book_id}`. 404 se o livro não existir. **409 se `Book.status` estiver em `{"uploaded", "extracting", "processing", "synthesizing"}`** (processamento em andamento) — evita apagar arquivo/linha que o worker ainda está escrevendo. Livros em `ready` ou `error` podem ser deletados a qualquer momento. Ver seção 3 para o porquê dessa escolha.
- `storage/db.py`: `delete_book(book_id, db_path=None) -> None` — remove a linha de `books`.
- `storage/audio_store.py`: `delete_chunks(book_id, db_path=None) -> None` — remove as linhas de `audio_chunks` **e** o diretório `storage/audio/{book_id}/` do disco (`shutil.rmtree`, ignorar se não existir).
- Remoção do PDF em `uploads/{book_id}.pdf` (`Path.unlink(missing_ok=True)`, via `storage/uploads.py` ou diretamente no endpoint — decisão de implementação).
- `plugins/queues/base.py` (`JobQueue`, ABC): método novo `delete_jobs_for_book(book_id: str) -> None` — extensão aditiva do contrato, mesmo padrão já usado na OS-022 com `requeue_orphaned()`. Implementar em `plugins/queues/sqlite_queue.py`. Atualizar `ARQUITETURA.md` seção 4.3 com a assinatura nova.
- `player/index.html` + `player/app.js`: botão "Deletar" em cada item de `#books-list`, com confirmação (`window.confirm`) antes de chamar `DELETE /books/{id}`. Após sucesso: remove o livro da lista (ou chama `refreshBooksList()`); se o livro deletado for o `currentBookId` aberto no player, esconde `#player-section` e limpa o estado salvo no `localStorage`.

**Fora do escopo:**
- Deletar múltiplos livros de uma vez (bulk delete).
- Soft delete / lixeira / desfazer exclusão.
- Cancelar um `Job` em andamento — o 409 só **bloqueia** a exclusão enquanto o livro está ativo, não tenta interromper o worker.

## 3. Contratos envolvidos

`JobQueue` (`ARQUITETURA.md` seção 4.3) ganha `delete_jobs_for_book()` — extensão aditiva, mesmo processo já usado na OS-022 (`requeue_orphaned()`): documentar antes de implementar, nada existente muda de comportamento.

Decisão de implementação a documentar no relatório: por que bloquear delete durante processamento ativo (409) em vez de permitir sempre — evita que um arquivo sendo escrito pelo worker (`audio_store.persist_chunks()`, que usa `shutil.move`) seja removido no meio, e evita o worker tentar `update_book_status()` num `book_id` que não existe mais.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `DELETE /books/{id}` remove o `Book`, todos os `AudioChunk`s (linhas do banco + arquivos `.wav`), todos os `Job`s do livro e o PDF enviado
- [ ] 404 ao deletar um `book_id` inexistente
- [ ] 409 ao tentar deletar um livro com status em `uploaded`/`extracting`/`processing`/`synthesizing`
- [ ] Deletar um livro `ready` ou `error` funciona sem erro
- [ ] `GET /books` não lista mais o livro deletado
- [ ] `GET /books/{id}/status` devolve 404 para um livro deletado
- [ ] Botão "Deletar" na lista pede confirmação antes de chamar a API
- [ ] Deletar o livro atualmente aberto no player esconde a seção do player e limpa o `localStorage`

## 5. Testes exigidos (mínimo)

- `test_delete_book_removes_book_chunks_jobs_and_pdf`
- `test_delete_book_returns_404_for_unknown_book`
- `test_delete_book_returns_409_while_processing`
- `test_delete_book_allowed_when_ready_or_error`
- `test_sqlite_queue_delete_jobs_for_book_removes_only_that_books_jobs`

Local sugerido: `tests/integration/test_api_books.py`, `tests/unit/queues/test_sqlite_queue.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-023-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
