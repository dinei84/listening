# OS-037 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/037-dicionario-fonetico
**Commit(s) relevante(s):** d79ca8a (test: Red), 7c4d6fa (feat: Green)

## 1. Resumo do que foi feito

Mapa de substituição fonética local em `plugins/speakers/phonetic_map.yaml`, aplicado por `_apply_phonetic_map()` no `KokoroSpeaker` **antes** da divisão por orçamento de fonemas (OS-034) — a substituição muda o tamanho fonêmico do texto, então precisa vir antes da medição. A troca respeita fronteira de palavra e ignora maiúsculas/minúsculas na busca. Mapa ausente ou malformado degrada para "sem substituição", nunca derruba a síntese. `RUNBOOK.md` ganhou a seção 6.1 explicando como verificar e adicionar entradas.

**Mapa inicial: 7 entradas, todas com evidência medida em frase** (ver seção 4). Uma candidata (`cache`) foi testada e **rejeitada** por piorar a fonemização.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (`d79ca8a` "Red" antes de `7c4d6fa` "Green")
- [x] Todos os testes da OS passam localmente — 224 pass, 0 fail
- [x] Nenhum teste existente quebrou (217 anteriores + 7 novos = 224)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato tocado; a substituição acontece **dentro** do `KokoroSpeaker`, antes de falar com o engine
- [x] Nenhuma chamada real a API paga dentro dos testes — `_build_pipeline()` segue mockado
- [x] Type hints e docstring de uma linha em toda função nova
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-037-report.md`
- [x] PR aberto contra o branch principal

### DoD específico da OS (seção 4)

- [x] Termos do mapa substituídos antes da fonemização, respeitando fronteira de palavra — `test_phonetic_map_replaces_known_term_before_synthesis`, `test_phonetic_map_respects_word_boundaries`
- [x] Texto sem termos do mapa passa inalterado — `test_text_without_mapped_terms_is_unchanged`
- [x] Substituição não altera contagem de `AudioChunk` nem `sequence` — `test_phonetic_map_does_not_change_audio_chunk_count`
- [x] Mapa vazio ou arquivo ausente não derruba a síntese — `test_missing_or_empty_map_does_not_break_synthesis`; `_phonetic_map()` devolve `{}` em qualquer falha de leitura
- [x] Cada entrada do mapa inicial tem evidência de melhora registrada — seção 4
- [x] `RUNBOOK.md` explica como adicionar entradas — seção 6.1
- [x] Nenhuma chamada de rede ou API paga na suíte

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_phonetic_map_replaces_known_term_before_synthesis` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_phonetic_map_respects_word_boundaries` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_phonetic_map_is_case_insensitive` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_text_without_mapped_terms_is_unchanged` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_missing_or_empty_map_does_not_break_synthesis` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_phonetic_map_does_not_change_audio_chunk_count` (regressão) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_phonetic_map_file_loads_real_entries` (extra) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `d79ca8a` (7 falhas: `AttributeError: module ... has no attribute '_phonetic_map'`) antes de `7c4d6fa`.

## 4. Verificação empírica (exigida pela seção 6 da OS)

### Correção de método durante a execução — vale registrar

A primeira rodada mediu os termos **isolados** (`pt.g2p("UML")`) e encontrou o que parecia um erro grave: `'ˈũml'`, um bloco nasal impronunciável. Ao verificar de novo **dentro de uma frase**, o espeak se comportou de outro jeito: `'ˌuˌemeˈɛly'` — já soletrado, só que colado. **A medição isolada superestimava o problema.** Todas as entradas foram reavaliadas em contexto, e o arquivo `phonetic_map.yaml` foi reescrito para citar a evidência correta. Fica a lição para quem adicionar entradas depois — o `RUNBOOK.md` seção 6.1 já instrui a medir em frase.

### Evidência em frase, entrada por entrada

```
MUDOU  UML       antes : ʊ ʤˌiaɡrˈɐ̃mæ ˌuˌemeˈɛly mˈɔstræ tˈudʊ.
                 depois: ʊ ʤˌiaɡrˈɐ̃mæ ˈu ˈemj ˌely mˈɔstræ tˈudʊ.
MUDOU  OCP       antes : ʊ prˌiŋsipˈiʊ ˌɔsˌepˈe ˌoɾiˈAŋtæ ʊ dezˈIn.
                 depois: ʊ prˌiŋsipˈiʊ ˈɔ sˈe pˈe ˌoɾiˈAŋtæ ʊ ʤˌizˈain.
MUDOU  API       antes : a ˌapˌeˈi dʊ sˌistˈemæ xˌespˈoŋʤy xˌapˈidʊ.
                 depois: a a pˈe ˈi dʊ sˌistˈemæ xˌespˈoŋʤy xˌapˈidʊ.
MUDOU  JSON      antes : u ˌaɾəkˈivʊ ʒsˈoŋ foɪ sˈWvʊ.
                 depois: u ˌaɾəkˈivʊ dʒˈeizoŋ foɪ sˈWvʊ.
MUDOU  Docker    antes : ʊ kˌoŋtInˈer dokˈer subˈiʊ bˈAŋ.
                 depois: ʊ kˌoŋtInˈer dˈɔkɛr subˈiʊ bˈAŋ.
MUDOU  design    antes : ʊ dezˈIn dʊ sˌistˈemæ ˌevolwˈiʊ.
                 depois: ʊ ʤˌizˈain dʊ sˌistˈemæ ˌevolwˈiʊ.
MUDOU  SOLID     antes : ʊs prˌiŋsipˈiʊs solˈid ˌaʒˈudɐ̃ʊ̃ mwˈiŋtʊ.
                 depois: ʊs prˌiŋsipˈiʊs sˈɔlid ˌaʒˈudɐ̃ʊ̃ mwˈiŋtʊ.
```

