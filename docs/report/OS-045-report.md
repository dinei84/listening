# OS-045 — Relatório de entrega

**Data:** 06/08/2026
**Branch:** `os/045-ritmo-e-temporizacao`
**Commit(s) relevante(s):** `9c65405` (Red), `15a5cb2` (Green)

## 1. Resumo do que foi feito

A narração saía a 178 WPM com pausas de 169/195/203 ms para vírgula, ponto-e-vírgula e ponto — praticamente indistinguíveis entre si e a apenas ~100 ms da linha de base sem pontuação alguma. Não havia hierarquia rítmica. Agora a velocidade entrega 140,5 WPM e as pausas seguem a tabela do *Guia Prático de Ritmo e Temporização*, com a de parágrafo existindo pela primeira vez.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `9c65405` com 12 falhas antes de `15a5cb2`
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou (290 → 305)
- [x] Contratos de `ARQUITETURA.md` respeitados — `Speaker.synthesize()` inalterado
- [x] Nenhuma chamada a API paga nos testes — o Kokoro é local e está dublado (`FakePipeline`)
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-045-report.md`
- [x] PR aberto — https://github.com/dinei84/listening/pull/42

Específico (seção 4 da OS):

- [x] ~146 WPM alvo → **140,5 WPM** medido em prosa representativa (faixa 140–160)
- [x] Vírgula ≈ 250 ms → **285 ms** (guia: 200–300)
- [x] Ponto e vírgula ≈ 450 ms → **485 ms** (guia: 400–500)
- [x] Ponto final ≈ 650 ms → **690 ms** (guia: 500–800)
- [x] Parágrafo ≈ 1100 ms → **1135 ms** (guia: 1000–1200)
- [x] Exclamação (780 ms) maior que ponto final (690 ms)
- [x] Hierarquia audível: 285 < 485 < 690 < 1135, contra 169/195/203 de antes
- [x] Quebra de parágrafo sobrevive ao `chunk_text` — **com a ressalva da seção 6**
- [x] `chunk_text` produz a mesma quantidade de chunks — `test_chunk_text_paragraph_break_does_not_change_chunk_count`
- [x] Player oferece 0.8x e 0.9x
- [x] Nenhum teste existente quebra

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_chunk_text_preserves_paragraph_break` | `tests/unit/processing/test_chunker.py` | Sim |
| `test_chunk_text_joins_same_paragraph_sentences_with_space` | idem | Sim |
| `test_chunk_text_paragraph_break_does_not_change_chunk_count` | idem | Sim |
| `test_chunk_text_treats_heading_without_punctuation_as_paragraph` | idem | Sim |
| `test_chunk_text_collapses_single_newline_into_space` | idem | Sim |
| `test_synthesize_uses_narration_speed` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_split_into_pause_segments_keeps_mark_with_preceding_text` | idem | Sim |
| `test_split_into_pause_segments_uses_the_mark_to_pick_the_pause` | idem | Sim |
| `test_split_into_pause_segments_detects_paragraph` | idem | Sim |
| `test_split_into_pause_segments_does_not_split_on_abbreviation` | idem | Sim |
| `test_pause_hierarchy_matches_the_guide` | idem | Sim |
| `test_pause_after_exclamation_is_longer_than_after_period` | idem | Sim |
| `test_silence_samples_match_configured_milliseconds` | idem | Sim |
| `test_trim_silence_removes_padding_but_keeps_guard_margin` | idem | Sim |
| `test_trim_silence_keeps_all_silent_audio_untouched` | idem | Sim |

Commit "Red" antes do "Green"? [x] Sim.

## 4. Saída de comandos relevantes

Medição **antes** (voz `pf_dora`, speed 1.0):

```
WPM: 178,4

ELEMENTO               MEDIDO   GUIA
(sem pontuação)         95 ms   —
vírgula                169 ms   200-300
ponto e vírgula        195 ms   400-500
dois pontos            172 ms   —
ponto final            203 ms   500-800
exclamação             190 ms   —
interrogação           174 ms   —
fim de parágrafo       390 ms   1000-1200   (e no app nem isso: o chunker matava)
```

Calibração da velocidade **com as pausas já aplicadas**, em prosa representativa (82 palavras, 20,5 palavras/frase):

```
speed 0.80 ->  39.4 s ->  124.9 WPM  técnico
speed 0.90 ->  33.6 s ->  146.6 WPM  FAIXA DE OURO
speed 1.00 ->  31.7 s ->  155.4 WPM  FAIXA DE OURO
speed 1.05 ->  30.8 s ->  159.5 WPM  FAIXA DE OURO
```

Medição **depois** (`NARRATION_SPEED = 0.90`):

```
WPM final: 140,5   (alvo 140-160)

