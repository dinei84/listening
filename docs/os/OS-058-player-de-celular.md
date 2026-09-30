# OS-058 — Player de celular de verdade

## 1. Objetivo

Tornar o player utilizável no aparelho em que um audiobook é realmente ouvido:
controles na tela bloqueada, instalável, e layout desenhado para o polegar.

É a "OS-B" proposta em `docs/report/ESTUDO-UI-UX.md` e aprovada pelo dono em
28/09/2026 na ordem A → B → C. Fecha o achado 2.3 do estudo.

## 2. Escopo

### O problema, medido no estudo

Zero ocorrências de `mediaSession`, `MediaMetadata`, `manifest`,
`serviceWorker` e `prefers-color-scheme` em `player/`. **Zero `@media`** em 88
linhas de CSS com `max-width: 640px`.

O aparelho não está *quebrado* — 640px com `system-ui` degrada de forma
aceitável — mas nada ali foi decidido para ele. Um audiobook é ouvido caminhando,
no carro e dormindo: **exigir aba em primeiro plano para pausar é o que separa
demo de produto.**

### Alterados

- `player/nowplaying.js` — **novo**. Lógica pura do que aparece na tela
  bloqueada (título, capítulo, fallbacks), separada para ser testável fora do
  navegador, no mesmo molde do `timeline.js` da OS-057.
- `player/app.js` — ligar `mediaSession`: metadados e handlers de `play`,
  `pause`, `previoustrack`, `nexttrack`, `seekbackward`, `seekforward`,
  `seekto` e `positionstate`.
- `player/manifest.webmanifest` — **novo**. App instalável.
- `player/index.html` — `<link rel="manifest">`, `theme-color`, carregar o
  `nowplaying.js`.
- `player/style.css` — reescrita responsiva: mobile-first, breakpoints, alvos
  de toque, controles do player fixos no rodapé em tela estreita.
- Testes correspondentes.

### Decisão de layout, e por que não é roteamento de telas

O estudo registrou "separar 'ouvindo' de 'biblioteca'" como decisão a tomar
aqui. **Não vou introduzir troca de telas.** No celular o sintoma concreto é
rolar por três seções para alcançar o player; **controles fixos no rodapé**
resolvem exatamente isso, em CSS puro, sem estado de navegação novo, sem mexer
no `openBook`/`resetPlaybackState` e sem dobrar o tamanho do PR. Roteamento de
telas continua disponível como OS futura se o dono quiser, e esta OS não o
impede.

### Adição ao escopo da OS-B do estudo, declarada

**Modo escuro** (`prefers-color-scheme`) não estava na descrição da OS-B — é o
achado 2.5 do estudo. Entra aqui porque a folha de estilo está sendo reescrita
de qualquer forma, e fazer depois significa reescrevê-la duas vezes. O produto é
usado à noite. Vetável sem prejuízo do resto.

### Fora de escopo

- **Service worker e escuta offline.** Cache de app shell seria barato, mas o
  que interessa é áudio, e um livro ocupa **1,26 GB** (item 61). Offline de
  verdade depende da compressão daquele item.
- **`engine_used` na tela e detalhamento de custo.** É a OS-C.
- **Compressão (61), dedup (62), autenticação e rate limit (63).**
- **Roteamento de telas**, pelo motivo acima.
- **Ícones desenhados.** O manifest declara os ícones; produzir arte não é
  trabalho de agente de execução. Declarado no relatório se ficar pendente.

## 3. Contratos envolvidos

Nenhum contrato de plugin e **nenhuma rota de API** muda. Esta OS é inteiramente
`player/` — é a primeira OS do projeto que não toca Python de produção.

`player/nowplaying.js` segue o padrão do `timeline.js`: IIFE que exporta via
`module.exports` no Node e como global no navegador, testado com `node --test`
pela ponte já existente em `tests/unit/test_timeline_os057.py`.

## 4. Critérios de aceite

- [ ] `NowPlaying.build` monta título e capítulo para a tela bloqueada
- [ ] `NowPlaying.build` tem fallback quando não há capítulo detectado
- [ ] `NowPlaying.build` tem fallback quando o título do livro está vazio
- [ ] `NowPlaying.build` não expõe a extensão `.pdf` no título da tela bloqueada
- [ ] `mediaSession.metadata` é atualizado a cada troca de trecho
- [ ] Handlers de `play`, `pause`, `previoustrack` e `nexttrack` registrados
- [ ] `seekbackward`/`seekforward` usam os mesmos 15 s dos botões da tela
- [ ] `seekto` usa a posição **absoluta do livro** (a linha de tempo da OS-057), não a do trecho
- [ ] `setPositionState` reflete duração total e posição absoluta
- [ ] Nada quebra em navegador sem `mediaSession` (o recurso é opcional)
- [ ] `manifest.webmanifest` é servido, é JSON válido e tem `name`, `short_name`, `start_url`, `display`, `theme_color`
- [ ] `index.html` referencia o manifest e declara `theme-color`
- [ ] O CSS tem pelo menos um `@media` de largura e um de `prefers-color-scheme`
- [ ] Alvos de toque dos botões do player têm no mínimo 44px
- [ ] Em tela estreita, os controles do player ficam acessíveis sem rolar até o fim
- [ ] Nenhum teste existente quebra (429 hoje)

## 5. Testes exigidos (mínimo)

Node (`tests/player/nowplaying.test.js`):

- `build` com livro e capítulo completos
- `build` sem capítulo
- `build` com título vazio
- `build` removendo a extensão `.pdf`
- `build` com um capítulo só

pytest:

- `test_manifest_is_served_and_valid_json`
- `test_manifest_has_required_fields`
- `test_index_links_manifest_and_theme_color`
- `test_player_loads_nowplaying_before_app`
- `test_css_has_width_breakpoint`
- `test_css_has_dark_mode_query`
- `test_css_declares_touch_target_minimum`
- `test_app_registers_media_session_handlers`
- `test_app_guards_missing_media_session`

## 6. Relatório

Ver `docs/report/OS-058-report.md`.
