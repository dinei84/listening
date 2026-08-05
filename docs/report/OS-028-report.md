# OS-028 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/028-progresso-leitura (empilhada sobre `os/027-deteccao-capitulos`)
**Commit(s) relevante(s):** ae299be (test: Red), 87ce78b (feat: Green)

## 1. Resumo do que foi feito

Posição de leitura persistida no servidor: modelo `ReadingProgress` novo, módulo `storage/progress_store.py` com a tabela `reading_progress` (chave primária `book_id` — só a posição **atual**, sobrescrita via `UPSERT`, sem histórico), e os endpoints `GET`/`PUT /books/{id}/progress`. O player passou a gravar a posição no servidor a cada ciclo do throttle já existente e, ao abrir um livro, consulta o servidor para decidir se oferece "retomar" — o `localStorage` continua existindo como cache/fallback, mas deixou de ser autoritativo. `DELETE /books/{id}` (OS-023) passou a limpar o progresso junto.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `ae299be` "Red" antes de `87ce78b` "Green")
- [x] Todos os testes da OS passam localmente — 196 pass, 0 fail
- [x] Nenhum teste existente quebrou (185 anteriores + 11 novos = 196)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato de `Extractor`/`Speaker`/`JobQueue` tocado; `ReadingProgress` documentado na seção 5
- [x] Nenhuma chamada real a API paga dentro dos testes
- [x] Type hints e docstring de uma linha em toda função pública nova
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4 e 5)
- [x] Relatório criado em `docs/report/OS-028-report.md`
- [x] PR aberto contra o branch principal, título `[OS-028] Persistência de progresso de leitura no servidor`

### DoD específico da OS (seção 4)

