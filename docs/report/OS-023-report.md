# OS-023 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/023-deletar-livro
**Commit(s) relevante(s):** f80713a (test: Red), cbaf4e8 (feat: Green)

## 1. Resumo do que foi feito

`DELETE /books/{id}` remove o `Book`, todos os `AudioChunk`s (linhas do banco + diretório `storage/audio/{id}/`), todos os `Job`s do livro e o PDF enviado. 404 para `book_id` inexistente; 409 enquanto o livro está em `uploaded`/`extracting`/`processing`/`synthesizing`. Na UI, cada item de "Meus livros" ganhou um botão "Deletar" com `window.confirm`; deletar o livro aberto no player esconde `#player-section` e limpa o `localStorage`.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `f80713a` "Red" antes de `cbaf4e8` "Green")
- [x] Todos os testes da OS passam localmente — 120 pass, 0 fail
- [x] Nenhum teste existente quebrou (114 anteriores + 6 novos = 120)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `JobQueue` (seção 4.3) ganhou `delete_jobs_for_book()` como extensão aditiva, documentada antes de implementar; `Extractor`/`Speaker` inalterados
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — FakeExtractor/FakeSpeaker mockados
- [x] Type hints e docstring de uma linha em toda função pública nova (`delete_book`, `delete_chunks`, `delete_pdf`, `delete_jobs_for_book`, endpoint `delete_book`)
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4 e 5)
- [x] Relatório criado em `docs/report/OS-023-report.md`
- [x] PR aberto contra o branch principal, título `[OS-023] deletar livro`

### DoD específico da OS (`docs/os/OS-023-deletar-livro.md` seção 4)

- [x] `DELETE /books/{id}` remove o `Book`, todos os `AudioChunk`s (linhas do banco + arquivos `.wav`), todos os `Job`s do livro e o PDF enviado — `test_delete_book_removes_book_chunks_jobs_and_pdf`
- [x] 404 ao deletar um `book_id` inexistente — `test_delete_book_returns_404_for_unknown_book`
- [x] 409 ao tentar deletar um livro com status em `uploaded`/`extracting`/`processing`/`synthesizing` — `test_delete_book_returns_409_while_processing` (usa `uploaded`, pós-POST)
- [x] Deletar um livro `ready` ou `error` funciona sem erro — `test_delete_book_allowed_when_ready_or_error` (cobre os dois estados)
- [x] `GET /books` não lista mais o livro deletado — assert no final de `test_delete_book_allowed_when_ready_or_error`
- [x] `GET /books/{id}/status` devolve 404 para um livro deletado — assert no final de `test_delete_book_removes_book_chunks_jobs_and_pdf`
- [x] Botão "Deletar" na lista pede confirmação antes de chamar a API — `window.confirm` em `deleteBook()` no `player/app.js` (sem suíte de teste JS neste projeto; ver seção 5)
- [x] Deletar o livro atualmente aberto no player esconde a seção do player e limpa o `localStorage` — `stopPolling()`, esconde `#player-section`, `localStorage.removeItem(STORAGE_KEY)` (ver seção 5)

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_delete_book_removes_book_chunks_jobs_and_pdf` | `tests/integration/test_api_books.py` | Sim |
| `test_delete_book_returns_404_for_unknown_book` | `tests/integration/test_api_books.py` | Sim |
| `test_delete_book_returns_409_while_processing` | `tests/integration/test_api_books.py` | Sim |
| `test_delete_book_allowed_when_ready_or_error` | `tests/integration/test_api_books.py` | Sim |
| `test_sqlite_queue_delete_jobs_for_book_removes_only_that_books_jobs` | `tests/unit/queues/test_sqlite_queue.py` | Sim |
| `test_sqlite_queue_delete_jobs_for_book_is_noop_for_unknown_book` (extra) | `tests/unit/queues/test_sqlite_queue.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `f80713a` (6 falhas: 4× `405 Method Not Allowed` por rota `DELETE` inexistente, 2× `AttributeError: no attribute 'delete_jobs_for_book'`) antes de `cbaf4e8`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação):
```
6 failed, 25 passed, 1 warning in 5.26s
```
Falhas: `test_delete_book_removes_book_chunks_jobs_and_pdf`, `test_delete_book_returns_404_for_unknown_book`, `test_delete_book_returns_409_while_processing`, `test_delete_book_allowed_when_ready_or_error` (todas `405 Method Not Allowed` — rota `DELETE` não existia), `test_sqlite_queue_delete_jobs_for_book_*` (`AttributeError` — método não existia).

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
120 passed, 1 warning in 7.87s
```

`black --check`: reformatou `api/routes_books.py` (colapso de um `HTTPException` multilinha). `ruff check` em `api/`, `storage/`, `plugins/` e `tests/`: sem achados. `player/app.js` não passa pelo black (é JS; verificado por revisão de código).

## 5. Decisões de implementação e verificação da UI

**409 em vez de permitir sempre (decisão exigida pela OS para documentar):** deletar durante processamento ativo arriscaria remover um arquivo que o worker ainda está escrevendo — `audio_store.persist_chunks()` usa `shutil.move`, e remover o diretório de destino no meio corromperia o chunk atual e os seguintes — e também faria o worker chamar `update_book_status()` num `book_id` que não existe mais, jogando status num buraco. Os status bloqueados (`uploaded`/`extracting`/`processing`/`synthesizing`) são exatamente os em que o worker ainda pode estar ativo; `ready`/`error` garantem worker ocioso.

**PDF removido via `storage/uploads.py::delete_pdf()`** (não inline no endpoint) — por simetria com `pdf_path_for()` já existente, mantendo o conhecimento de caminhos no módulo dono.

**Ordem de limpeza no endpoint:** jobs → chunks → PDF → book. Apagar os artefatos antes da linha do `books`; se algo falhar no meio, o `Book` ainda existe e o usuário pode repetir a exclusão.

**Verificação da UI (botão Deletar):** este projeto não tem suíte de testes JS (decisão #12, player em JS puro, sem build step). As mudanças em `player/app.js` (`deleteBook()` com `window.confirm`, `stopPropagation` no clique do botão para não disparar `openBook`, limpeza do player quando o livro aberto é deletado) foram validadas por revisão de código e seguem o mesmo padrão das OS-014/016, cujos DoDs de UI foram verificados manualmente em navegador na revisão pós-entrega. **Pendente: verificação manual em navegador real** de: botão com confirmação, refresh da lista após deletar, e esconder/limpar player quando o livro aberto é deletado.

## 6. Desvios do escopo original

Nenhum. Antes de executar, o sync de governança pendente no working tree (`docs/os/OS-023..026` + `PROJECT_STATE.md`) foi commitado em `main` (commit `92f249c`), conforme decisão #6 do `HANDOFF.md` e padrão do commit `dc695c3` — decisão confirmada pelo dono do projeto.

## 7. Dúvidas / bloqueios

Nenhuma.

## 8. Link do PR

*A preencher após `git push` e `gh pr create`.*
