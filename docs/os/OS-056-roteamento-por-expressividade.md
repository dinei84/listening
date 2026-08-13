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

## 5. Desenho

O ponto de corte já existe: `_split_into_pause_segments` (OS-045) divide o chunk em frases e devolve `(texto, pausa_ms)`. O roteamento decide o Speaker **por segmento**, sintetiza cada um e concatena — que é o que o `KokoroSpeaker` já faz internamente com os seus pedaços.

Duas restrições que a implementação precisa respeitar:

**Taxa de amostragem.** Kokoro entrega 24 kHz. A OpenAI também, no formato `wav` — verificado no spike (o arquivo medido tinha `sr=24000`). Se um motor futuro divergir, o áudio precisa ser reamostrado antes de concatenar, senão a velocidade muda no meio da frase.

**Casamento de volume.** Motores diferentes têm loudness diferente, e o ouvinte percebe salto de volume antes de perceber troca de voz. A concatenação precisa normalizar — RMS é suficiente e não exige dependência nova.

## 6. O risco aceito, declarado

Motores diferentes têm **vozes diferentes**. Estimadas ~506 trocas de timbre por livro roteando por frase. O dono decidiu seguir mesmo assim, com o argumento de que os poucos momentos ruins pesam mais na experiência do que a média sugere — e a estimativa de que soaria mal **nunca foi verificada de ouvido**, é suposição registrada como tal.

**Esta OS deve produzir uma amostra audível** de um parágrafo real com roteamento ativo, antes de qualquer conclusão sobre o resultado. Se a descontinuidade incomodar, a alternativa já estudada é o item 55: trocar **estilo** dentro de um motor só, sem trocar de voz.

## 7. Critérios de aceite

- [ ] Frase com `?` ou `!` vai para o Speaker caro; as demais vão para o barato
- [ ] O chunk devolvido é **um** `AudioChunk`, com a mesma granularidade de sempre
- [ ] A ordem das frases é preservada na concatenação
- [ ] As pausas da OS-045 continuam entre os segmentos, venham de qual motor vierem
- [ ] O volume é normalizado entre segmentos de motores diferentes
- [ ] Roteamento desligado (padrão) não muda absolutamente nada
- [ ] A estimativa da OS-042 reflete só a fração roteada, não o livro inteiro
- [ ] Falha do motor caro num segmento degrada **aquele segmento** para o barato, sem derrubar o livro
- [ ] Uma amostra de áudio de parágrafo real é gerada e anexada ao relatório
- [ ] Nenhum teste existente quebra

## 8. Testes exigidos (mínimo)

- `test_routes_expressive_sentence_to_premium_speaker`
- `test_routes_plain_sentence_to_local_speaker`
- `test_preserves_sentence_order_in_concatenation`
- `test_keeps_single_audio_chunk_per_text_chunk`
- `test_keeps_os045_pauses_between_routed_segments`
- `test_normalizes_volume_across_engines`
- `test_routing_disabled_changes_nothing`
- `test_estimate_counts_only_routed_fraction`
- `test_premium_failure_degrades_that_segment_to_local`

## 9. Relatório

Ver `docs/report/OS-056-report.md`.