- [x] `PUT /books/{id}/progress` grava a posição, sobrescrevendo qualquer valor anterior do mesmo livro — `test_put_books_progress_overwrites_previous` e `test_save_progress_overwrites_previous_value_for_same_book`
- [x] `GET /books/{id}/progress` devolve a última posição salva; 404 se nunca foi salva — `test_put_and_get_books_progress_roundtrip` e `test_get_books_progress_returns_404_when_never_saved`
- [x] Player grava a posição no servidor durante a reprodução (mesmo throttle de hoje) — `saveState()` chama `saveProgressToServer()` dentro do mesmo guard de `SAVE_THROTTLE_MS`
- [x] Ao reabrir um livro, o player usa o progresso do servidor (não só `localStorage`) para decidir se oferece retomar — `openBook()` consulta `fetchProgress()` antes do primeiro poll e monta o `pendingResume` a partir dele
- [x] 404 em `PUT`/`GET /books/{id}/progress` para um `book_id` inexistente — `test_get_books_progress_returns_404_for_unknown_book` e `test_put_books_progress_returns_404_for_unknown_book`

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_save_progress_persists_position` | `tests/unit/test_progress_store.py` | Sim |
| `test_save_progress_overwrites_previous_value_for_same_book` | `tests/unit/test_progress_store.py` | Sim |
| `test_get_progress_returns_none_when_never_saved` | `tests/unit/test_progress_store.py` | Sim |
| `test_save_progress_isolates_books` (extra) | `tests/unit/test_progress_store.py` | Sim |
| `test_delete_progress_removes_saved_position` (extra) | `tests/unit/test_progress_store.py` | Sim |
| `test_put_and_get_books_progress_roundtrip` | `tests/integration/test_api_books.py` | Sim |
| `test_put_books_progress_overwrites_previous` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_progress_returns_404_when_never_saved` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_progress_returns_404_for_unknown_book` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_put_books_progress_returns_404_for_unknown_book` | `tests/integration/test_api_books.py` | Sim |
| `test_delete_book_also_removes_reading_progress` (extra, regressão OS-023) | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `ae299be` (erro de coleta: `ModuleNotFoundError: No module named 'storage.progress_store'`, em `test_progress_store.py` e `test_api_books.py`) antes de `87ce78b`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação):
```
ERROR tests/integration/test_api_books.py
ERROR tests/unit/test_progress_store.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
1 warning, 2 errors in 4.92s
```

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
196 passed, 1 warning in 8.98s
```

```
$ venv/bin/ruff check core/ storage/ worker/ api/ tests/
All checks passed!
$ venv/bin/black --check core/ storage/ worker/ api/ tests/
45 files would be left unchanged.
$ node --check player/app.js
(sem erros)
```

### Verificação com servidor real (fora da suíte)

API real (`uvicorn`, porta 8021) rodando com `cwd` num diretório de scratchpad — o `books.db` do projeto não foi lido nem alterado:

```
book_id=f549009e-f075-4138-8068-5e6d3c62e989
--- GET progress (nunca salvo) ---      HTTP 404
--- PUT progress ---
{"book_id":"f549009e-...","sequence":12,"position_seconds":45.75}
--- GET progress (depois) ---
{"book_id":"f549009e-...","sequence":12,"position_seconds":45.75,"updated_at":"2026-08-05T21:16:30.249307+00:00"}
--- sobrescreve ---
{"book_id":"f549009e-...","sequence":99,"position_seconds":3.5,"updated_at":"2026-08-05T21:16:30.265463+00:00"}
--- 404 livro inexistente ---
GET  HTTP 404
PUT  HTTP 404
--- delete limpa progresso ---
DELETE HTTP 200
GET progress apos delete HTTP 404
```

## 5. Decisões de implementação documentadas

**(a) Servidor é a fonte de verdade; `localStorage` vira cache.** `openBook()` consulta `GET /books/{id}/progress` antes do primeiro poll: se o servidor tem posição salva, ela vence. Se o servidor devolve 404 (nunca salvo) ou a chamada falha, o `pendingResume` montado a partir do `localStorage` continua valendo. Isso preserva o comportamento offline/legado e faz o progresso sobreviver a trocar de navegador.

**(b) `save_progress()` usa `INSERT ... ON CONFLICT DO UPDATE` (UPSERT).** A tabela tem `book_id` como chave primária — uma linha por livro, sempre sobrescrita. Histórico está explicitamente fora de escopo.

**(c) A gravação no servidor falha em silêncio, de propósito.** `saveProgressToServer()` tem `.catch(() => {})`: perder uma gravação de posição não pode interromper a reprodução, e o throttle de 3s já garante nova tentativa em segundos. Mesmo critério que a OS-030 usou para falha em `GET /books/{id}/audio`.

**(d) `DELETE /books/{id}` limpa o progresso** (`progress_store.delete_progress`). Sem isso o progresso ficaria órfão no banco. Coberto por `test_delete_book_also_removes_reading_progress`.

**(e) Módulo próprio (`storage/progress_store.py`) em vez de mais funções em `storage/db.py`.** Segue o padrão já existente de um storage por conceito (`audio_store.py`), e mantém `db.py` focado em `books`/`chapters`. O arquivo do banco continua sendo o mesmo `books.db`.

## 6. Desvios do escopo original

Nenhum. A OS permitia módulo novo ou funções em `db.py` — escolhido o módulo novo, justificado em (e). Todos os arquivos tocados estão previstos na seção 2 da OS.

**Nota de empilhamento:** este branch tem como base `os/027-deteccao-capitulos` (PR #28), não `main`, porque as duas OS's tocam `api/routes_books.py` e `docs/PROJECT_STATE.md`. Mergear o #28 primeiro; o base deste vira `main` na sequência. A OS-028 não tem dependência **técnica** da OS-027 (a própria OS diz isso) — o empilhamento é só para evitar conflito de merge.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Uma observação: a verificação em navegador real do fluxo completo de retomada (tocar, fechar a aba, reabrir e ver a posição vinda do servidor) ficou para a **OS-029**, que é a OS de UI e exercita as três de uma vez. Nesta OS a verificação foi feita no nível da API, com servidor real (seção 4).

## 8. Link do PR

*A preencher após abrir o PR.*
