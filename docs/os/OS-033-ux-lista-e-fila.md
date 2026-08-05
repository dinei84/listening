# OS-033 — UX da lista de livros: nome amigável, estado da fila e delete de enfileirado

> **Esta OS absorve e substitui a OS-026** (`docs/os/OS-026-nome-amigavel-na-ui.md`), que nunca chegou a ser executada. Consolidada a pedido do dono do projeto para virar um PR só, junto com três achados de uma sessão de teste real (2026-08-05). A OS-026 fica no repositório como registro histórico, marcada como substituída.

> **Coordenação obrigatória com a OS-032 (em execução no momento em que esta OS foi escrita).** As duas tocam `api/routes_books.py` e `player/app.js`, e ambas mexem em `_BLOCKED_DELETE_STATUSES`. **Executar esta OS depois que a OS-032 estiver mergeada em `main`**, e rebasear sobre ela. Se por algum motivo a ordem se inverter, sinalizar no relatório. Ver seção 3.

## 1. Objetivo

Quatro problemas de UX confirmados em uso real, todos na mesma região do código (lista de livros + player + `routes_books`):

1. O player mostra `Livro: <uuid>` — não há como saber qual livro é sem decorar o UUID (era o objetivo da OS-026).
2. Clicar num livro da lista **não** preenche o campo "Abrir livro existente" — confirmado em navegador: o input fica vazio.
3. Um livro em `uploaded` não pode ser deletado (409), mesmo estando apenas **enfileirado**, com nada sendo escrito. Na prática, com um livro grande sintetizando por horas, nenhum livro era deletável.
4. Um livro enfileirado aparece como `uploaded` cru, sem dizer que está **esperando outro livro terminar** — foi exatamente isso que fez parecer que o sistema estava travado (a investigação mostrou API respondendo em milissegundos e worker saudável).

## 2. Escopo

**Dentro do escopo:**

### 2.1 Nome amigável em vez de UUID (herdado da OS-026)
- `api/routes_books.py::get_book_status`: resposta ganha `title` (de `book.title`). Mudança aditiva — nenhum campo existente sai ou muda de nome.
- `player/app.js`: `playerTitle.textContent` passa a usar o título. Quando a abertura vem de um clique na lista, usar o título que já está em mãos (sem esperar o primeiro poll); quando vem do campo manual ou de sessão restaurada, usar o `title` devolvido por `fetchStatus()`.
- `saveState()`/`loadSavedState()` (`localStorage`) passam a guardar também o `title`, para exibir ao restaurar a sessão sem uma chamada de rede extra.

### 2.2 Clique na lista preenche o campo "Abrir livro existente"
- `player/app.js`, no handler de clique do `<li>` ([hoje chama só `openBook(book.id, null)`]): setar `bookIdInput.value = book.id` junto. O campo continua sendo o caminho de entrada manual por `book_id` — só deixa de ficar vazio quando a abertura veio da lista.

### 2.3 Deletar livro apenas enfileirado
- `api/routes_books.py`: **remover `"uploaded"` de `_BLOCKED_DELETE_STATUSES`**, que passa a bloquear só `{"extracting", "processing", "synthesizing"}` (+ o que a OS-032 tiver definido — ver seção 3). Motivo: a justificativa da decisão #17 é "o worker pode estar escrevendo neste livro"; em `uploaded` o `Job` está `queued` e o worker **não tocou nele**, nada está sendo escrito.
- **Corrida conhecida, já tratada — não re-arquitetar:** existe uma janela estreita em que o worker chama `claim_next()` no exato momento da exclusão. Isso já é seguro hoje: `process_job()` faz `book = db.get_book(job.book_id)` e, se for `None`, chama `mark_failed()` e retorna sem tocar em disco (`worker/tasks.py`). Documentar no relatório que a corrida foi considerada e é benigna; **não** introduzir lock/transação nova por causa disso.
- `player/app.js::deleteBook()`: hoje faz `throw new Error("Falha ao deletar o livro")`, **descartando o motivo real** que a API mandou (`{"detail": "Book is still processing"}`). Passar a ler o `detail` do corpo da resposta e mostrá-lo ao usuário, com a mensagem genérica só como fallback quando não houver `detail`.

