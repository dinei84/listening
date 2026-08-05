# OS-034 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/034-truncamento-idiomas-espeak
**Commit(s) relevante(s):** 6a1d848 (test: Red), 7369dee (feat: Green), b067901 (docs)

## 1. Resumo do que foi feito

O `KokoroSpeaker.synthesize()` agora garante que nenhum texto enviado ao Kokoro ultrapasse o limite de **510 fonemas** em idiomas via espeak (es/fr/hi/it/pt — todos exceto `a`/`b`). Para isso, mede o texto com o G2P real do Kokoro (`pipeline.g2p()`, ~1,3% do tempo de um chunk, medido na OS-031) e, se passar do orçamento, divide por fronteira natural — `;`/`:`/`,` preferidos, depois espaço entre palavras, **nunca cortando palavra ao meio** — via uma rotina de divide-e-conquista que mede cada pedaço real (sem erro de estimativa). Cada pedaço é sintetizado e os áudios são concatenados num único `AudioChunk` (a granularidade de `chunk_text()` → `AudioChunk` não muda, preservando retomada/progresso/preempção). Inglês continua no caminho `en_tokenize` do próprio Kokoro, inalterado. O comentário desatualizado de `processing/chunker.py` ("o Kokoro lida com o limite internamente") foi corrigido. Verificação empírica com o Kokoro real: frase de 557 caracteres que era truncada em 510 fonemas (24,15s) agora sintetiza os 651 fonemas inteiros (34,55s, +43% de duração), terminando na última palavra.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `6a1d848` "Red" antes de `7369dee` "Green")
- [x] Todos os testes da OS passam localmente — 165 pass, 0 fail
- [x] Nenhum teste existente quebrou (159 anteriores + 6 novos = 165)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `Speaker.synthesize()` não mudou de assinatura; a lógica de divisão ficou **dentro do `KokoroSpeaker`** (onde mora o conhecimento do engine), `processing/chunker.py` continua agnóstico de engine e o contrato "nunca corta sentença ao meio" segue intacto
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — `_build_pipeline()` mockado (padrão desde a OS-004); o dublê `FakePipeline` ganhou um `g2p` fake determinístico
- [x] Type hints e docstring de uma linha em toda função pública nova/alterada
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4, 5 e 6)
- [x] Relatório criado em `docs/report/OS-034-report.md`
- [x] PR aberto contra o branch principal, título `[OS-034] ...`

### DoD específico da OS (`docs/os/OS-034-truncamento-idiomas-espeak.md` seção 4)

- [x] Nenhum texto enviado ao Kokoro excede 510 fonemas, em qualquer idioma — `_split_by_phoneme_budget()` mede cada pedaço com `g2p` e só para quando ≤ 510; `test_kokoro_speaker_splits_oversized_sentence_before_synthesis` + `test_kokoro_speaker_splits_oversized_text_at_clause_boundaries` (todos os pedaços `≤ 510` fonemas no dublê) + verificação empírica com o Kokoro real (max 327 fonemas por pedaço)
- [x] Uma frase longa em português (sem `.!?` internos) que hoje é truncada passa a ser sintetizada **por inteiro** — verificação empírica com Kokoro real: 557 caracteres → 651 fonemas (g2p real), antes sintetizava só 510; depois sintetiza todos; duração 24,15s → 34,55s (+43%) e a cauda de fonemas da última palavra presente no áudio (seção 4)
- [x] Nenhuma palavra é cortada ao meio pela divisão — `test_kokoro_speaker_never_splits_mid_word` e `test_kokoro_speaker_splits_oversized_text_at_clause_boundaries` (flatten das palavras dos pedaços == palavras originais, inclusive com pontuação) + verificação com o espeak real
- [x] Um pedaço de `chunk_text()` continua produzindo **exatamente um** `AudioChunk` (`sequence` inalterada) — a divisão acontece dentro do `synthesize()` e os áudios são concatenados num único `AudioChunk`; `test_kokoro_speaker_returns_single_audio_chunk_for_oversized_text` (1 `AudioChunk` com várias chamadas internas) + toda a suíte de retomada/progresso/preempção (OS-022/024/032) verde
- [x] Comportamento em inglês inalterado — a divisão por orçamento só roda para `effective_lang_code not in "ab"`; inglês segue com `pieces = [text]` e o `en_tokenize` do Kokoro; os testes de inglês existentes (`test_kokoro_speaker_concatenates_multiple_results_into_single_audio_chunk`, `test_kokoro_speaker_detects_english_...`) continuam verdes
- [x] Comentário desatualizado de `processing/chunker.py` corrigido — agora deixa explícito que o Kokoro só divide texto longo sozinho **para inglês** e que o tratamento do orçamento de fonemas dos demais idiomas mora no `KokoroSpeaker` (OS-034)
- [x] `PROJECT_STATE.md` registra a limitação de qualidade do espeak-ng como risco conhecido em aberto — seção 6 (a fonemização de pt via espeak é aproximada, ex: "segurança" → `...æ`; sem solução barata, exigiria `Speaker` alternativo, decisão do dono; a OS-034 corrige o truncamento, não isso)
- [x] Nenhuma chamada de rede ou API paga na suíte de testes — tudo mockado; a única chamada real foi na verificação empírica manual (Kokoro local, sem custo, fora da suíte)

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_kokoro_speaker_splits_oversized_sentence_before_synthesis` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_never_splits_mid_word` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_returns_single_audio_chunk_for_oversized_text` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_short_text_unchanged` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_splits_oversized_text_at_clause_boundaries` (extra, pontuação) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_chunk_text_contract_unchanged` | `tests/unit/processing/test_chunker.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `6a1d848` (2 falhas: `AssertionError` por `len(pipeline.calls) > 1` — o speaker mandava o texto inteiro numa chamada só) antes de `7369dee`.

## 4. Verificação empírica com o Kokoro real (seção 7 da OS)

Frase longa em português SEM `.!?` interno, 557 caracteres (o cenário do achado), sintetizada com voz `pf_dora` no Kokoro real (CUDA). **ANTES** = chamada direta `pipeline(text, ...)` (como o `synthesize` fazia); **DEPOIS** = `KokoroSpeaker().synthesize(text, lang_code="p")` corrigido.

```
texto: 557 caracteres
fonemas totais (g2p real): 651  (>510? True)

