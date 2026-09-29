# OS-057 — Linha de tempo contínua do livro

## 1. Objetivo

Dar ao ouvinte a linha de tempo do **livro**, não do chunk: posição absoluta,
total, restante, scrub que atravessa fronteira de trecho e ±15 s — e tornar o
polling que a alimenta barato o bastante para sustentá-la.

É a "OS-A" proposta em `docs/report/ESTUDO-UI-UX.md` e aprovada pelo dono em
28/09/2026, com os três itens de banco/requisição da auditoria de 29/09/2026
(item 63 do backlog) incorporados ao escopo.

## 2. Escopo

### O problema, medido

`playChunk` faz `audioPlayer.src = chunks[index].url` e toca **um chunk por vez**,
então a régua nativa do `<audio controls>` cobre **um trecho**. Duração média real
no banco: **52,8 s**. Livro de 533 k chars ≈ 533 chunks ≈ **7,8 h**. A régua zera
533 vezes e não existe resposta para "quanto falta".

O dado necessário **já está no cliente**: `GET /books/{id}/audio` devolve
`duration_seconds` por chunk. A soma resolve posição absoluta, total e restante.

### Alterados

- `player/timeline.js` — **novo**. Matemática pura da linha de tempo, sem DOM:
  deslocamentos acumulados, mapeamento absoluto ↔ (trecho, offset), formatação.
  Separado de `app.js` exatamente para ser testável fora do navegador.
- `player/app.js` — consumir o `Timeline`, scrub absoluto, ±15 s, leitura de
  tempo, pré-carga do trecho seguinte, `?since=` no polling.
- `player/index.html` — barra de scrub, leitura de tempo, botões ±15 s, carregar
  `timeline.js` antes de `app.js`.
- `player/style.css` — estilo dos controles novos.
- `storage/audio_store.py` — `count_chunks()`; `since` em `list_chunks()`; WAL.
- `storage/db.py`, `storage/progress_store.py` — WAL.
- `api/routes_books.py` — `chunks_done` via `count_chunks()`.
- `api/routes_audio.py` — `?since=` em `GET /books/{id}/audio`.
- Testes correspondentes.

### Fora de escopo

- **`mediaSession`, manifest, breakpoints, modo escuro.** É a OS-B.
- **`engine_used` na tela e detalhamento de custo.** É a OS-C.
- **Compressão do áudio (item 61) e dedup por hash (item 62).**
- **Autenticação, rate limit e validação de upload (item 63).** Bloqueador
  pré-SaaS, mas depende de uma decisão de produto sobre usuários que não existe.
- **Gapless de verdade.** Exige `MediaSource`/Web Audio. Esta OS faz pré-carga,
  que aquece o cache e encurta a lacuna — não a elimina.
- **Adotar suíte de testes de browser.** Continua decisão aberta do dono.

## 3. Contratos envolvidos

Nenhum contrato de plugin muda — nada em `plugins/*/base.py` é tocado.

Duas mudanças de contrato de **API**, ambas retrocompatíveis:

| Endpoint | Mudança | Compatibilidade |
|---|---|---|
| `GET /books/{id}/audio` | aceita `?since=N`, devolve só `sequence > N` | sem o parâmetro, comportamento idêntico ao atual |
| `GET /books/{id}/status` | `chunks_done` passa a vir de `COUNT(*)` | mesmo valor, mesma chave |

`list_chunks(book_id, db_path=None, *, since=None)` — `since` é **keyword-only**
de propósito: `db_path` já é o segundo posicional em chamadas existentes.

### Decisão de tooling que o dono pode vetar

`player/timeline.js` é testado com `node --test` (embutido no Node, **nenhuma
dependência nova**) e ligado ao `pytest` por um teste que invoca o Node e
**pula com `skipif` quando o Node não existe**, para `pytest` seguir sendo o
portão único. Isto **não** é suíte de browser — são funções puras, sem DOM e sem
navegador, então a decisão aberta sobre Playwright continua intocada. Registrado
aqui porque é ferramenta nova no caminho de teste, conforme `AGENTS.md` seção 6.

### Tensão de escopo declarada

`AGENTS.md` seção 3 diz "uma OS = uma responsabilidade". O WAL é, a rigor,
**higiene de banco independente** da linha de tempo. Entra aqui porque a feature
aumenta a frequência de leitura sobre o mesmo banco que o worker escreve, e
entregar a linha de tempo sobre `journal_mode=delete` seria construir sobre um
lock conhecido. `COUNT(*)` e `?since=` são pré-requisito direto. Escopo aprovado
pelo dono em 29/09/2026.

## 4. Critérios de aceite

- [ ] `Timeline.build` devolve deslocamentos acumulados e total a partir de `duration_seconds`
- [ ] `Timeline.locate` mapeia segundo absoluto → (índice, offset no trecho), com fronteira exata caindo no trecho seguinte
- [ ] `Timeline.locate` satura nos dois extremos (negativo → 0; além do total → fim do último trecho)
- [ ] `Timeline.absolute` é o inverso de `locate`
- [ ] Livro sem chunks não quebra: total 0, índice 0
- [ ] `Timeline.format` produz `mm:ss` abaixo de 1 h e `h:mm:ss` acima
- [ ] A UI distingue **total do que está pronto** de **total previsto** enquanto a síntese não terminou — a linha de tempo não pode mentir
- [ ] Arrastar o scrub atravessa fronteira de trecho e troca a `src` quando necessário
- [ ] ±15 s atravessa fronteira de trecho
- [ ] O trecho seguinte é pré-carregado enquanto o corrente toca
- [ ] `GET /books/{id}/audio?since=N` devolve só `sequence > N`
- [ ] `GET /books/{id}/audio` sem `since` devolve tudo, como hoje
- [ ] `audio_store.count_chunks()` devolve a contagem sem materializar os chunks
- [ ] `chunks_done` em `GET /status` usa `count_chunks()`
- [ ] Os três bancos abrem em `journal_mode=wal`
- [ ] WAL é idempotente: banco já em WAL não é alterado, banco antigo migra no lugar
- [ ] Nenhum dos sete comportamentos preservados (seção 3 do estudo) regride
- [ ] Nenhum teste existente quebra (401 hoje)

## 5. Testes exigidos (mínimo)

Node (`tests/player/timeline.test.js`):

- `build` com lista vazia, um chunk, vários
- `locate` no início, no meio, na fronteira exata, além do fim, negativo
- `absolute` como inverso de `locate`
- `format` abaixo e acima de 1 h
- `remaining` nunca negativo

pytest:

- `test_timeline_js_unit_tests_pass` (invoca `node --test`, pula sem Node)
- `test_audio_store_count_chunks_does_not_materialize`
- `test_count_chunks_matches_list_chunks_length`
- `test_list_chunks_since_returns_only_newer`
- `test_list_chunks_without_since_returns_all`
- `test_status_chunks_done_uses_count`
- `test_audio_endpoint_since_filters`
- `test_audio_endpoint_without_since_unchanged`
- `test_db_opens_in_wal_mode`
- `test_wal_is_idempotent_on_existing_db`
- `test_player_has_scrub_and_time_readout`
- `test_player_loads_timeline_before_app`

## 6. Relatório

Ver `docs/report/OS-057-report.md`.