**Classificação honesta do ganho de cada entrada:**

| Entrada | Ganho | Natureza |
|---|---|---|
| `JSON` | claro | `ʒsˈoŋ` era leitura quebrada ("jsong") → `dʒˈeizoŋ` |
| `Docker` | claro | tônica errada (`dokˈer`, "do-KÉR") → `dˈɔkɛr` ("DÓ-ker") |
| `design` | claro | `dezˈIn` → `ʤˌizˈain`, mais perto do uso em PT-BR |
| `SOLID` | claro | tônica errada (`solˈid`) → `sˈɔlid` |
| `UML`, `OCP`, `API` | **modesto** | em frase o espeak já soletra; a substituição **separa as letras**, deixando a sigla mais inteligível — não corrige leitura quebrada |

As três siglas foram mantidas porque a separação é um ganho real de inteligibilidade em áudio, mas o relatório e o próprio YAML deixam claro que o ganho é menor do que o das quatro primeiras.

### Entrada rejeitada

```
cache    antes='kˈaʃy'   candidata 'quéxi' -> 'kˈɛksi'
```

`'kˈɛksi'` ("kéksi") é **pior** que o original `'kˈaʃy'` ("káshi"). Rejeitada. É exatamente o critério que a OS pedia: entrada sem evidência de melhora não entra.

### Fronteira de palavra, com o mapa real carregado

```
'A RAPIDEZ impressiona.'  -> 'A RAPIDEZ impressiona.'     (API não casa dentro de RAPIDEZ)
'designer grafico'        -> 'designer grafico'           (design não casa dentro de designer)
'APIs modernas'           -> 'APIs modernas'              (API não casa em APIs)
```

### Frase completa

```
ANTES : O diagrama UML documenta a API REST e o formato JSON usado no Docker, seguindo SOLID e OCP no design.
DEPOIS: O diagrama u ême ele documenta a a pê i REST e o formato djêizon usado no dóquer, seguindo sólid e ó cê pê no dizáin.
```

## 5. Decisões de implementação documentadas

**(a) YAML em vez de JSON.** O projeto já usa `yaml` em `config.yaml` e a dependência já existe. Além disso o YAML aceita comentário por linha — cada entrada carrega a evidência (`# 'ʒsˈoŋ' -> 'dʒˈeizoŋ'`) ao lado dela, que é justamente o que a OS exige documentar.

**(b) O arquivo fica em `plugins/speakers/`, junto do Speaker que o usa.** Mantém o conhecimento do engine dentro do plugin, como a seção 3 da OS previa. Se um dia houver um segundo `Speaker`, avaliar mover — mesma observação já registrada na OS-025 sobre `LANG_CODE_BY_LANGUAGE`.

**(c) O padrão regex é derivado do mapa a cada chamada, sem cache próprio.** A primeira versão cacheava mapa e padrão separadamente com `lru_cache`, e os dois saíam de sincronia quando o mapa mudava — o padrão casava um termo que o mapa já não tinha, estourando `KeyError`. Foi um bug real, pego pelo teste do mapa vazio, não só um artefato de teste. O `re` já mantém cache interno de padrões compilados, então o custo é desprezível.

**(d) Termos mais longos primeiro na alternância do regex.** Evita que um termo curto case antes de um mais específico que o contenha.

**(e) `(?<!\w)`/`(?!\w)` em vez de `\b`.** Funciona também para termos que comecem ou terminem em caractere não-alfanumérico, e garante que a troca nunca aconteça dentro de outra palavra.

**(f) A substituição roda antes da divisão por orçamento de fonemas (OS-034).** "u ême ele" tem muito mais fonemas que "UML" — medir antes de substituir daria um orçamento errado e poderia reintroduzir truncamento.

## 6. Desvios do escopo original

Nenhum. Arquivos tocados: `plugins/speakers/phonetic_map.yaml` (novo), `plugins/speakers/kokoro_speaker.py`, `RUNBOOK.md` e os testes.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Duas observações para o dono do projeto:

1. **Isto não conserta o sotaque geral do português** — como a OS já dizia. O espeak-ng continua fonemizando por regras e produzindo aproximações (o `æ` de "segurança" segue lá). O mapa conserta **termo a termo**, e depende de alguém notar o erro e adicionar a entrada. O único caminho para resolver de forma ampla continua sendo um `Speaker` alternativo para português — decisão sua, provavelmente com TTS pago (`ARQUITETURA.md` seção 6). Risco segue aberto na seção 6 do `PROJECT_STATE.md`.
2. **O mapa é lido uma vez por processo** (`lru_cache`). Depois de editar o YAML é preciso reiniciar o worker — está dito no `RUNBOOK.md` seção 6.1.

## 8. Link do PR

*A preencher após abrir o PR.*
