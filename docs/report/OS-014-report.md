# OS-014 — Relatório de entrega

**Data:** 2026-08-04
**Branch:** os/014-player-web-basico
**Commit(s) relevante(s):** c5d7dea (test: Red), 10a3850 (feat: Green)

## 1. Resumo do que foi feito

`player/` (HTML/CSS/JS puro, sem build step, decisão #12) implementa upload de PDF, polling de status até `ready`/`error`, playback automático dos chunks de áudio em sequência, play/pause, controle de velocidade (4 opções) e retomar posição via `localStorage`. `api/main.py` monta `player/` como arquivos estáticos na raiz (`StaticFiles`, registrado depois das rotas da API). **Esta OS está implementada mas não fechada**: o DoD exige verificação manual em navegador real, que o agente de execução não tem como fazer neste ambiente (sem ferramenta de automação de navegador) — ver seção 6.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `c5d7dea` "Red" existe antes de `10a3850` "Green") — aplicável só ao teste de backend (`test_player_static_files_are_served`); o restante desta OS é frontend, sem ciclo Red/Green (nota já prevista no texto da própria OS-014, seção "Nota sobre verificação")
- [x] Todos os testes automatizados da OS passam localmente
- [x] Nenhum teste existente quebrou (78 testes no total, todos passando)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (nenhum contrato de backend mudou; o player consome só os endpoints já existentes: `POST /books`, `GET /books/{id}/status`, `GET /books/{id}/audio`, `GET /books/{id}/audio/{sequence}`)
- [x] Nenhuma chamada real a API paga dentro dos testes
- [x] Type hints e docstring de uma linha em toda função pública Python tocada (`api/main.py`); não aplicável a `player/*.js` (JavaScript, sem convenção de type hints/docstring do projeto)
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2 + seção 6) — **marcado explicitamente como bloqueado, não como concluído**, refletindo a realidade (ver seção 6 deste relatório)
- [x] Relatório criado em `docs/report/OS-014-report.md`
- [ ] PR aberto contra o branch principal — será aberto como **draft**, não pronto para merge, até a verificação manual da seção 6 ser feita por alguém com acesso a navegador

### DoD específico da OS (seção 4 de `docs/os/OS-014-player-web-basico.md`)

- [x] `api/main.py` serve `player/` como estático, acessível num navegador (confirmado via `curl`, não via navegador real — ver seção 6)
- [x] Upload de PDF funcional via UI, chamando `POST /books` (código implementado e testado via `curl` no nível HTTP; interação de UI real não verificada — ver seção 6)
- [x] Polling de status até `ready`/`error`, com feedback visível pro usuário (implementado em `app.js`; não observado rodando de verdade)
- [x] Playback automático dos chunks em sequência quando `ready` (implementado via evento `ended` do `<audio>`; não observado rodando de verdade)
- [x] Play/pause funcional (implementado; não observado rodando de verdade)
- [x] Controle de velocidade com pelo menos 3 opções (implementado — 4 opções: 1x/1.25x/1.5x/2x; não observado rodando de verdade)
- [x] Retomar posição funciona após recarregar a página (implementado via `localStorage`; não observado rodando de verdade)
- [x] Campo manual pra digitar um `book_id` existente (implementado)
- [x] Nenhuma dependência nova de frontend (framework/bundler/npm) — só HTML/CSS/JS servido como estático, nenhuma linha adicionada a `requirements.txt`
- [x] Nenhuma chamada de rede além da própria API do projeto (`app.js` só chama `fetch()` para `/books...`, sem CDN/lib externa)

### Nota sobre verificação (DoD específico desta seção da OS)

