# OS-016 — Relatório de entrega

**Data:** 2026-08-04
**Branch:** os/016-listagem-no-player
**Commit(s) relevante(s):** 724ab26 (feat)

## 1. Resumo do que foi feito

`player/index.html` e `player/app.js` ganharam uma seção "Meus livros": busca `GET /books` ao carregar a página, renderiza `title`/`status`/`created_at` de cada livro numa lista clicável, clicar num item abre o livro reaproveitando `openBook()` já existente, botão "Atualizar lista" rebusca sem recarregar a página, e a lista se atualiza sozinha após um upload bem-sucedido. Campo manual de `book_id` mantido intacto. **A OS não está concluída** — falta a verificação manual em navegador real exigida pelo seu próprio DoD; ver seção 6.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — não aplicável no sentido de Red/Green: esta OS não introduz nenhum contrato de backend novo (usa `GET /books` já testado na OS-015), e a própria OS (seção 5) declara que não há teste automatizado novo, só a checklist manual
- [x] Todos os testes automatizados existentes passam localmente (82 testes)
- [x] Nenhum teste existente quebrou
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato de backend tocado; consome `GET /books` exatamente como documentado
- [x] Nenhuma chamada real a API paga
- [ ] Type hints e docstring de uma linha em toda função pública — não aplicável, `player/*.js` é JavaScript, sem convenção de type hints/docstring do projeto (mesma nota já registrada na OS-014)
- [x] `PROJECT_STATE.md` atualizado — marcado explicitamente como **bloqueado**, não como concluído
- [x] Relatório criado em `docs/report/OS-016-report.md`
- [x] PR aberto contra o branch principal, como **draft** (verificação manual pendente)

### DoD específico da OS (`docs/os/OS-016-listagem-no-player.md` seção 4)

- [x] Ao carregar a página, a lista de livros é buscada e renderizada — confirmado por leitura de código (`init()` chama `refreshBooksList()`) e pelo backend real via `curl` (seção 4); **não confirmado em navegador**
- [x] Lista vazia mostra mensagem amigável ("Nenhum livro ainda.", elemento `#books-list-empty`) — confirmado por leitura de código; **não confirmado em navegador**
- [x] Clicar num item da lista abre o livro via `openBook()` já existente (`li.addEventListener("click", () => openBook(book.id, null))`) — confirmado por leitura de código; **não confirmado em navegador**
- [x] Botão "Atualizar lista" rebusca e re-renderiza sem recarregar a página (`refreshBooksBtn` chama `refreshBooksList()`) — confirmado por leitura de código; **não confirmado em navegador**
- [x] Depois de um upload bem-sucedido, a lista se atualiza automaticamente (`refreshBooksList()` chamado após `openBook(id, null)` no handler de submit do upload) — confirmado por leitura de código; **não confirmado em navegador**
- [x] Campo manual de `book_id` continua funcionando — nenhuma linha do `manual-form`/`manualForm` foi tocada
- [x] Nenhuma dependência nova de frontend — só HTML/CSS/JS, nenhuma linha nova em `requirements.txt` ou equivalente
- [x] Nenhuma chamada de rede além da própria API do projeto — `fetchBooks()` só chama `fetch("/books")`

### Nota sobre verificação (seção da própria OS)

- [ ] **Verificação manual num navegador real — NÃO FEITA.** O agente de execução não teve acesso a nenhuma ferramenta de automação de navegador neste ambiente (nenhum MCP de browser/Playwright disponível). Seguindo o protocolo já estabelecido na OS-014 para este exato cenário: implementar, deixar o PR como draft, documentar precisamente o que falta e por quê — não fechar a OS sem essa verificação.

## 3. Testes escritos

Nenhum teste automatizado novo — a própria OS (seção 5) declara isso como esperado, já que nenhum contrato de API muda. A suíte completa (82 testes, toda pré-existente) foi rodada para confirmar ausência de regressão.

Confirmar: commit "Red" existe antes do commit "Green"? Não aplicável — sem ciclo TDD nesta OS (frontend puro, sem contrato novo a testar).

## 4. Saída de comandos relevantes

