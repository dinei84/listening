# OS-024 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/024-progress-bar-sintese
**Commit(s) relevante(s):** 2e63ecc (test: Red), 41e52eb (feat: Green)

## 1. Resumo do que foi feito

`Book` ganhou `chunk_total` (coluna `chunk_total INTEGER` em `books`, nova função `storage/db.py::set_book_chunk_total()`), e `worker/tasks.py::process_job()` grava o total logo após calcular `count_text_chunks()`, antes de marcar `synthesizing`. `GET /books/{id}/status` agora devolve `chunks_done` (`len(list_chunks(book_id))`, tempo real) e `chunks_total` (pode ser `null`). O player trocou o texto cru de status por uma barra `<progress>` durante a síntese, com fallback pro texto quando `chunks_total` é `null`.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `2e63ecc` "Red" antes de `41e52eb` "Green")
- [x] Todos os testes da OS passam localmente — 123 pass, 0 fail
- [x] Nenhum teste existente quebrou (120 anteriores + 3 novos = 123)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda (seção 3 da OS); `Book` (seção 5) ganhou `chunk_total: int | None = None`, documentado antes de implementar
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — FakeExtractor/FakeSpeaker mockados
- [x] Type hints e docstring de uma linha em toda função pública nova (`set_book_chunk_total`)
- [x] `PROJECT_STATE.md` atualizado (seções 2, 3/ADL, 4 e 5)
- [x] Relatório criado em `docs/report/OS-024-report.md`
- [x] PR aberto contra o branch principal, título `[OS-024] progress bar real de síntese`

### DoD específico da OS (`docs/os/OS-024-progress-bar-sintese.md` seção 4)

- [x] `Book.chunk_total` é `None` até a síntese começar; passa a ter o total real assim que `process_job()` calcula `count_text_chunks()` — `test_worker_process_job_sets_book_chunk_total_before_synthesizing` (grava no banco antes de `synthesizing`, e `chunk_total_at_call == [3, 3, 3]` prova que o total já está visível durante toda a síntese) + `test_get_books_status_chunks_total_is_none_before_synthesis_starts`
- [x] `GET /books/{id}/status` devolve `chunks_done` e `chunks_total` (`chunks_total` pode ser `null`) — `test_get_books_status_returns_chunks_done_and_chunks_total` e `test_get_books_status_chunks_total_is_none_before_synthesis_starts`
- [x] `chunks_done` sempre reflete `len(list_chunks(book_id))` em tempo real, inclusive com o livro ainda `synthesizing` — o endpoint calcula `len(audio_store.list_chunks(book_id))` a cada chamada, sem cache; a mecânica de persistência incremental que alimenta essa contagem já é testada pela OS-021 (`test_worker_process_job_persists_chunks_incrementally`, que vê os chunks aparecendo no banco com o livro `synthesizing`)
- [x] Player mostra uma barra de progresso (`<progress>`) durante a síntese, com fallback pro texto de status quando `chunks_total` é `null` — `renderSynthesisProgress()` em `player/app.js` + elemento `<progress id="synthesis-progress">` em `player/index.html` (sem suíte de teste JS neste projeto; ver seção 5)
- [x] `RUNBOOK.md` avisa sobre a coluna nova exigindo apagar `books.db` local (mesmo padrão já usado pela OS-018)

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_worker_process_job_sets_book_chunk_total_before_synthesizing` | `tests/unit/test_worker.py` | Sim |
| `test_get_books_status_returns_chunks_done_and_chunks_total` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_status_chunks_total_is_none_before_synthesis_starts` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `2e63ecc` (3 falhas: 1× `AttributeError: 'Book' object has no attribute 'chunk_total'`, 2× `KeyError` para `chunks_done`/`chunks_total`) antes de `41e52eb`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação):
```
3 failed, 1 warning in 4.91s
```
Falhas: `test_worker_process_job_sets_book_chunk_total_before_synthesizing` (`AttributeError` — `Book` não tinha `chunk_total`), `test_get_books_status_returns_chunks_done_and_chunks_total` e `test_get_books_status_chunks_total_is_none_before_synthesis_starts` (`KeyError` — response do endpoint sem `chunks_done`/`chunks_total`).

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
123 passed, 1 warning in 7.82s
```

```
$ venv/bin/black --check core/ storage/ worker/ api/
All done! ✨ 🍰 ✨
15 files would be left unchanged.

$ venv/bin/ruff check core/ storage/ worker/ api/ tests/
All checks passed!
```

`player/app.js` não passa pelo black (é JS; verificado por revisão de código).

## 5. Decisões de implementação e verificação da UI

**Total gravado antes de `synthesizing`, reaproveitando o `chunk_count` da OS-022:** `process_job()` já calculava `count_text_chunks()` para a checagem de consistência da retomada — `set_book_chunk_total(job.book_id, chunk_count)` é chamado no mesmo fluxo, antes de `db.update_book_status(job.book_id, "synthesizing")`. Assim o total nunca fica "perdido" em livro interrompido: quem retoma já tem o total no banco.

**Sem endpoint novo — `chunks_done`/`chunks_total` entram no response existente de `GET /books/{id}/status`** (decisão #18 no ADL). O player já faz polling nesse endpoint; ampliar o response evita um endpoint/request extra por poll e mantém um único caminho de status.

**Fallback de UI:** quando `chunks_total` é `null` (livro ainda sem síntese iniciada), o `<progress>` fica `hidden` e `#player-status` mantém o texto cru (`Status: ...`), como antes. Durante a síntese, a barra mostra `chunks_done`/`chunks_total` (`max`/`value`), com `Math.min` para nunca estourar o `max`; no `onReady` a barra é escondida de novo. Barra nova (`<progress>`) não é visível em navegadores antigos sem suporte — aceitável para o público-alvo do projeto.

**Verificação da UI (barra de progresso):** este projeto não tem suíte de testes JS (decisão #12, player em JS puro, sem build step). As mudanças em `player/index.html`/`player/app.js` (`renderSynthesisProgress()`, `chunks_done`/`chunks_total` desestruturados no `check()` do `pollUntilReady`) foram validadas por revisão de código e seguem o mesmo padrão das OS-014/016/023, cujos DoDs de UI foram verificados manualmente em navegador na revisão pós-entrega. **Pendente: verificação manual em navegador real** de: barra preenchendo durante a síntese, fallback para texto quando `chunks_total` é `null`, e barra escondida quando o livro fica `ready`.

## 6. Desvios do escopo original

Nenhum.

## 7. Dúvidas / bloqueios

Nenhuma.

## 8. Link do PR

https://github.com/dinei84/listening/pull/21
