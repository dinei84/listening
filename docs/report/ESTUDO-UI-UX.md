# Estudo — reconstrução da UI/UX do player

**Data:** 28/09/2026 · **Status:** estudo, nenhuma OS aberta · **Decisão de escopo: do dono.**

Este documento não é relatório de OS. É o levantamento que precede a decisão de
*o que* reconstruir, no mesmo espírito dos itens 49–59 do backlog: medir primeiro,
decidir depois.

## 1. O que existe hoje, medido

| Arquivo | Linhas |
|---|---|
| `player/app.js` | 939 |
| `player/index.html` | 105 |
| `player/style.css` | **56** |

- **4 seções empilhadas**, todas visíveis ao mesmo tempo: `upload-section`
  (Enviar PDF), `books-list-section` (Meus livros), `manual-section` (Abrir livro
  existente), `player-section` (Player).
- **33 `id`s** manipulados direto por `document.getElementById`, sem componente
  nem estado central.
- **0 `@media`** no CSS. `max-width: 640px`, `margin: 2rem auto`, `system-ui`.
- **0 ocorrências** de `mediaSession`, `MediaMetadata`, `serviceWorker`,
  `manifest`, `preload`, `aria-`, `role=`, `prefers-color-scheme`.

Nada disso é acidente de desleixo: a UI foi construída como *superfície de
verificação* das OS de backend (OS-014, 016, 023, 024, 029, 030, 032, 033, 039,
042, 051), cada uma acrescentando o elemento mínimo para provar que a feature
funcionava. O resultado é uma UI que **prova o backend** e não **serve o ouvinte**.

## 2. Achados estruturais

Os quatro primeiros mudam o que o produto *é*. Os outros mudam o quanto ele
incomoda.

### 2.1 A barra de progresso cobre 1 trecho de ~533 — o achado principal

`playChunk` faz `audioPlayer.src = chunks[index].url` e toca **um chunk por vez**.
O `<audio controls>` nativo, portanto, mostra a linha de tempo de *um chunk*.

Medido: chunk = `DEFAULT_MAX_CHARS = 1000` caracteres; duração média real no banco
= **52,8 s** (min 25,2 · max 80,4). Um livro de 533 k caracteres ≈ **533 chunks
≈ 7,8 h de áudio**.

Ou seja: quem está ouvindo um livro de quase 8 horas tem uma régua de ~53
segundos que **zera 533 vezes**, e nenhuma resposta para "quanto falta". Não
existe scrub contínuo, nem "voltar 15 s", nem tempo total, nem tempo restante do
capítulo. O `#position-indicator` diz "trecho 212 de 533", que é a unidade do
*pipeline*, não a do ouvinte.

**O dado para consertar isso já existe no cliente:** `GET /books/{id}/audio` já
devolve `duration_seconds` por chunk. Somar é suficiente para posição absoluta,
total e restante — **sem tocar no backend**. É a maior distância entre este player
e qualquer app de audiobook, e é a mais barata de fechar.

### 2.2 Emenda audível a cada ~53 segundos

No `ended`, o handler chama `playChunk(nextIndex)`, que faz `src = …` e `load()` e
só toca no `loadedmetadata`. O chunk seguinte **não é pré-carregado** enquanto o
atual toca, e o `<audio>` não tem `preload`. São ~533 lacunas de rede + decode por
livro, uma a cada 53 s.

Isto é relevante além do conforto: passamos duas OS (045, 056) calibrando pausa de
frase em 420–520 ms e evitando troca de motor no meio da frase para não produzir
emenda audível — enquanto o player insere uma lacuna não medida a cada trecho.

### 2.3 Não há controle de fundo, nem instalação, nem offline

Zero `mediaSession`: no celular, com a tela bloqueada, não há como pausar sem
desbloquear e achar a aba. Zero `manifest` e zero service worker: não instala e
não toca offline.

Um audiobook é ouvido caminhando, no carro, dormindo. **Exigir aba em primeiro
plano e localhost no ar é o que separa "demo de desktop" de "produto".**

### 2.4 O motor que narrou cada trecho é invisível

`AudioChunk.engine_used` existe e é gravado (`"openai"` / `"kokoro"`), mas **não
está no payload de `/books/{id}/audio`** nem em nenhum lugar da tela.

