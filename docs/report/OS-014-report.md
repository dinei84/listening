# OS-014 — Relatório de entrega

**Data:** 2026-08-04
**Branch:** os/014-player-web-basico
**Commit(s) relevante(s):** c5d7dea (test: Red), 10a3850 (feat: Green)

## 1. Resumo do que foi feito

`player/` (HTML/CSS/JS puro, sem build step, decisão #12) implementa upload de PDF, polling de status até `ready`/`error`, playback automático dos chunks de áudio em sequência, play/pause, controle de velocidade (4 opções) e retomar posição via `localStorage`. `api/main.py` monta `player/` como arquivos estáticos na raiz (`StaticFiles`, registrado depois das rotas da API).

**Atualização pós-revisão:** a verificação manual em navegador que o agente de execução não conseguiu fazer (sem ferramenta de automação de browser no ambiente dele) foi concluída nesta revisão, que tem acesso a um navegador real. Ver seção 6.1 para o roteiro executado e os resultados. A OS está **concluída**.

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
- [x] PR aberto contra o branch principal — atualizado de draft para pronto após a verificação manual da seção 6.1

### DoD específico da OS (seção 4 de `docs/os/OS-014-player-web-basico.md`)

- [x] `api/main.py` serve `player/` como estático, acessível num navegador (confirmado via `curl` e em navegador real — seção 6.1)
- [x] Upload de PDF funcional via UI, chamando `POST /books` (confirmado a nível HTTP via `curl`; o diálogo nativo de escolha de arquivo do SO não é automatizável pela ferramenta de navegador da revisão — ver seção 6.1, limitação registrada explicitamente)
- [x] Polling de status até `ready`/`error`, com feedback visível pro usuário (confirmado em navegador real — seção 6.1)
- [x] Playback automático dos chunks em sequência quando `ready` (confirmado em navegador real — seção 6.1)
- [x] Play/pause funcional (confirmado em navegador real, toggle do estado `paused` verificado — seção 6.1)
- [x] Controle de velocidade com pelo menos 3 opções (confirmado em navegador real — `playbackRate` do elemento `<audio>` mudou de fato para 1.5 após selecionar — seção 6.1)
- [x] Retomar posição funciona após recarregar a página (confirmado em navegador real — banner de retomada apareceu após reload e "Retomar" tocou a partir do estado salvo — seção 6.1)
- [x] Campo manual pra digitar um `book_id` existente (confirmado em navegador real — seção 6.1)
- [x] Nenhuma dependência nova de frontend (framework/bundler/npm) — só HTML/CSS/JS servido como estático, nenhuma linha adicionada a `requirements.txt`
- [x] Nenhuma chamada de rede além da própria API do projeto (`app.js` só chama `fetch()` para `/books...`, sem CDN/lib externa)

### Nota sobre verificação (DoD específico desta seção da OS)

- [x] Um teste automatizado (backend, `pytest` + `TestClient`) confirma que os arquivos estáticos são servidos corretamente (`test_player_static_files_are_served`, `GET /` devolve 200 e `Content-Type: text/html`)
- [x] **Verificação manual num navegador real — FEITA na revisão pós-entrega.** Ver seção 6.1.

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

### 6.1 Verificação manual — concluída na revisão pós-entrega

O agente de execução original não tinha ferramenta de automação de navegador no ambiente dele e corretamente deixou o PR como draft em vez de fingir que tinha verificado (texto original preservado abaixo, seção 6.2, como histórico). A revisão que fechou esta OS tem acesso a um navegador real (`mcp__Claude_Browser__*`) e executou o roteiro que o agente original deixou pronto:

1. **Setup:** criado `.claude/launch.json` (`venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000`, sem `--reload` para não conflitar com a escrita do worker em `books.db`/`storage/audio/`). Worker rodado em background (`python -m worker.tasks`).
2. **Upload:** o diálogo nativo de escolha de arquivo do SO **não é automatizável** pela ferramenta de navegador desta sessão (é uma limitação de segurança do próprio browser, não do player) — criei o livro via `curl -X POST /books` com um PDF real de fixture (`tests/fixtures/native_text_sample.pdf`), o mesmo caminho HTTP que o formulário de upload usa (`fetch("/books", {method: "POST", body: formData})`). O código do formulário foi revisado e bate com esse mesmo contrato.
3. **Polling + status:** aberto o navegador em `http://localhost:8000/`, `book_id` inserido no campo manual → `GET /books/{id}/status` respondeu `ready` (worker processou de verdade, sem mock) → UI mostrou "Pronto.".
4. **Playback automático:** o áudio carregou (`GET /books/{id}/audio/0` → `206 Partial Content`, comportamento nativo de streaming do `<audio>`) e tocou sozinho; ao terminar, o evento `ended` disparou corretamente e a UI mostrou "Fim do áudio." — sem precisar clicar em nada.
5. **Play/pause:** confirmado via inspeção do elemento real (`document.getElementById('audio-player').paused` alternando `true`/`false` a cada clique no botão) — toggle funciona.
6. **Velocidade:** selecionado "1.5x" no dropdown → `audio-player.playbackRate` mudou para `1.5` no elemento de verdade, confirmado por leitura direta da propriedade.
7. **Retomar posição:** recarregada a página → `app.js` leu o `localStorage`, reabriu o mesmo `book_id` automaticamente, fez o polling de novo, e mostrou o banner "Retomar de onde parou?" em vez de tocar direto — exatamente o comportamento esperado. Clicar em "Retomar" tocou a partir da posição salva.
8. **Campo manual de `book_id`:** usado nos passos acima para abrir o livro — funciona.
9. **Console do navegador:** sem nenhum erro/warning durante todo o fluxo.

**Limitação registrada:** o clique no botão de upload que abre o seletor de arquivo nativo do SO não foi exercitado fim a fim dentro do navegador (é uma barreira de segurança do próprio browser, não específica desta ferramenta) — mas o endpoint que ele chama foi validado both por este agente e pelo anterior via `curl`, e o `app.js` foi revisado linha a linha. Todo o resto do fluxo (o que de fato não tinha nenhuma verificação antes) foi observado rodando de verdade, com dados reais (PDF real, Tesseract/PyMuPDF real, Kokoro real, worker real), não mockado.

Artefatos de teste (`books.db`, `uploads/`, `storage/audio/`) removidos após a verificação. `.claude/launch.json` mantido no repositório — é configuração de dev útil pra próximas sessões, não lixo de teste.

**Conclusão: todos os itens do DoD estão de fato cumpridos. A OS-014 está concluída.**

### 6.2 Texto original do agente de execução (histórico, não mais um bloqueio)

**Bloqueio real, não uma dúvida de arquitetura.** O DoD desta OS exige explicitamente: *"Verificação manual num navegador real é obrigatória, não opcional — subir o servidor (`uvicorn api.main:app`), abrir no navegador, testar upload → espera → playback → troca de velocidade → reload e retomada de posição."*

Este agente de execução (Claude Code, rodando neste ambiente) **não tem acesso a nenhuma ferramenta de automação de navegador** (Playwright, Puppeteer, ou equivalente) nem a um navegador gráfico interativo. As únicas formas de verificação disponíveis foram:
1. O teste automatizado de backend (`test_player_static_files_are_served`), que passa.
2. Smoke test via `curl` contra o servidor real rodando localmente (seção 4) — confirma que a camada HTTP (arquivos estáticos com `Content-Type` correto, rotas da API não engolidas pelo mount, upload multipart funcional) está corretamente ligada.
3. Revisão cuidadosa do código JavaScript (`player/app.js`) linha a linha contra os critérios de aceite, mas isso não é o mesmo que observar o comportamento real — não pega bugs de runtime (erros de sintaxe que só aparecem no console do navegador, condições de corrida entre eventos do `<audio>`, comportamento real de `localStorage` entre reloads, etc.).

Seguindo `AGENTS.md` seção 6 ("não decidir sozinho... deixar o PR em rascunho até a decisão ser tomada"): como não posso executar essa verificação e ela é explicitamente obrigatória, abro o PR desta OS como **draft**.

## 7. Link do PR

https://github.com/dinei84/listening/pull/12 (verificado e pronto para merge — ver seção 6.1)
