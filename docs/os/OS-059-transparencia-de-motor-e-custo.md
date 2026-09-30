# OS-059 — Transparência de motor e de custo

## 1. Objetivo

Tornar visível qual motor narrou cada trecho e quanto do livro vai para a voz
paga — hoje o app decide as duas coisas e não conta nenhuma delas ao usuário.

É a "OS-C" proposta em `docs/report/ESTUDO-UI-UX.md` e aprovada pelo dono em
28/09/2026 na ordem A → B → C. Fecha o achado 2.4 do estudo e a queixa sobre a
confirmação de custo.

## 2. Escopo

### O problema

`AudioChunk.engine_used` é gravado desde sempre (`"kokoro"` / `"openai"`), mas
**não aparece no payload de `/books/{id}/audio` nem em lugar nenhum da tela.**

Foi exatamente a dúvida do dono em 13/08/2026: *"não consegui investigar se
realmente está consumindo da API key"*. A pergunta era de UI, não de backend — e
depois das OS-055/056 o roteamento por expressividade é **o diferencial do
produto**, decidido a cada chunk, sem nenhuma superfície que o mostre.

Do lado do custo, a estimativa **já** considera o roteamento (OS-056,
`core/pipeline.py:238`): cada chunk é cobrado pelo motor que de fato vai
sintetizá-lo. O que falta é a **divisão**. Hoje o banner diz "este livro deve
custar US$ 0,85" e cala sobre o que sustenta esse número — quantos trechos vão
para o pago, quantos ficam no local, e que o local não custa nada. Sem isso, o
usuário confirma um número sem entender de onde ele vem, e as opções são
confirmar ou deletar.

### Alterados

- `core/pipeline.py` — `estimate_breakdown()` devolvendo a divisão;
  `estimate_cost()` passa a delegar para ele (assinatura e valor **inalterados**).
- `core/models.py` — campos da divisão em `Book`.
- `storage/db.py` — colunas novas via `ensure_column` (padrão da OS-052) e setter.
- `worker/tasks.py` — persistir a divisão junto com a estimativa.
- `api/routes_books.py` — expor a divisão em `GET /books/{id}/status`.
- `api/routes_audio.py` — `engine_used` no payload de `/books/{id}/audio`.
- `player/engines.js` — **novo**. Nome humano do motor e resumo por trecho,
  puro e testável fora do navegador, no molde do `timeline.js` e do
  `nowplaying.js`.
- `player/app.js`, `player/index.html`, `player/style.css` — marca de motor no
  trecho corrente, resumo do livro e banner de confirmação detalhado.
- Testes correspondentes.

### Fora de escopo

- **Custo real medido após a síntese.** Tentador, e não dá para fazer honesto:
  o número de caracteres por chunk não é persistido, então o custo real só sairia
  de estimativa sobre duração. O que **é** exato depois da síntese é a **contagem
  de trechos por motor**, e é isso que a tela mostra.
- **Escolher o limiar por livro na hora de confirmar.** O limiar é global, vindo
  do `config.yaml`; torná-lo por livro é o item 59 do backlog e depende de um
  conceito de usuário que não existe.
- **Recalibrar o `cost_per_char` da OpenAI.** Continua derivado de uma amostra de
  933 caracteres; recalibrar depois de um livro inteiro é item à parte.
- **Compressão (61), dedup (62), autenticação e rate limit (63).**

## 3. Contratos envolvidos

Nenhum contrato de plugin muda.

| Alvo | Mudança | Compatibilidade |
|---|---|---|
| `GET /books/{id}/audio` | ganha `engine_used` em cada item | campo novo; nada some |
| `GET /books/{id}/status` | ganha a divisão da estimativa | campos novos; nada some |
| `pipeline.estimate_cost` | passa a delegar para `estimate_breakdown` | **assinatura e valor idênticos** |
| tabela `books` | 3 colunas novas | `ensure_column`, banco antigo migra no lugar |

O valor devolvido por `estimate_cost` **não pode mudar** — a trava de custo da
OS-042 e o teto `max_cost_per_book` dependem dele, e um teste desta OS trava isso.

## 4. Critérios de aceite

- [ ] `estimate_breakdown` devolve custo total, custo do pago, custo do local, trechos no pago e trechos no total
- [ ] `estimate_breakdown().total` é **exatamente** o que `estimate_cost` devolvia
- [ ] Com roteamento desligado, a divisão põe tudo no motor configurado e zero no pago
- [ ] Com roteamento ligado, só os chunks acima do limiar contam como pagos
- [ ] O custo do normalizador entra no total mas **não** é atribuído a nenhum dos dois motores
- [ ] A divisão é persistida junto com a estimativa, antes de `pending_confirmation`
- [ ] `GET /status` expõe a divisão
- [ ] `GET /audio` expõe `engine_used` por trecho
- [ ] `Engines.label` dá nome humano a `kokoro` e `openai`
- [ ] `Engines.label` não imprime "undefined" para motor desconhecido
- [ ] `Engines.summarize` conta trechos por motor e ignora lista vazia
- [ ] O trecho corrente mostra qual motor o narrou
- [ ] O banner de confirmação mostra a divisão, e diz que o local não custa nada
- [ ] Livro sem roteamento não ganha ruído de "0 trechos premium" na tela
- [ ] Nenhum teste existente quebra (452 hoje)

## 5. Testes exigidos (mínimo)

Node (`tests/player/engines.test.js`):

- `label` para `kokoro`, `openai`, desconhecido, vazio/nulo
- `summarize` de lista vazia, de um motor só, de dois motores
- `summarize` preserva a ordem por contagem

pytest:

- `test_estimate_breakdown_total_matches_estimate_cost`
- `test_breakdown_without_routing_puts_everything_on_configured_speaker`
- `test_breakdown_with_routing_splits_by_threshold`
- `test_breakdown_normalizer_cost_is_not_attributed_to_an_engine`
- `test_worker_persists_breakdown_before_pending_confirmation`
- `test_status_exposes_cost_breakdown`
- `test_audio_endpoint_exposes_engine_used`
- `test_db_migrates_breakdown_columns_on_existing_database`
- `test_player_shows_engine_of_current_chunk`
- `test_player_confirmation_banner_shows_split`

## 6. Relatório

Ver `docs/report/OS-059-report.md`.