Foi exatamente esta a dúvida do dono em 13/08/2026: *"não consegui investigar se
realmente está consumindo da API key"*. A pergunta era de UI, não de backend. E
conecta direto no item 59 do backlog: se o limiar vai virar diferenciador de
plano, o usuário precisa **ver** o que está pagando.

### 2.5 O resto

- **"Abrir livro existente" colando um UUID** é afordância de desenvolvedor
  ocupando uma das quatro seções de topo, com o mesmo peso visual do player.
- **Tudo na mesma tela, sempre.** Durante 8 horas de escuta, o formulário de
  upload fica acima do player. Não existe "estou ouvindo" versus "estou
  gerenciando a biblioteca".
- **Confirmação de custo é um botão e um número.** `pending_confirmation` mostra
  "deve custar US$ X" e oferece confirmar ou deletar — sem dizer quanto é premium
  e quanto é local, sem permitir ajustar o limiar daquele livro, sem "faz tudo no
  motor local".
- **Celular não está quebrado, mas nunca foi alvo.** 640px + `system-ui` degrada
  de forma aceitável; o que não existe é decisão: `#controls` é um flex que quebra
  onde der, alvos de toque têm tamanho default, e a barra de controles não foi
  dimensionada para o polegar.
- **Sem modo escuro**, num produto usado à noite.
- **Sem acessibilidade:** nenhum `aria-`, nenhum `role`, nenhum estilo de foco.
  Os atalhos ← → espaço existem (OS-039) e não estão escritos em lugar nenhum da
  tela.

## 3. O que está certo e não deve ser jogado fora

Reconstruir a UI não é motivo para perder comportamento que custou OS para
descobrir:

- **Tocar antes de `ready`** (OS-030): o player toca o que já foi sintetizado.
  Foi a correção de um sintoma real de "10 minutos carregando".
- **`waitingForNextChunk`** — alcançar o fim do sintetizado não é fim do livro, e
  o polling retoma sozinho.
- **Retomada com fonte de verdade no servidor** (OS-028) e `localStorage` como
  cache para resposta imediata ao reabrir.
- **Throttle de gravação de posição** com escrita imediata na navegação manual.
- **"Anterior" com limiar de 3 s** (padrão de tocador de podcast).
- **Aviso de worker ausente** (OS-051).
- **`mergeChunks` incorporando chunks novos sem reiniciar a reprodução.**

Qualquer reconstrução precisa de teste que trave esses sete pontos antes de mexer.

## 4. Escopo proposto — três OS, em ordem de valor por custo

Deliberadamente **não** proponho reescrever em framework. 939 linhas de JS
baunilha com 33 `id`s é gerenciável; trocar por React/Svelte é decisão de stack
do dono, não pré-requisito de nenhum achado acima.

**OS-A — Linha de tempo contínua do livro.** Fecha 2.1 e 2.2. Posição absoluta,
total e restante somando `duration_seconds`; scrub contínuo que atravessa
fronteira de chunk; ±15 s; pré-carga do chunk seguinte. Sem mudança de backend.
É o maior ganho percebido do pacote.

**OS-B — Player de celular de verdade.** Fecha 2.3. `mediaSession` com metadados e
controles de tela bloqueada, `manifest`, breakpoints e alvos de toque. Aqui entra
a decisão de layout: separar "ouvindo" de "biblioteca".

**OS-C — Transparência de motor e de custo.** Fecha 2.4 e o item de confirmação.
`engine_used` no payload de `/audio` (uma linha), marca por trecho na tela,
e a confirmação de custo mostrando a divisão premium/local. Esta tem dependência
de produto: **é a superfície de que o item 59 (limiar como plano) vai precisar.**

## 5. Decisões que são do dono, não de execução

1. **Stack.** Manter JS baunilha ou adotar framework. Recomendo manter — nenhum
   achado deste estudo exige framework.
2. **Ordem.** A proposta é A → B → C por valor/custo. Se a prioridade é o lado
   comercial do item 59, C sobe.
3. **Alvo primário.** Se celular passa a ser o alvo, B deixa de ser polimento e
   vira pré-requisito de A (scrub com o dedo é diferente de scrub com o mouse).
4. **Verificação.** A receita Playwright da OS-030 está registrada e é reutilizável,
   mas adotar suíte de browser como dependência do projeto continua em aberto.
   Sem ela, reconstrução de UI é verificada de olho — e este projeto já tem
   histórico de código que passou em teste mockado sem nunca ter rodado de ponta a
   ponta.