Suíte completa, sem regressões:

```
$ python -m pytest -q
........................................................................ [ 87%]
..........                                                               [100%]
82 passed, 1 warning in 8.89s
```

`node --check player/app.js`: sem erro de sintaxe.

Smoke test via `curl` contra a API real (`uvicorn api.main:app`) + worker reais rodando localmente, para confirmar que o backend que a UI nova consome está correto (não substitui a verificação em navegador, só valida a camada HTTP):

```
$ curl -s http://127.0.0.1:8010/books
[]

$ curl -s -X POST http://127.0.0.1:8010/books -F "file=@tests/fixtures/native_text_sample.pdf;type=application/pdf"
{"id":"1efb8f29-6d13-45f1-ad92-b36dba818f9a","status":"uploaded"}

$ curl -s -X POST http://127.0.0.1:8010/books -F "file=@tests/fixtures/image_only_sample.pdf;type=application/pdf"
{"id":"26f86000-7beb-42b9-8032-6e8dbc6a15a8","status":"uploaded"}

$ curl -s http://127.0.0.1:8010/books
[{"id":"26f86000-7beb-42b9-8032-6e8dbc6a15a8","title":"image_only_sample.pdf","status":"ready","created_at":"2026-08-04T22:56:59.661847+00:00"},
 {"id":"1efb8f29-6d13-45f1-ad92-b36dba818f9a","title":"native_text_sample.pdf","status":"ready","created_at":"2026-08-04T22:56:55.938463+00:00"}]

$ curl -s http://127.0.0.1:8010/ | grep -A3 books-list-section
    <section id="books-list-section">
      <h2>Meus livros</h2>
      <button id="refresh-books-btn" type="button">Atualizar lista</button>
      <ul id="books-list"></ul>
```

Dois livros reais processados pelo worker de verdade (Kokoro/Tesseract/PyMuPDF, sem mock), ordenados por `created_at` decrescente, com `title`/`status`/`created_at` presentes — exatamente o formato que `renderBooksList()` consome. Processos de API e worker encerrados ao final; `books.db`/`uploads/`/`storage/audio/` (gerados em runtime, não versionados) limpos antes do teste.

## 5. Desvios do escopo original

Nenhum desvio de escopo. O único desvio é de **processo**, não de escopo: a verificação manual em navegador que o DoD da OS exige não foi feita, pela ausência de ferramenta de automação de browser neste ambiente — não por decisão de pular a etapa.

## 6. Dúvidas / bloqueios

**Bloqueio (não é dúvida de arquitetura):** falta a verificação manual em navegador real, exigida explicitamente pela seção "Nota sobre verificação" da própria OS-016. Roteiro que ainda precisa ser executado por um agente/pessoa com acesso a navegador:

1. Subir API + worker (`RUNBOOK.md` seção 4).
2. Abrir `http://localhost:8000/` e confirmar que a lista "Meus livros" aparece (vazia, com a mensagem amigável, se `books.db` estiver limpo).
3. Enviar um PDF pela seção de upload; confirmar que a lista se atualiza sozinha e o livro recém-criado aparece, mesmo antes de ficar `ready`.
4. Enviar um segundo PDF; confirmar que ambos aparecem, mais recente primeiro.
5. Clicar num item da lista (de um livro diferente do que está tocando) e confirmar que abre e toca normalmente (mesmo fluxo de `openBook()` da OS-014: polling, playback, resume).
6. Clicar em "Atualizar lista" e confirmar que rebusca sem recarregar a página inteira (ex: gerar um terceiro upload via `curl` em paralelo e ver se aparece só depois do clique).
7. Confirmar que o campo manual de `book_id` (`#manual-section`) continua funcionando normalmente.

Este mesmo cenário já ocorreu na OS-014 e foi resolvido na revisão pós-entrega por um agente com acesso a navegador real — o precedente e o roteiro de verificação já estão documentados em `docs/report/OS-014-report.md` seção 6.1, e podem servir de modelo para preencher esta seção quando a verificação acontecer.

## 7. Link do PR

https://github.com/dinei84/listening/pull/14 (draft — verificação manual pendente, ver seção 6)
