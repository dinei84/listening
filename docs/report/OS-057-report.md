# OS-057 — Relatório de entrega

**Data:** 29/09/2026
**Branch:** `os/057-linha-de-tempo-continua`
**Commit(s) relevante(s):** `f7a980c` (OS + backlog), `90f42b5` (Red), `d73e7e6` (Green)

## 1. Resumo do que foi feito

A régua do player passou a ser a do **livro**, não a do trecho: posição
absoluta, total, restante, scrub que atravessa fronteira de chunk e ±15 s,
somando os `duration_seconds` que o servidor já mandava. Junto, os três achados
medidos da auditoria de 29/09/2026 que sustentam esse polling: WAL nos três
stores, `chunks_done` por `COUNT(*)` e `?since=` no `/audio`.

## 2. Checklist de DoD

### Padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit Red `90f42b5` precede o Green `d73e7e6`
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 401 → **429 passando**
- [x] Código segue os contratos de `ARQUITETURA.md` — nenhum `base.py` de plugin foi tocado
- [x] Nenhuma chamada real a API paga nos testes — esta OS não toca Speaker nem normalizador
- [x] Type hints e docstring de uma linha em toda função pública (Python); JSDoc nas funções do `timeline.js`
- [x] `PROJECT_STATE.md` atualizado — itens 61, 62, 63 registrados e item 60 fechado
- [x] Relatório criado em `docs/report/OS-057-report.md`
- [x] PR aberto com título `[OS-057] ...`

### Específico (seção 4 da OS)

- [x] `Timeline.build` devolve deslocamentos acumulados e total
- [x] `Timeline.locate` mapeia absoluto → (índice, offset), fronteira exata no trecho que começa ali
- [x] `Timeline.locate` satura nos dois extremos
- [x] `Timeline.absolute` é o inverso de `locate`
- [x] Livro sem chunks não quebra
- [x] `Timeline.format` produz `mm:ss` e `h:mm:ss`
- [x] A UI distingue total pronto de total previsto — verificado no navegador: `"0:01 / 1:45 -1:44 do que está pronto (2 de 533 trechos)"`
- [x] Arrastar o scrub atravessa fronteira e troca a `src` — verificado: 90 s → trecho 1, offset 9,57
- [x] ±15 s atravessa fronteira — verificado: −15 s de 90 s volta ao trecho 0
- [x] Trecho seguinte é pré-carregado — verificado: `preloader.dataset.url` aponta para o chunk 1 assim que o 0 começa
- [x] `GET /audio?since=N` devolve só `sequence > N`
- [x] `GET /audio` sem `since` devolve tudo
- [x] `count_chunks()` conta sem materializar — teste monkeypatcha `AudioChunk` para explodir se for construído
- [x] `chunks_done` usa `count_chunks()` — teste monkeypatcha `list_chunks` para explodir
- [x] Os três bancos abrem em `journal_mode=wal`
- [x] WAL é idempotente e migra banco antigo no lugar
- [x] Nenhum dos sete comportamentos preservados regride — ver seção 4
- [x] Nenhum teste existente quebra

## 3. Testes escritos

28 testes novos (16 + 3 em Node, 9 em pytest unit, 13 em pytest integration —
somando 41 asserções de caso; a contagem de funções de teste é a da tabela).

| Teste | Arquivo | Passou? |
|---|---|---|
| `build` acumula deslocamentos / lista vazia / um chunk / duração inválida | `tests/player/timeline.test.js` | ✅ |
| `locate` começo / meio / fronteira exata / satura fim / satura começo / vazia | `tests/player/timeline.test.js` | ✅ |
| `absolute` inverso de `locate` / índice fora da faixa | `tests/player/timeline.test.js` | ✅ |
| `format` mm:ss / h:mm:ss / fração e entrada inválida | `tests/player/timeline.test.js` | ✅ |
| `remaining` nunca negativo | `tests/player/timeline.test.js` | ✅ |
| `nextSince` vazio / contíguo / com buraco | `tests/player/timeline.test.js` | ✅ |
| `count_chunks` bate com `len(list_chunks)` / zero para livro desconhecido / não materializa | `tests/unit/test_timeline_os057.py` | ✅ |
| `list_chunks` `since` exclusivo / sem `since` / `since=None` / keyword-only | `tests/unit/test_timeline_os057.py` | ✅ |
| WAL nos três stores / migra banco em `delete` / idempotente / leitor não bloqueia | `tests/unit/test_timeline_os057.py` | ✅ |
| ponte `node --test` a partir do pytest | `tests/unit/test_timeline_os057.py` | ✅ |
| `/audio` sem `since` / com `since` / no topo / forma do payload / `since` negativo 422 / 404 | `tests/integration/test_timeline_os057.py` | ✅ |
| `chunks_done` via `COUNT(*)` / zero sem áudio | `tests/integration/test_timeline_os057.py` | ✅ |
| HTML: ordem dos scripts / módulo servido / scrub e leitura / ±15 s / sem `controls` | `tests/integration/test_timeline_os057.py` | ✅ |

Commit "Red" antes do "Green"? **[x] Sim** — `90f42b5` (13 falhas em unit, 9 em
integration, 16 em Node) precede `d73e7e6`.

## 4. Saída de comandos relevantes

### Suíte completa

```
429 passed, 2 warnings in 15.11s
```

### Testes de matemática em Node

```
ℹ tests 19
ℹ pass 19
ℹ fail 0
```

### Verificação em navegador real (API em `localhost:8000`, livro `ready` de 2 trechos)

Linha de tempo montada a partir do payload real:

```
chunks: 2
offsets: [0, 80.42579166666667]
timelineTotal: 105.63666666666667
scrubMax: "105.63666666666667"
audioTemControlsNativos: false
preloaderUrl: "/books/2cfe9a63-.../audio/1"
readout: "0:00 / 1:45 -1:45"
```