- [x] Um teste automatizado (backend, `pytest` + `TestClient`) confirma que os arquivos estáticos são servidos corretamente (`test_player_static_files_are_served`, `GET /` devolve 200 e `Content-Type: text/html`)
- [ ] **Verificação manual num navegador real — NÃO FEITA.** Ver seção 6 para detalhes completos e o que foi feito em substituição (best-effort via `curl`).

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_player_static_files_are_served` | `tests/integration/test_player.py` | Sim |

Confirmar: commit "Red" (teste falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Teste falhando antes da implementação (commit Red, `c5d7dea`):

```
tests/integration/test_player.py::test_player_static_files_are_served FAILED
E       assert 404 == 200
```

Suíte completa após a implementação (commit Green, `10a3850`):

```
$ python -m pytest -q
........................................................................ [ 92%]
......                                                                   [100%]
78 passed, 1 warning in 5.97s
```

`black --check` e `ruff check` em `api/main.py` e `tests/integration/test_player.py`: sem alterações pendentes, todos os checks passaram.

**Smoke test via `curl`** (servidor real, `uvicorn api.main:app`, rodando localmente durante a implementação — não substitui a verificação manual em navegador, só confirma que a camada HTTP está corretamente ligada):

```
$ curl -s -o /dev/null -w "status=%{http_code} content-type=%{content_type}\n" http://127.0.0.1:8014/
status=200 content-type=text/html; charset=utf-8

$ curl -s -o /dev/null -w "status=%{http_code} content-type=%{content_type}\n" http://127.0.0.1:8014/app.js
status=200 content-type=text/javascript; charset=utf-8

$ curl -s -o /dev/null -w "status=%{http_code} content-type=%{content_type}\n" http://127.0.0.1:8014/style.css
status=200 content-type=text/css; charset=utf-8

$ curl -s -o /dev/null -w "status=%{http_code}\n" http://127.0.0.1:8014/books/does-not-exist/status
status=404

$ curl -s -o /dev/null -w "status=%{http_code}\n" http://127.0.0.1:8014/docs
status=200

$ curl -s -X POST http://127.0.0.1:8014/books -F "file=@fake.pdf;type=application/pdf"
{"id":"17ffbf07-2746-4bc3-b365-7854d8bb1ccd","status":"uploaded"}
status=200

$ curl -s http://127.0.0.1:8014/books/17ffbf07-2746-4bc3-b365-7854d8bb1ccd/status
{"id":"17ffbf07-2746-4bc3-b365-7854d8bb1ccd","status":"uploaded"}