---

## 5. Adendo de 29/09/2026 — auditoria de banco, requisições e segurança

Levantada a pedido do dono ao aprovar a ordem A → B → C. As perguntas foram:
o áudio fica salvo (o usuário paga de novo?), e há N+1 ou outro problema clássico?

### 5.1 Pagamento é único, e está garantido no código

O áudio vai para arquivo em disco (`storage/audio/{book_id}/{sequence}.wav`) e o
banco guarda só metadado. Reouvir é `FileResponse(chunk.file_path)` — **zero
chamada de API**.

A garantia não é só "o arquivo existe": `worker/tasks.py:72` monta `already_done`
a partir dos chunks persistidos e passa `skip_sequences=already_done` ao pipeline,
que em `core/pipeline.py:442` **filtra essas sequences antes de sintetizar**.
Chunk já pago nunca volta ao motor — inclusive quando o worker morre no meio do
livro (OS-022 retoma do primeiro chunk não persistido).

**Onde ainda se paga duas vezes:** reenviar o mesmo PDF gera `book_id` novo e
sintetiza tudo outra vez — não há dedup por hash (item 62 do backlog). E
`delete_book` apaga o áudio de verdade (`shutil.rmtree`), aí repetir é inevitável.

**O custo que realmente escala não é o motor, é o disco:** WAV 24 kHz mono 16 bit
= 47 KB/s → **165 MB por hora → 1,26 GB por livro** de 7,8 h. O motor é pago uma
vez; o disco é pago todo mês (item 61).

### 5.2 N+1 não existe — o que existe é outra coisa

Procurado e **não** encontrado: N+1 (`GET /books` é uma query e a lista renderiza
inteira a partir dela, sem requisição por livro), injeção de SQL (tudo
parametrizado; o f-string de `ensure_column` só recebe literais), XSS
(`label.textContent`, nunca `innerHTML`), path traversal (`book_id` é `uuid4()` do
servidor). Os índices são **adequados**: as PKs compostas `(book_id, sequence)` e
`(book_id, id)` cobrem exatamente as queries quentes.

Os três problemas reais, medidos:

| Achado | Medição |
|---|---|
| `journal_mode = delete`, não WAL | escritor e leitor se bloqueiam; worker escreve a cada ~1,3 s, API lê a cada 2 s |
| `chunks_done` faz `len(list_chunks(...))` | 533 objetos Pydantic para um inteiro: **1,33 ms vs 0,10 ms** de `COUNT(*)` — 13×, 1.800×/hora |
| `GET /audio` reenvia tudo a cada poll | **51,8 KB → 91 MB/hora** para um delta quase sempre de 0 ou 1 chunk |

Somando: cada função abre sua própria `sqlite3.connect()`, sem pool — um poll de
`/status` abre 2 conexões, servir um chunk abre 2. Irrelevante em SQLite local,
mas é o padrão que impede trocar para Postgres sem mexer na camada toda.

**Os três entraram no escopo da OS-057**, porque a linha de tempo contínua lê
`duration_seconds` de todos os chunks continuamente — não faz sentido construí-la
sobre um endpoint que já retransmite 91 MB/h.

### 5.3 Segurança: adequada para localhost, bloqueador para SaaS

**Não existe autenticação.** Nenhuma, e não há conceito de usuário (o mesmo
bloqueio que o item 59 registrou para o limiar por plano). Qualquer um que alcance
a porta lê e **deleta** qualquer `book_id`.

O mais grave dos dois: **`POST /books` dispara trabalho pago sem autenticação e
sem rate limit.** Depois das OS-055/056 esse endpoint gasta dinheiro real. A trava
da OS-042 protege contra *susto* (confirmação explícita, teto por livro), não
contra *abuso*.

Segundo: **o upload não valida nada.** `shutil.copyfileobj` escreve o que chegar,
sem limite de tamanho e sem checar magic bytes — o `accept="application/pdf"` do
HTML é dica de cliente. Um arquivo de 10 GB enche o disco antes de o PyMuPDF
reclamar.

Ponto positivo por omissão: **não há `CORSMiddleware`**, então nenhuma origem
externa chama a API pelo navegador. O default seguro está valendo de graça.

Nada disto entrou na OS-057 — é item 63 do backlog, e virar OS depende da decisão
de produto sobre usuários, que não existe ainda.