ELEMENTO               MEDIDO   GUIA
vírgula                285 ms   200-300
ponto e vírgula        485 ms   400-500
ponto final            690 ms   500-800
exclamação             780 ms   > ponto
parágrafo             1135 ms   1000-1200
```

Padding de borda que motivou o aparo:

```
segmento A: 208 ms de silêncio inicial, 196 ms final
segmento B: 208 ms de silêncio inicial, 299 ms final
=> concatenar sem inserir nada daria um vão de 404 ms
```

Suíte: `305 passed`. `ruff check`: `All checks passed!`

### Correção de rumo após avaliação de escuta

A primeira versão desta OS foi **reprovada na escuta** e corrigida antes do merge. O registro fica aqui porque o erro é instrutivo e a medição sozinha não o teria pego.

Sintomas relatados: ritmo "exageradamente lento", voz "robotizada, quase como se fosse quebrar", e — pior — **piora na entonação**: a interrogação, que antes dava para ouvir de leve, ficou lisa.

Causa, identificada por construção e não por medição: dividir o texto em vírgula, ponto e vírgula e dois pontos entrega ao modelo cada fragmento como **enunciado independente**, sem contexto do que vem antes ou depois. Ele então aplica contorno de frase completa — com queda final — no meio da oração. Isso explica a emenda audível e o achatamento da entonação ao mesmo tempo.

Tentei confirmar por contorno de F0, mas o método (autocorrelação em fatias) mostrou-se grosseiro demais para servir de prova — a frase declarativa registrou variação final maior que a interrogativa, o que é ruído do estimador. **Registrado como medição inconclusiva**, não como evidência.

Correções aplicadas:

| | v1 (reprovada) | v2 (entregue) |
|---|---|---|
| Divisão | `, ; : . ! ?` | só `. ! ?` |
| `NARRATION_SPEED` | 0.90 | 1.0 |
| Ponto final | 650 ms | 420 ms |
| Exclamação | 750 ms | 520 ms |
| Parágrafo | 1100 ms | 800 ms |
| WPM | 140,5 | **159,0** |

Os valores ficaram **abaixo** dos 500–800 ms do guia de propósito: o guia assume controle total do motor de voz, mas aqui ele é só uma das duas fontes de pausa — o modelo já produz a sua. Somar as duas foi o que soou arrastado.

`test_split_into_pause_segments_never_splits_inside_a_sentence` trava a regressão.

**Validação final:** aprovada na escuta pelo dono do projeto, com a voz `pf_dora`.

## 5. Desvios do escopo original

**A velocidade aprovada era 0.80; foi entregue 0.90.** O dono escolheu o alvo de ~146 WPM a partir de uma tabela medida **sem** as pausas. Com o silêncio calibrado inserido, o mesmo 0.80 passou a entregar ~125 WPM, porque a pausa também conta no tempo total. Para honrar o alvo escolhido (140–160 WPM), a velocidade foi recalibrada para 0.90, que mede 146,6 WPM na prosa de referência. O número que o dono escolheu foi preservado; a constante que o produz é que mudou.

## 6. Dúvidas / bloqueios

**Dependência nova: plugin importando `processing`.** `kokoro_speaker.py` passou a importar `is_false_sentence_boundary` de `processing/chunker.py`. Sem isso, "Dr. Silva" ganharia uma pausa de 650 ms no meio do nome — o ponto da abreviação viraria fim de oração. A alternativa era duplicar a lista `_ABBREVIATIONS` dentro do Speaker, criando duas fontes de verdade que divergiriam na primeira abreviação nova.

A regra do `AGENTS.md` seção 5 proíbe **plugin importar plugin**, e `processing` não é plugin — plugins já importam `core.models`. Ainda assim, **nenhum plugin importava `processing` antes desta OS**, então isso estabelece uma direção de dependência nova e merece ratificação do dono. Se for recusada, a saída é mover a segmentação por pausa para `core/pipeline.py`, o que exigiria mudar o contrato de `Speaker.synthesize()` — fora do escopo desta OS.

**A pausa de parágrafo depende de uma linha em branco que o PDF raramente entrega.** O `chunk_text` agora preserva `\n\n` corretamente (testado), mas foi medido que o `PyMuPDFExtractor` não produz linha em branco nenhuma no PDF de teste: o texto vem linha a linha, e `clean_text` (OS-035) só preserva quebra quando a linha anterior termina em pontuação — o que também acontece no meio de um parágrafo. Ou seja, **em PDF sem linha em branco explícita a pausa de 1135 ms não dispara**, e não há como distinguir "fim de parágrafo" de "frase que terminou no fim da linha" a partir do texto puro.

Resolver isso exige inferir parágrafo do **layout** (gap vertical e indentação, que o PyMuPDF expõe via `get_text("dict")` / bbox), o que é uma OS própria e mexe no Extractor. Registrado para o backlog, não improvisado aqui.

**Fora de escopo, confirmado por medição:** o artefato "pausa no *por*, corrida no *isso*" reportado no teste de expressividade não tem conserto na camada de texto — a fonemização está correta (`poɾ ˈisʊ`) e não há silêncio anômalo. É o preditor de duração do modelo.

## 7. Link do PR

https://github.com/dinei84/listening/pull/42