ANTES (pipeline direto): 1 resultado(s), duracao=24.15s, fonemas sintetizados=510
DEPOIS (KokoroSpeaker OS-034): duracao=34.55s
tempo de sintese: antes=1.02s depois=2.02s

split OS-034: 2 pedaco(s), max fonemas por pedaco = 327

GANHO de duracao: 10.40s (43.1% maior)
```

- **Antes:** o Kokoro sintetizou só os 510 primeiros fonemas (o resto — 141 fonemas, ~22% da frase — foi descartado com um `logger.warning`), 24,15s de áudio.
- **Depois:** os 651 fonemas inteiros, 34,55s (+43%), divididos em 2 pedaços de no máximo 327 fonemas.
- **Fim da frase coberto** (a frase termina completa, não no meio da palavra):

```
ultima palavra do texto: 'com'
cauda dos fonemas completos: 'ˌistˈemæz ʤˌistribˈuɪdʊz mˌodˈɛɾənʊs koŋ'
fonemas do ultimo pedaco (cauda): 'ˌistˈemæz ʤˌistribˈuɪdʊz mˌodˈɛɾənʊs koŋ'
cauda coberta: True
```

A audição fina (ouvir que a frase termina completa) fica registrada como evidência indireta forte: a duração cresce 43% e a última palavra do texto tem seus fonemas presentes no último pedaço sintetizado — impossível de acontecer se o truncamento persistisse. O custo do `g2p` extra é o aceito pela OS (~1,3% por contagem; aqui ~2 chamadas por chunk grande).

## 5. Decisões de implementação documentadas

1. **Local da divisão:** dentro de `KokoroSpeaker.synthesize()` (recomendado pela OS), não no `chunker`. Motivos confirmados: é onde mora o conhecimento do engine (limite de fonemas, idioma efetivo); o `synthesize()` já concatena múltiplos áudios (`torch.cat`), então dividir não muda a granularidade de `AudioChunk`; `chunker.py` segue agnóstico de engine.
2. **Medição real, não estimativa:** o orçamento é checado com `pipeline.g2p(text)` (o G2P real do Kokoro), não com heurística de caracteres — a densidade varia por idioma (1,19 em pt, ~0,88 em en). A medição empírica confirmou que "soma de fonemas por palavra + espaços" ≈ total (158 = 144 + 14), mas a implementação **não** confia em estimativa: cada pedaço é validado por medição real, eliminando qualquer erro de arredondamento.
3. **Algoritmo:** preferência de fronteira `;`/`:`/`,` (cláusulas), acumulando até o orçamento com medição real de cada candidato; cláusula que sozinha estoura é subdividida por divide-e-conquista em fronteiras de palavra. Nunca corta palavra ao meio; palavra única acima do orçamento (caso de borda, ~430+ caracteres) é emitida inteira — impossível dividir sem violar o contrato.
4. **Inglês intocado:** a divisão só roda para `effective_lang_code not in "ab"`. O caminho `en_tokenize` do Kokoro já respeitava o limite; pre-dividir o inglês mudaria o áudio existente sem necessidade (a OS proíbe).
5. **Limitação do espeak-ng (registrada, não corrigida):** a qualidade/sotaque do português (ex: "segurança" → `sˌeɡuɾˈɐ̃ŋsæ`, terminando em `æ`, vogal inexistente em pt) é limitação inerente do Kokoro+espeak, sem parâmetro que corrija; exigiria um `Speaker` alternativo (decisão do dono, possivelmente TTS pago). Registrado em `PROJECT_STATE.md` seção 6 como risco em aberto, como a OS manda.

## 6. Desvios do escopo original

Nenhum. As mudanças ficaram em `plugins/speakers/kokoro_speaker.py` (a implementação), `processing/chunker.py` (só o comentário) e os dois arquivos de teste; `core/pipeline.py` e `chunk_text()` não foram tocados, e a granularidade de `AudioChunk` não mudou. A investigação da OS (seção 2) foi reaproveitada, não repetida — a única medição nova foi a confirmação empírica de que a soma de fonemas por palavra ≈ total, usada para justificar a escolha por medição real em vez de estimativa.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Uma observação: o dublê `FakeG2P` dos testes usa densidade 1.19 (a de pt) para reproduzir o comportamento real de densidade por idioma; a implementação em produção mede com o G2P real do idioma efetivo, então a densidade do dublê só afeta a expectativa dos testes, não o comportamento.

## 8. Link do PR

A preencher após abertura do PR.