Travessia de fronteira, ida e volta, e saturação:

| Ação | Trecho | `src` | `currentTime` | Absoluto | Leitura |
|---|---|---|---|---|---|
| início | 0 | — | 0 | 0 | `0:00 / 1:45 -1:45` |
| scrub → 90 s | **1** | `/audio/1` | 9,57 | 90,00 | `1:29 / 1:45 -0:15` |
| −15 s | **0** | `/audio/0` | 75,00 | 75,00 | `1:14 / 1:45 -0:30` |
| +15 s | **1** | `/audio/1` | 9,57 | 90,00 | `1:29 / 1:45 -0:15` |
| scrub → 9999 s | 1 | `/audio/1` | 25,17 | 105,60 | `1:45 / 1:45 -0:00` |

Estado pausado e `?since=` na rede:

```
pausadoAntesDoScrub: true
continuaPausadoDepois: true      <- arrastar com o áudio pausado não faz tocar
urlDoPolling: ["/books/2cfe9a63-.../audio?since=1"]
tocandoDeVerdade: true
currentTimeApos1500ms: 1.24
indicadorDePosicao: "Capítulo 1 de 1 — Parte 1 · trecho 1 de 2"
```

Síntese incompleta (a linha de tempo não pode mentir):

```
comSinteseIncompleta: "0:01 / 1:45 -1:44 do que está pronto (2 de 533 trechos)"
comLivroCompleto:     "0:01 / 1:45 -1:44"
```

### Sete comportamentos preservados (seção 3 do estudo)

Tocar antes de `ready` (OS-030), `waitingForNextChunk`, retomada com fonte no
servidor (OS-028), throttle de gravação, limiar de 3 s do "anterior" (OS-039),
aviso de worker (OS-051) e `mergeChunks` sem reiniciar a reprodução: nenhum
deles foi alterado, e os testes que os cobrem continuam passando dentro dos 429.
O banner "Retomar de onde parou?" apareceu no navegador durante a verificação,
confirmando a OS-028 de ponta a ponta.

### Lint

```
All checks passed!     (tests/ storage/ api/ player/)
```

Os 5 erros restantes do `ruff check .` são **pré-existentes**, todos em
`scripts/spike_ocr_confidence.py` e `scripts/validate_normalizer.py`, arquivos
que esta OS não toca.

## 5. Desvios do escopo original

Três, todos pequenos e declarados:

1. **`Timeline.nextSince` não estava na lista de funções da OS.** Apareceu ao
   escrever o `app.js`: `worker/tasks.py::_resume_inconsistency` só compara a
   MAIOR sequence com o total e **não impede buraco na faixa**, então mandar
   `since = maior sequence conhecida` perderia para sempre os trechos de um
   eventual buraco. A função só devolve número quando a faixa é contígua desde
   0; caso contrário pede o payload cheio. Entrou com teste próprio (Red antes
   do Green, dentro do mesmo ciclo).

2. **`playChunk` ganhou o parâmetro `autoplay`.** Sem ele, arrastar a barra com o
   áudio pausado começaria a tocar sozinho. Padrão `true`, então navegação por
   trecho, retomada e fim de trecho seguem idênticas.

3. **Rótulos dos botões revertidos.** Cheguei a renomear "◀ Anterior"/"Próximo ▶"
   para "◀ Trecho"/"Trecho ▶" (ambiguidade com os novos ±15 s), e isso quebrou
   `test_player_has_prev_and_next_buttons`, da OS-039. Como a renomeação era
   escolha cosmética minha e **não estava no escopo**, revertida — o teste
   existente voltou a passar sem ser alterado. Se o rótulo incomodar na escuta,
   é assunto da OS-B, que trata layout.

O `enable_wal` foi colocado em `storage/db.py` e importado pelos outros dois
stores, seguindo o precedente do `ensure_column` (OS-052), que já vive lá no
mesmo papel de helper compartilhado de schema. Nenhum módulo novo foi criado
fora dos listados na seção 2 da OS, além do `player/timeline.js`, que estava
previsto.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Três observações para o dono, nenhuma exigindo decisão agora:

1. **`node --test` entrou no caminho de teste.** Está declarado na seção 3 da OS
   e é vetável. Nenhuma dependência nova (é embutido no Node) e nenhum browser —
   são funções puras. O pytest segue sendo o portão único, com `skipif` quando o
   Node não existe. A decisão aberta sobre adotar Playwright **continua
   intocada**. Detalhe encontrado na execução: `node --test <diretório>` não é
   suportado nesta versão (v24 tenta carregar o diretório como módulo); a ponte
   descobre os arquivos e passa um a um.

2. **A leitura de tempo mostra `1:29` ao pular para 1:30.** Não é erro de
   cálculo: o navegador encaixa `currentTime` no frame decodável mais próximo e o
   absoluto fica em `89,99999966…`; `Math.floor` — a convenção de todo tocador,
   e o que os testes fixam — dá 89. Só aparece em pulo para segundo exato.

3. **A pré-carga encurta a lacuna entre trechos, não a elimina.** O `<audio>`
   oculto aquece o cache do navegador, então o `load()` seguinte responde do
   cache em vez da rede; o `FileResponse` manda `etag`/`last-modified` mas não
   `Cache-Control`, então o cache é heurístico. Gapless de verdade exige
   `MediaSource`/Web Audio e está declarado fora do escopo. **Não medi o tamanho
   da lacuna antes e depois** — afirmar redução medida seria asserção sem
   medição.

## 7. Link do PR

Ver o PR aberto contra `main` com título `[OS-057] Linha de tempo contínua do livro`.