$ curl -s http://127.0.0.1:8014/books/17ffbf07-2746-4bc3-b365-7854d8bb1ccd/audio
[]
```

Isso confirma: a página HTML, o JS e o CSS são servidos com `Content-Type` correto; `/docs` (Swagger) continua acessível (o mount de estáticos em `/` não engoliu as rotas da API, incluindo as internas do FastAPI); `POST /books` aceita multipart e devolve `status="uploaded"` (contrato assíncrono da OS-012 preservado); `GET /books/{id}/status` e `GET /books/{id}/audio` respondem corretamente para um livro recém-criado (sem worker rodando, então sem áudio ainda — esperado). Artefatos do smoke test (`books.db`, `uploads/`) foram removidos do working tree depois.

## 5. Desvios do escopo original

Nenhum desvio de escopo. Implementados apenas os itens dentro do escopo declarado: `api/main.py` monta `player/` estático; `player/index.html`/`style.css`/`app.js` cobrem upload, polling, playback sequencial, play/pause, velocidade, resume e campo manual de `book_id`. `GET /books` (listagem), autenticação, design visual sofisticado e qualquer framework/bundler continuam fora, conforme a OS.

Decisões de implementação dentro do espaço deixado em aberto:

- **Arquivos separados** (`index.html` + `style.css` + `app.js`) em vez de um arquivo único — mais legível para revisão e edição futura, sem custo real (é tudo servido estático do mesmo jeito).
- **Montado em `/`** (não `/player`) — mais simples para o usuário final abrir `http://localhost:8000/` direto; registrado *depois* de `app.include_router(books_router)`/`app.include_router(audio_router)` em `api/main.py`, com comentário explicando que a ordem importa (o Starlette só cai no mount estático para caminhos que nenhuma rota da API já respondeu — confirmado pelo smoke test que `/docs` e `/books/...` continuam funcionando).
- **`player/__init__.py` removido.** Existia desde a OS-001 como stub vazio, mas `player/` nunca vai ter código Python — é só HTML/CSS/JS estático servido pelo FastAPI (decisão #12). Manter um `__init__.py` lá sugeria (incorretamente) que era um pacote Python importável. Fora do escopo literal da OS, mas é uma limpeza de um arquivo só, diretamente decorrente da própria OS-014 confirmar que `player/` é puramente estático — não expandi escopo além disso.
- **Retomar posição:** chave única em `localStorage` (`audiobook_player_state_v1`) guardando `{bookId, sequence, currentTime}` do último livro tocado — não uma entrada por livro. Suficiente para "retomar de onde parou" com um usuário só (app pessoal, sem múltiplos livros simultâneos no ar); guardar por livro seria mais flexível mas não foi pedido e adicionaria complexidade de gerenciar um dicionário crescente no `localStorage`. Salvamento no evento `timeupdate`, mas limitado (throttle) a uma vez a cada 3 segundos — evita gravar dezenas de vezes por segundo, conforme pedido explicitamente na OS ("throttled, não em todo `timeupdate`").
- **Intervalo de polling:** 2000ms, o valor exato sugerido no texto da OS ("intervalo razoável, ex: 2s").
- **Opções de velocidade:** 1x, 1.25x, 1.5x, 2x — a OS pedia "pelo menos 3 opções (ex: 1x, 1.25x, 1.5x)"; adicionei 2x por ser um valor comum em players de audiobook, sem custo de implementação (é só mais uma `<option>`, usando `audio.playbackRate` nativo).

## 6. Dúvidas / bloqueios

**Bloqueio real, não uma dúvida de arquitetura.** O DoD desta OS exige explicitamente: *"Verificação manual num navegador real é obrigatória, não opcional — subir o servidor (`uvicorn api.main:app`), abrir no navegador, testar upload → espera → playback → troca de velocidade → reload e retomada de posição."*

Este agente de execução (Claude Code, rodando neste ambiente) **não tem acesso a nenhuma ferramenta de automação de navegador** (Playwright, Puppeteer, ou equivalente) nem a um navegador gráfico interativo. As únicas formas de verificação disponíveis foram:
1. O teste automatizado de backend (`test_player_static_files_are_served`), que passa.
2. Smoke test via `curl` contra o servidor real rodando localmente (seção 4) — confirma que a camada HTTP (arquivos estáticos com `Content-Type` correto, rotas da API não engolidas pelo mount, upload multipart funcional) está corretamente ligada.
3. Revisão cuidadosa do código JavaScript (`player/app.js`) linha a linha contra os critérios de aceite, mas isso não é o mesmo que observar o comportamento real — não pega bugs de runtime (erros de sintaxe que só aparecem no console do navegador, condições de corrida entre eventos do `<audio>`, comportamento real de `localStorage` entre reloads, etc.).

**O que falta, concretamente, antes de considerar a OS-014 de fato concluída:**
1. Rodar `uvicorn api.main:app --reload` localmente.
2. Abrir `http://localhost:8000/` num navegador.
3. Fazer upload de um PDF real (com texto, para o `PyMuPDFExtractor` conseguir extrair) e confirmar que o polling mostra o status mudando até `ready` (isso vai exigir também rodar `python -m worker.tasks` numa segunda janela — o worker não roda sozinho).
4. Confirmar que o áudio toca automaticamente em sequência ao terminar cada chunk.
5. Testar o botão de play/pause.
6. Trocar a velocidade e confirmar que o áudio acelera/desacelera de fato.
7. Recarregar a página e confirmar que aparece a opção de retomar de onde parou, e que "Retomar" de fato pula pro ponto certo.
8. Testar o campo manual de `book_id` com um id de um livro já processado.

Seguindo `AGENTS.md` seção 6 ("não decidir sozinho... deixar o PR em rascunho até a decisão ser tomada"): como não posso executar essa verificação e ela é explicitamente obrigatória (não uma decisão de arquitetura em aberto, mas um item de DoD que só um humano pode cumprir neste ambiente), abro o PR desta OS como **draft**. Peço que o dono do projeto (ou qualquer pessoa com acesso a navegador) rode o roteiro acima e relate o resultado — só depois disso o PR deve ser marcado como pronto e a OS-014 considerada de fato concluída em `PROJECT_STATE.md`.

## 7. Link do PR

A preencher após abertura do PR (draft) na próxima etapa.
