# OS-058 — Relatório de entrega

**Data:** 29/09/2026
**Branch:** `os/058-player-de-celular`
**Commit(s) relevante(s):** `ae726ba` (OS), `a125a90` (Red), `adeb731` (Green)

## 1. Resumo do que foi feito

O player ganhou controle de tela bloqueada (`mediaSession` com os sete
handlers), virou instalável (`manifest.webmanifest`) e teve a folha de estilo
reescrita para o aparelho em que um audiobook é de fato ouvido: mobile-first,
alvos de toque de 44px, modo escuro e controles fixos no rodapé em tela estreita.

## 2. Checklist de DoD

### Padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit Red `a125a90` precede o Green `adeb731`
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 429 → **452 passando**
- [x] Código segue os contratos de `ARQUITETURA.md` — **nenhum arquivo Python de produção foi tocado**
- [x] Nenhuma chamada real a API paga nos testes — esta OS não toca Speaker nem normalizador
- [x] Type hints e docstring — **não se aplica a Python** (a OS é inteiramente `player/`); as funções do `nowplaying.js` têm JSDoc
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-058-report.md`
- [x] PR aberto com título `[OS-058] ...`

### Específico (seção 4 da OS)

- [x] `NowPlaying.build` monta título e capítulo
- [x] Fallback sem capítulo detectado → `"Trecho 6 de 533"`
- [x] Fallback com título vazio → `"Audiobook"`
- [x] Não expõe `.pdf` — e só a extensão final (`"guia.pdf.para.iniciantes.pdf"` → `"guia.pdf.para.iniciantes"`)
- [x] `mediaSession.metadata` atualizado a cada troca de trecho (chamada no fim do `playChunk`)
- [x] Handlers de `play`, `pause`, `previoustrack`, `nexttrack` registrados
- [x] `seekbackward`/`seekforward` usam os mesmos `SKIP_SECONDS` dos botões
- [x] `seekto` usa a posição **absoluta do livro** — entra pelo mesmo `seekAbsolute` dos botões
- [x] `setPositionState` reflete duração total e posição absoluta — **medido: 105,64 s (livro) contra 80,43 s (trecho corrente)**
- [x] Nada quebra sem `mediaSession` — `temMediaSession()` guarda todo acesso, e cada `setActionHandler` está em `try`
- [x] `manifest.webmanifest` servido, JSON válido, com os cinco campos
- [x] `index.html` referencia manifest e `theme-color`
- [x] CSS com `@media` de largura e de `prefers-color-scheme`
- [x] Alvos de toque ≥ 44px — **medido: os cinco botões e o scrub em exatamente 44px**
- [x] Controles acessíveis sem rolar até o fim — **corrigido durante a execução, ver seção 5**
- [x] Nenhum teste existente quebra

## 3. Testes escritos

23 novos (7 em Node, 16 em pytest).

| Teste | Arquivo | Passou? |
|---|---|---|
| `build` completo / sem capítulo / capítulo sem título / um capítulo só | `tests/player/nowplaying.test.js` | ✅ |
| `build` remove `.pdf` (minúsculo, maiúsculo, só o final) | `tests/player/nowplaying.test.js` | ✅ |
| `build` com título vazio / sem argumento nenhum | `tests/player/nowplaying.test.js` | ✅ |
| manifest servido e JSON válido / 5 campos obrigatórios / `display: standalone` | `tests/integration/test_mobile_os058.py` | ✅ |
| `index.html` com manifest e `theme-color` | `tests/integration/test_mobile_os058.py` | ✅ |
| `nowplaying.js` servido e carregado antes do `app.js` | `tests/integration/test_mobile_os058.py` | ✅ |
| os 7 handlers de `mediaSession` / `setPositionState` / guarda de ausência | `tests/integration/test_mobile_os058.py` | ✅ |
| CSS: breakpoint de largura / modo escuro / 44px / controles fixos | `tests/integration/test_mobile_os058.py` | ✅ |

Commit "Red" antes do "Green"? **[x] Sim** — `a125a90` (23 falhas em pytest, 1 em Node) precede `adeb731`.

## 4. Saída de comandos relevantes

### Suíte completa

```
452 passed, 2 warnings in 15.79s
```

### Lint

```
All checks passed!     (tests/ storage/ api/)
```

### Verificação em navegador real, a 375×812 (preset de celular)

`mediaSession` — o que o navegador **de fato aceitou registrar**, lido de
`registeredMediaActions`, não do código-fonte:

```
acoesRegistradas: ["play", "pause", "previoustrack", "nexttrack",
                   "seekbackward", "seekforward", "seekto"]
