# OS-014 — Player web básico

## 1. Objetivo

Entregar os 3 itens do player que `ARQUITETURA.md` seção 8 (roadmap) já previa: play/pause, velocidade de reprodução, retomar posição. HTML/CSS/JS puro, sem build step (decisão #12 em `PROJECT_STATE.md`) — servido pelo próprio FastAPI.

## 2. Escopo

**Dentro do escopo:**
- `api/main.py`: montar `player/` como arquivos estáticos (`fastapi.staticfiles.StaticFiles`), acessível a partir de `/` ou `/player` (à escolha de quem implementar).
- `player/index.html` (+ CSS/JS, num arquivo só ou separados — decisão de implementação, documentar no relatório):
  - Formulário pra selecionar um PDF e enviar via `POST /books`.
  - Depois do upload, faz polling em `GET /books/{id}/status` (intervalo razoável, ex: 2s) até `ready` ou `error`, mostrando o status pro usuário enquanto espera.
  - Quando `ready`, busca `GET /books/{id}/audio` e toca os chunks em sequência (`sequence` crescente) usando `<audio>` — ao terminar um chunk, carrega e toca o próximo automaticamente, sem intervenção do usuário.
  - Play/pause.
  - Controle de velocidade de reprodução (`audio.playbackRate` — suporte nativo do HTML5, sem lib nenhuma), pelo menos 3 opções (ex: 1x, 1.25x, 1.5x).
  - Retomar posição: salvar em `localStorage` o `book_id` + `sequence` + tempo dentro do chunk (throttled, não em todo `timeupdate`) e, ao recarregar a página, oferecer retomar de onde parou.
  - Campo pra digitar manualmente um `book_id` já existente (não existe endpoint de listagem de livros ainda — `GET /books` está fora de escopo desta OS, ver abaixo).

**Fora do escopo:**
- `GET /books` (listagem de livros) — sem isso, o player só sabe de um livro pelo id (do upload recém-feito ou digitado manualmente). Fica pro backlog se for útil depois.
- Autenticação, múltiplos usuários.
- Design visual sofisticado — só precisa ser funcional e legível.
- Qualquer framework/bundler de frontend (React, Vue, Vite, webpack) — decisão #12, HTML/CSS/JS puro.
- Suporte a capítulos múltiplos reais — o pipeline hoje só produz um capítulo sintético por livro (OS-012); o player toca a sequência de `AudioChunk` que a API devolve, não precisa saber de capítulo nenhum.

## 3. Contratos envolvidos

Nenhum contrato de backend muda. O player consome só os endpoints já existentes: `POST /books`, `GET /books/{id}/status`, `GET /books/{id}/audio`, `GET /books/{id}/audio/{sequence}`.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `api/main.py` serve `player/` como estático, acessível num navegador
- [ ] Upload de PDF funcional via UI, chamando `POST /books`
- [ ] Polling de status até `ready`/`error`, com feedback visível pro usuário
- [ ] Playback automático dos chunks em sequência quando `ready`
- [ ] Play/pause funcional
- [ ] Controle de velocidade com pelo menos 3 opções
- [ ] Retomar posição funciona após recarregar a página (mesmo `book_id`)
- [ ] Campo manual pra digitar um `book_id` existente
- [ ] Nenhuma dependência nova de frontend (framework/bundler/npm) — só HTML/CSS/JS servido como estático
- [ ] Nenhuma chamada de rede além da própria API do projeto

### Nota sobre verificação (esta OS é diferente das anteriores)

Esta é a primeira OS de frontend do projeto — o ciclo Red/Green de TDD não se aplica da mesma forma a interação de UI (não tem sentido escrever um teste automatizado que "clica" em play antes de o botão existir, sem introduzir uma dependência pesada de teste de browser tipo Playwright, que não se justifica pra um player "básico" de projeto pessoal). Em vez disso:
- [ ] Um teste automatizado (backend, `pytest` + `TestClient`) confirma que os arquivos estáticos são servidos corretamente (`GET /` ou `/player` devolve 200 e `Content-Type` de HTML).
- [ ] **Verificação manual num navegador real é obrigatória, não opcional** — subir o servidor (`uvicorn api.main:app`), abrir no navegador, testar upload → espera → playback → troca de velocidade → reload e retomada de posição. Descrever no relatório o que foi testado e o resultado (idealmente com screenshot).

## 5. Testes exigidos (mínimo)

- `test_player_static_files_are_served` (backend, `TestClient`)

Mais a verificação manual descrita acima, documentada no relatório — não é um "teste" no sentido de `pytest`, mas é DoD.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-014-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
