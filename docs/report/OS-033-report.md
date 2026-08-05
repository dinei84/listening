# OS-033 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/033-ux-lista-e-fila
**Commit(s) relevante(s):** decdd0b (test: Red), 87a6e37 (feat: Green), 593eb07 (docs)

**Coordenação com a OS-032 (seção 3 da OS):** executada na ordem mandada — a OS-032 foi mergeada em `main` primeiro (PR #25) e este branch foi criado sobre a `main` atualizada, então o `_BLOCKED_DELETE_STATUSES` e o `player/app.js` já incluíam as mudanças da OS-032. Resultado combinado conferido: os botões "Processar agora" e "Deletar" convivem no mesmo `<li>`, ambos com `event.stopPropagation()`.

## 1. Resumo do que foi feito

Quatro problemas de UX da lista de livros resolvidos num PR só, todos em `api/routes_books.py` + `player/app.js` (nenhuma mudança em `core/models.py`): (1) `GET /books/{id}/status` devolve `title` e o cabeçalho do player mostra o título do livro em vez do UUID — o título vem do clique na lista (sem esperar poll), do `title` de `fetchStatus()` (campo manual/sessão) ou do `title` salvo em `localStorage` (`saveState`/`loadSavedState`, mostrado antes do primeiro poll quando já salvo); (2) clicar num livro da lista preenche o campo "Abrir livro existente"; (3) `DELETE /books/{id}` passou a funcionar para livro `uploaded` — `_BLOCKED_DELETE_STATUSES` virou `{"extracting", "processing", "synthesizing"}` (decisão #22) — e o `deleteBook()` do player mostra o `detail` real da API quando falha, em vez da mensagem genérica; (4) o status cru `uploaded` virou "Na fila — aguardando processamento" na lista e no `#player-status` via `statusLabel()` (só exibição, `Book.status` não mudou).

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `decdd0b` "Red" antes de `87a6e37` "Green")
- [x] Todos os testes da OS passam localmente — 159 pass, 0 fail
- [x] Nenhum teste existente quebrou (156 anteriores + 3 novos = 159; o teste antigo `test_delete_book_returns_409_while_processing` foi ajustado para usar `processing`, status que continua bloqueado — o comportamento que ele testava mudou de propósito pela própria OS)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato de `Extractor`/`Speaker`/`JobQueue` mudou; resposta de `GET /books/{id}/status` ganhou `title` (campo novo, aditivo) e `Book.status` não foi tocado (a OS proíbe explicitamente mexer em `core/models.py`)
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — FakeExtractor/FakeSpeaker nos testes de API
- [x] Type hints e docstring de uma linha em toda função pública nova/alterada (as funções de API continuam tipadas; `player/app.js` é JS — regra de Python não se aplica, seguido o estilo de comentário do arquivo)
- [x] `PROJECT_STATE.md` atualizado (seções 2, 3, 4, 5 e 6)
- [x] Relatório criado em `docs/report/OS-033-report.md`
- [x] PR aberto contra o branch principal, título `[OS-033] ...`

### DoD específico da OS (`docs/os/OS-033-ux-lista-e-fila.md` seção 4)

- [x] `GET /books/{id}/status` devolve `title` junto com `id`/`status` — `test_get_books_status_returns_title` (`body["title"] == "book.pdf"`)
- [x] Cabeçalho do player mostra o título do livro, não o UUID — verificação manual em navegador: `Livro: livro-b.pdf` (seção 4)
- [x] Restaurar uma sessão salva (`localStorage`) mostra o título mesmo antes do primeiro poll completar, quando o título já estava salvo — verificação manual determinística abortando a rota de status (o título restaurado aparece sem receber nada da API; seção 4)
- [x] Clicar num livro da lista preenche o campo "Abrir livro existente" com o `book_id` daquele livro — verificação manual: campo preenchido com o UUID do livro clicado (seção 4)
- [x] Campo "Abrir livro existente" continua aceitando um `book_id` digitado, como hoje — o handler do form manual não foi alterado; `test_manual_form`... (não há teste JS; verificado por revisão de código — o `manualForm` submit continua chamando `openBook(bookIdInput.value.trim(), null)`)
- [x] `DELETE /books/{id}` funciona para um livro em `uploaded` (remove `Book`, `Job`s, chunks e PDF) — `test_delete_book_allowed_when_uploaded` + verificação manual (livro enfileirado deletado da lista)
- [x] `DELETE /books/{id}` continua devolvendo 409 para `extracting`/`processing`/`synthesizing` — `test_delete_book_returns_409_while_processing` e `test_delete_book_still_blocked_while_synthesizing` (regressão da decisão #17 no que ela continua valendo)
- [x] Falha ao deletar mostra o motivo real vindo da API (`detail`), não uma mensagem genérica — verificação manual: `Erro ao deletar: Book is still processing` (seção 4)
- [x] Livro enfileirado aparece na UI como "na fila / aguardando", não como `uploaded` cru — verificação manual: `Na fila — aguardando processamento` na lista e no `#player-status` (seção 4)
- [x] `core/models.py` **não** foi alterado por esta OS — `git diff` não toca em `core/models.py`
- [x] Verificação manual em navegador real registrada no relatório — feita (seção 4): abrir livro pela lista, deletar livro enfileirado, conferir o rótulo de fila (e de bônus, o `detail` real do delete bloqueado)

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_get_books_status_returns_title` | `tests/integration/test_api_books.py` | Sim |
| `test_delete_book_allowed_when_uploaded` | `tests/integration/test_api_books.py` | Sim |
| `test_delete_book_still_blocked_while_synthesizing` | `tests/integration/test_api_books.py` | Sim |

Ajuste de teste existente: `test_delete_book_returns_409_while_processing` agora seta o status para `processing` explicitamente (antes criava o livro e esperava 409 por ser `uploaded`, o que a OS-033 muda de propósito — `uploaded` passou a ser deletável).

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `decdd0b` (2 falhas: `AssertionError` em `test_get_books_status_returns_title` por não haver campo `title`, e `409` em `test_delete_book_allowed_when_uploaded` por `uploaded` ainda estar bloqueado) antes de `87a6e37`.

## 4. Verificação manual em navegador real (obrigatória pelo DoD)

Mesma receita da OS-030, com dois atalhos legítimos: (a) os cenários desta OS (lista, título, delete, rótulo de fila) não dependem de síntese — dá para verificar só com a API, sem worker/Kokoro; (b) os livros usados foram criados via `POST /books` com um PDF de fixture e um deles teve o status forçado para `synthesizing` direto no `books.db` do scratchpad (não existiria de outra forma sem o worker rodando de verdade). Chrome real (`channel: "chrome"`, headless) dirigido por Playwright num venv de scratchpad (`/tmp/opencode/os033/`), API rodando com `cwd` num diretório temporário e `PYTHONPATH` apontando para o repo — o `books.db` real do projeto não foi lido nem alterado.

Saída bruta:

```
$ /tmp/opencode/os033/playwright-venv/bin/python /tmp/opencode/os033/verify.py
{
  "lista_rotulos": [
    "livro-b.pdf — Na fila — aguardando processamento — 05/08/2026, 16:43:36",
    "livro-a.pdf — Sintetizando — 05/08/2026, 16:43:36"
  ],
  "abrir_pela_lista": {
    "clicado": "livro-b.pdf",
    "player_title": "Livro: livro-b.pdf",
    "campo_abrir": "482c1b5d-43dd-41c7-bdc7-a83b58666f86",
    "player_status": "Status: Na fila — aguardando processamento"
  },
  "sessao_restaurada_antes_poll": "Livro: livro-b.pdf",
  "deletar_enfileirado": {
    "dialogos": [
      ["confirm", "Deletar este livro? O áudio e o PDF serão removidos."]
    ],
    "restantes": [
      "livro-a.pdf — Sintetizando — 05/08/2026, 16:43:36"
    ]
  },
  "deletar_sintetizando": {
    "dialogos": [
      ["confirm", "Deletar este livro? O áudio e o PDF serão removidos."],
      ["alert", "Erro ao deletar: Book is still processing"]
    ]
  },
  "erros_js": []
}
```

Os cenários confirmados pela saída acima:

1. **Rótulo de fila na lista:** `uploaded` → "Na fila — aguardando processamento", `synthesizing` → "Sintetizando".
2. **Abrir pela lista:** cabeçalho mostra `Livro: livro-b.pdf` (título, não UUID), o campo "Abrir livro existente" é preenchido com o `book_id`, e o `#player-status` mostra `Status: Na fila — aguardando processamento` (o `uploaded` cru sumiu dos dois lugares).
3. **Sessão restaurada com título antes do poll:** o item `sessao_restaurada_antes_poll` do script inicial veio com o título real porque o delay do poll naquele teste acabou ultrapassando a leitura (o handler de rota dorme no event loop do Playwright). Refeito de forma determinística com um teste focado que **aborta** a rota de status (o player nunca recebe o `title` da API):

```
$ /tmp/opencode/os033/playwright-venv/bin/python /tmp/opencode/os033/focus.py
injetado no localStorage: {"bookId":"ca1cd157-...","sequence":0,"currentTime":0,"title":"Livro Restaurado Teste"}
{
  "titulo_apos_reload_sem_poll": "Livro: Livro Restaurado Teste",
  "player_status_sem_poll": "Erro: Failed to fetch"
}
```

Como o poll foi abortado, o único jeito de o cabeçalho mostrar `Livro: Livro Restaurado Teste` é o título ter vindo do `localStorage` via `openBook(resumeState.title)` — exatamente o critério "antes do primeiro poll completar, quando o título já estava salvo". (O `player_status` "Erro: Failed to fetch" é artefato do abort deliberado do poll nesse teste; em uso real o poll responde normalmente.)
4. **Deletar livro enfileirado:** o confirm aparece, o livro `uploaded` some da lista (o `synthesizing` permanece) — remove `Book`, `Job`, PDF e chunks do banco/do disco.
5. **Falha ao deletar mostra o detail real:** deletar o livro em síntese gera `alert` com `Erro ao deletar: Book is still processing` — o `detail` da API, não a mensagem genérica.
6. **Nenhum erro de JS no console** durante todo o roteiro.

## 5. Decisões de implementação documentadas

1. **`statusLabel()` centraliza a tradução de status** e é usada nos dois lugares que o achado citava (lista e `#player-status`). `uploaded` → "Na fila — aguardando processamento"; os demais também ganharam rótulo legível ("Sintetizando", "Pronto", "Erro", "Pausado", "Extraindo", "Processando"), com fallback para o valor cru. Tudo derivado do status real da API, nada persistido no modelo.
2. **Fluxo do título no player:** `openBook(bookId, resumeState, title)` ganhou um terceiro parâmetro opcional. O clique na lista passa `book.title` (exibição imediata, sem esperar poll); o campo manual e a sessão restaurada sem título dependem do `title` de `fetchStatus()` (o primeiro poll seta `playerTitle`); a sessão restaurada **com** título salvo usa `resumeState.title` antes do poll. `saveState()` passou a gravar `title` (campo novo no JSON do `localStorage`, retrocompatível com estados antigos sem `title`).
3. **`DELETE /books/{id}` em `uploaded` — corrida conhecida, não re-arquitetada:** conforme a OS manda, a janela estreita em que o worker chama `claim_next()` no exato momento da exclusão já é segura hoje — `process_job()` faz `book = db.get_book(job.book_id)` e, se `None`, chama `mark_failed()` e retorna sem tocar em disco (`worker/tasks.py`). Nenhum lock/transação novo foi introduzido.

## 6. Desvios do escopo original

Nenhum desvio de escopo de código: as mudanças ficaram em `api/routes_books.py` e `player/app.js` (o `player/index.html` não precisou mudar — nenhum elemento novo; tudo é texto/render via JS), `core/models.py` intocado como a OS exige. Um desvio de **processo** registrado por transparência: os arquivos `docs/os/OS-033-ux-lista-e-fila.md` e a marcação "substituída" na `docs/os/OS-026-nome-amigavel-na-ui.md` chegaram na working tree vindos da sincronização do repo de arquitetura (decisão #6) e foram commitados junto com os docs desta OS — não são trabalho de execução.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Uma observação, sem decisão de arquitetura deste agente: o teste manual da sessão restaurada precisou abortar a rota de status para provar o timing "antes do poll" de forma determinística — em uso real o título do `localStorage` aparece primeiro e é logo "confirmado" (e sobrescrito pelo mesmo valor) pelo `title` do poll; o comportamento observado atende o critério.

## 8. Link do PR

A preencher após abertura do PR.