playbackState:    "playing"
metadata: { title: "Parte 1", artist: "teste-expressividade2", album: "" }
```

O `artist` confirma a remoção do `.pdf` no caminho real, e o `album` vazio
confirma a supressão de "Capítulo 1 de 1" — o livro de teste tem um capítulo só.

A barra da tela bloqueada anuncia o **livro**, não o trecho (tudo lido no mesmo
instante, com o trecho 0 carregado):

```
duracaoDoTrechoCorrente_audioElement: 80.43
duracaoAnunciadaAoSistema:           105.64
totalDoLivro:                        105.64
veredito: "anuncia o LIVRO (correto)"
```

Layout a 375px:

```
alvosDeToque: prev-btn 44 · back-15-btn 44 · play-pause-btn 44 ·
              forward-15-btn 44 · next-btn 44
scrubAltura:  44
semRolagemHorizontal: true
```

Controles fixos, com a página **no topo** (é onde fica o formulário de upload):

```
scrollY: 0 · alturaViewport: 836
controlesTopo: 663 · controlesBase: 836
playVisivelComPaginaNoTopo: true
position: "fixed"
```

A barra fixa não esconde conteúdo de forma permanente — no fim da página, o
último elemento fica acima dela:

```
baseDoUltimoConteudo: 643 · topoDaBarraFixa: 663
conteudoNaoFicaEscondido: true
```

Modo escuro seguindo o sistema:

```
escuro: true
fundoBody: rgb(21, 22, 26) · corTexto: rgb(233, 233, 236)
```

Acima do breakpoint (1024px), a barra volta ao fluxo:

```
positionNoDesktop: "static"
larguraMaximaDoCorpo: "640px"
paddingInferior: "32px"
veredito: "volta ao fluxo no desktop (correto)"
```

## 5. Desvios do escopo original

**Um defeito meu, encontrado na verificação e corrigido.** Os controles fixos
foram implementados com `position: sticky; bottom: 0`, e o teste
`test_css_pins_player_controls_on_narrow_screens` — que aceitava "sticky **ou**
fixed" — passou. Mas `sticky` só segura o elemento na tela **depois** que a
rolagem passa pela posição natural dele; não o traz para a vista antes. Medido a
375px com a página no topo: os controles ficavam em **y=981 numa viewport de
836px**, ou seja fora da tela — exatamente o problema que a regra existia para
resolver. O critério de aceite **não estava cumprido com o teste passando**.

Corrigido para `position: fixed`, e o teste foi **endurecido** para exigir
`fixed` e rejeitar `sticky`. É o segundo teste desta série (o primeiro foi o de
concorrência do WAL, na OS-057) que passava sem provar o que afirmava.

**Dois testes meus estavam frágeis e foram ajustados antes do Green:**

1. `test_player_loads_nowplaying_before_app` comparava `html.index("app.js")`, e
   casava com um **comentário** acima das tags que cita "app.js" — falhava com a
   ordem correta na tela. Passou a procurar `src="app.js"`.
2. `test_app_registers_media_session_handler` exigia `setActionHandler("play"`,
   o que fixaria a **forma** do código (uma chamada literal por ação) e
   reprovaria um laço sobre a lista de ações, que é o código melhor. Afrouxado
   de propósito, com a prova real transferida para a verificação em navegador —
   por isso o `app.js` publica `registeredMediaActions`.

**`player/icon.svg` foi criado, e não estava na lista da seção 2.** A OS declarou
ícones fora de escopo ("produzir arte não é trabalho de agente de execução"), mas
um manifest apontando para um 404 quebra a instalação. O arquivo é um marcador
geométrico (retângulo, dois arcos), não arte, e está comentado como provisório.
Trocar por arte de verdade continua sendo decisão do dono.

**Modo escuro** entrou como declarado na seção 2 da OS: não estava na descrição
da OS-B no estudo, e foi incluído porque a folha de estilo estava sendo
reescrita de qualquer forma.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Três observações:

1. **A tela bloqueada de verdade não foi testada.** A verificação rodou em
   navegador desktop com viewport emulada: prova que os handlers são aceitos, que
   os metadados estão certos e que a duração anunciada é a do livro — mas **não**
   prova como Android ou iOS desenham isso na tela de bloqueio, nem se o áudio
   continua com a tela apagada (o que depende também de política de energia do
   aparelho). Isso só o dono consegue verificar, com o telefone.

2. **`display: standalone` sozinho não instala no iOS.** O Safari exige
   "Adicionar à Tela de Início" manual e ignora parte do manifest; as meta
   `apple-mobile-web-app-*` foram incluídas para cobrir o que ele lê. Não
   verificado em aparelho Apple.

3. **Offline continua fora.** Cache de app shell seria barato, mas o que
   interessa num audiobook é o áudio, e um livro ocupa **1,26 GB** (item 61 do
   backlog). Escuta offline de verdade depende da compressão daquele item — é a
   dependência que faz o item 61 valer mais do que "economizar disco".

## 7. Link do PR

Ver o PR aberto contra `main` com título `[OS-058] Player de celular de verdade`.
