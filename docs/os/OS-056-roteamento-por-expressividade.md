# OS-056 — Roteamento por expressividade dentro do chunk

## 1. Objetivo

Dentro de cada chunk, mandar **só as frases com `!` ou `?`** para o motor caro, sintetizar o resto no Kokoro e devolver tudo concatenado no mesmo `AudioChunk`. Entrega a qualidade do motor pago nos trechos que importam, pagando por ~9% do livro.

## 2. Depende da OS-055

Sem um segundo `Speaker` registrado não há para onde rotear. A OS-055 entrega o `OpenAISpeaker`; esta usa.

## 3. Números medidos que sustentam a decisão

| | |
|---|---|
| Frases com `!` ou `?` em prosa técnica real | **9,1%** (211 de 2.327, capítulos 1–4 do "Programador Pragmático") |
| Livro inteiro na OpenAI | US$ 8,58 |
| **Roteando por frase (9,1%)** | **US$ 0,78** |
| Roteando por chunk (1000 chars) | US$ 3,42 — amplificação de 8 a 9,6× |

**Rotear por frase é obrigatório.** Um chunk de 1000 caracteres tem ~10 frases, e um único `?` mandaria as dez para o motor pago.

## 4. Escopo

Alterados:

- `core/pipeline.py` — roteamento por frase dentro do chunk e concatenação.
- `core/config.py` e `config.yaml` — bloco do roteamento.
- Testes correspondentes.

Fora de escopo:

- **Estilo/instrução diferente por tipo de frase.** Esta OS roteia; calibrar o `instructions` por tipo é ajuste posterior.
- **Roteamento por outro critério** (frase longa, diálogo). Só `!` e `?` nesta OS.
- **Casar timbre entre os motores.** Ver seção 6 — é o risco aceito.

## 5. Desenho — decisão do dono, validada por medição

O desenho original roteava **frase a frase**. O dono propôs outro, depois de ouvir o efeito das pausas num texto de frases curtas: **contar as frases expressivas do chunk e, se passarem de um limiar, mandar o chunk INTEIRO para o motor pago** — em vez de alternar dentro dele.

Medido em 230 chunks reais (páginas 24–140 do "Programador Pragmático", 216.365 caracteres):

| Limiar | Chunks marcados | % do livro no pago | **Trocas de motor** | US$/livro |
|---|---|---|---|---|
| 1 | 85 | 37,1% | 86 | 3,19 |
| 2 | 44 | 19,2% | 56 | 1,65 |
| **3** | 21 | **9,2%** | **32** | **0,79** |
| 4 | 14 | 6,1% | 25 | 0,53 |
| 5 | 10 | 4,3% | 17 | 0,37 |
| *(por frase)* | — | *9,0%* | *~374* | *0,78* |

**O limiar 3 entrega a mesma cobertura e o mesmo custo do roteamento por frase, com 12× menos trocas.** É o padrão adotado, configurável.

Duas consequências que tornam este desenho superior ao original:

- **A troca cai em fronteira de chunk**, que já tem pausa de parágrafo ou de frase. Trocar de voz num silêncio é muito menos perceptível que trocar no meio da prosa.
- **Não há concatenação de motores diferentes dentro de um `AudioChunk`.** Cada chunk tem um motor só, então some o problema de casar volume e taxa de amostragem no meio do áudio — o `_merge_wav_files` continua juntando pedaços de um mesmo motor, como já fazia.

**Custo do trade-off, declarado:** uma pergunta isolada num chunk de prosa (abaixo do limiar) continua no motor local, sem melhoria. É deliberado — melhorar essa frase custaria uma troca de timbre que o dono já constatou ser pior que o defeito.

## 7. Critérios de aceite

- [ ] Chunk com **≥ limiar** frases expressivas vai inteiro para o Speaker pago
- [ ] Chunk abaixo do limiar vai inteiro para o Speaker local
- [ ] O limiar é configurável, com padrão 3
- [ ] Nenhum `AudioChunk` mistura motores — cada um tem um `engine_used` só
- [ ] `AudioChunk.engine_used` reflete o motor realmente usado naquele chunk
- [ ] Roteamento desligado (padrão) não muda absolutamente nada
- [ ] A estimativa da OS-042 conta **só a fração roteada**, não o livro inteiro
- [ ] Falha do motor pago num chunk degrada **aquele chunk** para o local, sem derrubar o livro
- [ ] As pausas da OS-045 seguem valendo dentro de cada chunk
- [ ] Uma amostra de áudio de parágrafo real é gerada e anexada ao relatório
- [ ] Nenhum teste existente quebra

## 8. Testes exigidos (mínimo)

- `test_chunk_above_threshold_goes_to_premium_speaker`
- `test_chunk_below_threshold_goes_to_local_speaker`
- `test_threshold_is_configurable`
- `test_audio_chunk_records_engine_actually_used`
- `test_routing_disabled_changes_nothing`
- `test_estimate_counts_only_routed_chunks`
- `test_premium_failure_degrades_chunk_to_local`
- `test_no_audio_chunk_mixes_engines`

## 9. Relatório

Ver `docs/report/OS-056-report.md`.