### 2.4 Estado real da fila na UI
- `player/app.js`: onde hoje o status cru é exibido (lista de livros e `#player-status`), traduzir `uploaded` para algo como **"Na fila — aguardando processamento"**. Os demais status podem ganhar rótulos legíveis também (`synthesizing` → "Sintetizando", `ready` → "Pronto", `error` → "Erro"), a critério da implementação, desde que o texto continue derivando do status real vindo da API.
- **Fazer isso puramente na exibição, sem mexer em `Book.status`.** Não adicionar um status `"queued"` ao `Literal` de `core/models.py`: a OS-032 está adicionando `"paused"` a esse mesmo `Literal`, e duas OS's mexendo no mesmo enum em paralelo é conflito garantido. Além disso, `uploaded` já descreve corretamente o estado do dado — o que falta é vocabulário na UI, não no modelo.

**Fora do escopo:**
- Mostrar a **posição** na fila ("3º da fila") ou tempo estimado — exigiria endpoint novo; "na fila" já resolve a confusão que motivou o achado.
- Renomear/editar o título de um livro depois do upload.
- Mudar o formato do `book_id` (continua UUID internamente — isto é só exibição).
- Qualquer mudança em preempção/prioridade de fila — é a OS-032.
- Cancelar um `Job` em andamento.

## 3. Contratos envolvidos

Nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda. Mudança aditiva na resposta de `GET /books/{id}/status` (campo `title` novo). Nenhuma mudança em `core/models.py`.

**Decisão #17 é alterada (não revogada):** a lista de status que bloqueiam `DELETE` deixa de incluir `uploaded`. O princípio original ("não apagar o que o worker pode estar escrevendo") continua valendo — o que muda é o reconhecimento de que `uploaded` não satisfaz esse critério. Registrar a alteração como **entrada nova** no ADL do `PROJECT_STATE.md`, referenciando a #17, nunca editando a #17 retroativamente (seção 7 do `PROJECT_STATE.md`).

**Ao rebasear sobre a OS-032:** aquela OS também altera `_BLOCKED_DELETE_STATUSES` (para garantir que `paused` seja deletável) e também mexe em `player/app.js` (botão "Processar agora" e tratamento do status `paused`). O resultado combinado esperado é: bloqueiam delete apenas `extracting`, `processing` e `synthesizing`. Conferir que o botão "Processar agora" e o botão "Deletar" convivem no mesmo `<li>`, ambos com `event.stopPropagation()` para não abrirem o livro ao serem clicados.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `GET /books/{id}/status` devolve `title` junto com `id`/`status`
- [ ] Cabeçalho do player mostra o título do livro, não o UUID
- [ ] Restaurar uma sessão salva (`localStorage`) mostra o título mesmo antes do primeiro poll completar, quando o título já estava salvo
- [ ] Clicar num livro da lista preenche o campo "Abrir livro existente" com o `book_id` daquele livro
- [ ] Campo "Abrir livro existente" continua aceitando um `book_id` digitado, como hoje
- [ ] `DELETE /books/{id}` funciona para um livro em `uploaded` (remove `Book`, `Job`s, chunks e PDF)
- [ ] `DELETE /books/{id}` continua devolvendo 409 para `extracting`/`processing`/`synthesizing`
- [ ] Falha ao deletar mostra o motivo real vindo da API (`detail`), não uma mensagem genérica
- [ ] Livro enfileirado aparece na UI como "na fila / aguardando", não como `uploaded` cru
- [ ] `core/models.py` **não** foi alterado por esta OS
- [ ] Verificação manual em navegador real registrada no relatório (mesmo padrão das OS-014/016/023/030): abrir livro pela lista, deletar um livro enfileirado, e conferir o rótulo de fila

## 5. Testes exigidos (mínimo)

- `test_get_books_status_returns_title`
- `test_delete_book_allowed_when_uploaded`
- `test_delete_book_still_blocked_while_synthesizing` (regressão da decisão #17 no que ela continua valendo)

As mudanças de `player/app.js`/`index.html` são JS puro, sem suíte de testes JS no projeto (decisão #12) — verificação principal é manual, registrada no relatório. Se houver como cobrir algo servido no HTML por um teste de integração existente (como `tests/integration/test_player.py` já faz para o seletor de idioma da OS-025), aproveitar.

Local sugerido: `tests/integration/test_api_books.py`, `tests/integration/test_player.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-033-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
