# OS-045 — Ritmo e temporização da narração

## 1. Objetivo

Corrigir a cadência da narração: hoje ela sai a 178 WPM sem hierarquia de pausas, o que torna a escuta prolongada desconfortável. Alvo: ~146 WPM e pausas calibradas conforme o *Guia Prático de Ritmo e Temporização*, incluindo a pausa de parágrafo, que hoje **não existe** porque o chunker a destrói antes de o texto chegar ao Speaker.

## 2. Escopo

Alterados:

- `plugins/speakers/kokoro_speaker.py` — velocidade de narração, segmentação por pontuação, aparo das bordas silenciosas e injeção de silêncio calibrado.
- `processing/chunker.py` — preservar a quebra de parágrafo até o Speaker.
- `player/index.html` — opções de velocidade abaixo de 1x.
- `tests/unit/speakers/test_kokoro_speaker.py` e `tests/unit/processing/test_chunker.py`.

Fora de escopo:

- `Speaker` (`plugins/speakers/base.py`) — o contrato **não** muda. A velocidade é constante do módulo, não parâmetro de interface.
- `processing/sanitizer.py` — a OS-044 fechou a notação; esta OS é só temporização.
- Emoção/ênfase real. O Kokoro-82M não tem controle de emoção (ressalva da decisão #23). O ajuste da exclamação é **paliativo por tempo**, não interpretação — está declarado como tal.
- O artefato "pausa no *por*, corrida no *isso*": investigado, a fonemização está correta (`poɾ ˈisʊ`) e não há silêncio anômalo. É o preditor de duração do modelo. Sem conserto na camada de texto.

## 3. Contratos envolvidos

Nenhum contrato de interface alterado. `Speaker.synthesize()` mantém assinatura e continua devolvendo um `AudioChunk` por chamada — a granularidade de chunk, da qual dependem a retomada (OS-022) e a navegação por trecho (OS-039), não muda.

`chunk_text()` mantém o contrato de **quantidade** de chunks: a preservação do parágrafo muda o conteúdo do chunk (separador `\n\n` em vez de espaço), nunca o agrupamento. `count_text_chunks()` segue batendo com a síntese, que é o que a checagem de consistência da OS-022 exige.

## 4. Critérios de aceite

- [ ] Velocidade padrão entrega ~146 WPM (faixa 140–160 do guia), medido no áudio real
- [ ] Pausa de vírgula ≈ 250 ms (guia: 200–300)
- [ ] Pausa de ponto e vírgula / dois pontos ≈ 450 ms (guia: 400–500)
- [ ] Pausa de ponto final ≈ 650 ms (guia: 500–800)
- [ ] Pausa de fim de parágrafo ≈ 1100 ms (guia: 1000–1200)
- [ ] Exclamação recebe pausa maior que a do ponto final
- [ ] A hierarquia é audível na medição: vírgula < ponto e vírgula < ponto < parágrafo, com separação clara (hoje é 169/195/203 ms — indistinguível)
- [ ] Quebra de parágrafo sobrevive ao `chunk_text` e chega ao Speaker
- [ ] `chunk_text` produz a **mesma quantidade** de chunks de antes para o mesmo texto
- [ ] O player oferece velocidades abaixo de 1x
- [ ] Nenhum teste existente quebra (290 hoje)

## 5. Testes exigidos (mínimo)

- `test_chunk_text_preserves_paragraph_break`
- `test_chunk_text_paragraph_break_does_not_change_chunk_count`
- `test_chunk_text_joins_same_paragraph_sentences_with_space`
- `test_chunk_text_treats_heading_without_punctuation_as_paragraph`
- `test_synthesize_uses_narration_speed`
- `test_split_into_pause_segments_keeps_mark_with_preceding_text`
- `test_split_into_pause_segments_detects_paragraph`
- `test_pause_after_exclamation_is_longer_than_after_period`
- `test_trim_silence_keeps_guard_margin`
- `test_silence_samples_match_configured_milliseconds`

## 6. Relatório

Ver `docs/report/OS-045-report.md`.
