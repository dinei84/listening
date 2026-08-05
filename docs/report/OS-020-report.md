# OS-020 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/020-deteccao-idioma-kokoro
**Commit(s) relevante(s):** 557767e (test: Red), 56e9a40 (feat: Green)

## 1. Resumo do que foi feito

`KokoroSpeaker.synthesize()` passa a detectar o idioma do texto recebido (via `langdetect`, com seed fixa pra ser determinístico) e usar o `lang_code` e a voz correspondentes do Kokoro, mantendo um pipeline em cache por idioma. Idioma sem mapeamento, texto curto demais pra detecção confiável, ou idioma cujo pipeline não pode ser construído neste ambiente degradam pro inglês — nunca erro. Contrato do `Speaker` inalterado.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `557767e` "Red" antes de `56e9a40` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (101 no total: 94 anteriores + 7 novos)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `Speaker` (seção 4.2) inalterado, `synthesize(text, voice=None)` com a mesma assinatura; detecção encapsulada no plugin
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — `_build_pipeline()` sempre mockado; `langdetect` roda de verdade nos testes (local, sem rede, conforme a própria OS autoriza na seção 2)
- [x] Type hints e docstring de uma linha em toda função pública nova (`_detect_lang_code`, `_get_pipeline`, `_build_pipeline`)
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4, 5 e 6, incluindo o achado sobre japonês/mandarim)
- [x] Relatório criado em `docs/report/OS-020-report.md`
- [x] PR aberto contra o branch principal, título `[OS-020] ...`

### DoD específico da OS (`docs/os/OS-020-deteccao-idioma-kokoro.md` seção 4)

- [x] `langdetect==1.0.9` em `requirements.txt`, versão conferida via `pip index versions langdetect` (mais recente no PyPI)
- [x] `synthesize()` detecta o idioma e usa `lang_code`/voz correspondentes — seção 5
- [x] Idioma sem mapeamento cai pro inglês, não erro — testado com alemão (`test_kokoro_speaker_falls_back_to_english_for_unmapped_language`)
- [x] Texto curto tem comportamento explícito e documentado — abaixo de `MIN_DETECTION_CHARS = 40` reaproveita o último idioma detectado com sucesso na mesma instância (justificativa e medições na seção 5)
- [x] Um pipeline por idioma, cache lazy — `test_kokoro_speaker_caches_pipeline_per_language` (4 sínteses em 2 idiomas → 2 construções)
- [x] Nomes de voz verificados empiricamente, documentados — seção 5
- [x] Testes não constroem `kokoro.KPipeline` real — `_build_pipeline()` é o único ponto que toca o engine e está mockado em todos os testes que sintetizam
- [x] Validação empírica com português real (não mockado) — seção 5
- [x] Nenhuma chamada de rede ou API paga na suíte automatizada

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_kokoro_speaker_detects_portuguese_and_uses_correct_lang_code` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_detects_english_and_uses_correct_lang_code` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_falls_back_to_english_for_unmapped_language` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_caches_pipeline_per_language` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_handles_short_text_without_crashing` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_falls_back_to_english_when_pipeline_is_unavailable` (extra) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_short_text_reuses_last_detected_language` (extra) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_explicit_voice_overrides_detected_default` (extra) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |

Os testes já existentes de OS anteriores (`engine_used`, escrita do `.wav`, concatenação de múltiplos `Result`s) foram adaptados pro novo dublê, que agora substitui `_build_pipeline(lang_code)` em vez de `_get_pipeline()`.

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `557767e` (`AttributeError: KokoroSpeaker has no attribute '_build_pipeline'`, 11 falhas) antes de `56e9a40`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação): 11 de 13 testes falhando com `AttributeError: <class 'KokoroSpeaker'> has no attribute '_build_pipeline'`.

Suíte completa após a implementação (Green):

```
$ python -m pytest -q
101 passed, 1 warning in 8.98s
```

`black --check` e `ruff check` em `plugins/speakers/kokoro_speaker.py` e `tests/unit/speakers/test_kokoro_speaker.py`: sem alterações pendentes, sem achados.

## 5. Validação empírica

### 5.1 Nomes de voz por idioma (descobertos, não advinhados)

Os nomes não estão listados estaticamente no pacote — `KPipeline.load_single_voice()` baixa `voices/{voice}.pt` do repositório `hexgrad/Kokoro-82M` no Hugging Face sob demanda. Listados via `huggingface_hub.list_repo_files('hexgrad/Kokoro-82M')`, filtrando `voices/`: **54 vozes**, no padrão `{lang_code}{f|m}_{nome}`. Vozes por idioma relevante:

| `lang_code` | Idioma | Vozes disponíveis | Escolhida como padrão |
|---|---|---|---|
| `a` | American English | `af_alloy`, `af_aoede`, `af_bella`, `af_heart`, `af_jessica`, `af_kore`, `af_nicole`, `af_nova`, `af_river`, `af_sarah`, `af_sky`, `am_adam`, `am_echo`, `am_eric`, `am_fenrir`, `am_liam`, `am_michael`, `am_onyx`, `am_puck`, `am_santa` | `af_heart` (mantida — era o padrão antes desta OS) |
| `b` | British English | `bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis` | `bf_alice` |
| `e` | Espanhol | `ef_dora`, `em_alex`, `em_santa` | `ef_dora` |
| `f` | Francês | `ff_siwis` | `ff_siwis` (única) |
| `h` | Hindi | `hf_alpha`, `hf_beta`, `hm_omega`, `hm_psi` | `hf_alpha` |
| `i` | Italiano | `if_sara`, `im_nicola` | `if_sara` |
| `p` | Português (pt-br) | `pf_dora`, `pm_alex`, `pm_santa` | `pf_dora` |
| `j` | Japonês | `jf_alpha`, `jf_gongitsune`, `jf_nezumi`, `jf_tebukuro`, `jm_kumo` | `jf_alpha` (ver 5.4) |
| `z` | Mandarim | `zf_xiaobei`, `zf_xiaoni`, `zf_xiaoxiao`, `zf_xiaoyi`, `zm_yunjian`, `zm_yunxi`, `zm_yunxia`, `zm_yunyang` | `zf_xiaoxiao` (ver 5.4) |

Critério: primeira voz feminina de cada idioma, mantendo `af_heart` no inglês pra não mudar o comportamento que já existia.

### 5.2 Português real, sem mock — a correção funcionando

```
PT: lang_code='p' voz='pf_dora'
EN: lang_code='a' voz='af_heart'

G2P portugues (p): 'a ˌAŋʒeɲaɾˈiæ ʤy sˌeɡuɾˈɐ̃ŋkæ xekˈɛr mˌetˈodʊs foɾəmˈIs.'
G2P ingles    (a): 'ɐ ɛnʤənhˈɛɹiə də sˌɛɡjʊɹɹˈæŋkə ɹᵻkˈɜɹ mɛtˈOdOz fˈɔɹmIz.'

synthesize(PT) OK: duration=8.80s frames=211200 rate=24000 elapsed=3.07s
pipelines em cache: ['a', 'p']
```

A frase é a mesma nos dois casos (`"A engenharia de seguranca requer metodos formais."`). Os fonemas são completamente diferentes: o pipeline `p` produz fonemas de português (`ʒ`, `ɲ`, `ɐ̃`, `ʊ`), o pipeline `a` aplica fonemas de inglês às palavras portuguesas (`ɛnʤənhˈɛɹiə` para "engenharia") — que é exatamente o áudio incompreensível relatado no achado que motivou esta OS. A síntese real em português gerou 8,80s de áudio (211200 frames a 24kHz) com a voz `pf_dora`, e o cache terminou com os dois pipelines construídos.

### 5.3 Limite de texto curto (`MIN_DETECTION_CHARS = 40`)

O `langdetect` erra bastante em strings curtas — medido:

```
'Hello'       -> 'fi'   (finlandês)
'Ola'         -> 'tr'   (turco)
'Capitulo 1'  -> 'ro'   (romeno)
'...'         -> LangDetectException: No features in text.
```

Truncando um texto conhecido em vários comprimentos:

```
pt: n= 10 BAD -> 'da'      en: n= 10 OK -> 'en'
    n= 20 OK  -> 'pt'          n= 20 OK -> 'en'
    n= 30 OK  -> 'pt'          n= 30 OK -> 'en'
    n= 40 OK  -> 'pt'          n= 40 OK -> 'en'
```

A detecção estabilizou a partir de ~20 caracteres nas amostras testadas; `40` foi escolhido por dar o dobro dessa margem (mesma lógica de margem de segurança já usada no threshold `0.85` da decisão #9). Como `chunk_text()` produz chunks de até 1000 caracteres, o limite raramente afeta conteúdo real — ele existe pra cabeçalhos e fragmentos soltos.

**Comportamento escolhido abaixo do limite: reaproveitar o último idioma detectado com sucesso na mesma instância** (e o padrão inglês, se ainda não houve nenhum). Motivo: `core/pipeline.py:synthesize_text()` cria **um** `KokoroSpeaker` e reusa a mesma instância pra todos os chunks do livro (linhas 35-39), então o "último idioma" é sempre o do próprio livro em processamento. Cair pro inglês em vez disso faria um cabeçalho curto no meio de um livro em português ser lido em inglês, que é justamente o problema que esta OS corrige. Também vale pro caso `LangDetectException` (texto sem features).

**Nota de determinismo:** o `langdetect` é não-determinístico por padrão — a mesma string pode devolver idiomas diferentes entre execuções. A implementação fixa `DetectorFactory.seed = 0` na importação do módulo, senão a escolha de voz de um mesmo livro poderia variar entre execuções.

### 5.4 Achado: japonês e mandarim não funcionam neste ambiente

Ao testar a construção real de cada pipeline:

```
_build_pipeline('j') -> ModuleNotFoundError: No module named 'pyopenjtalk'
_build_pipeline('z') -> ModuleNotFoundError: No module named 'ordered_set'
_build_pipeline('p') -> OK
_build_pipeline('e') -> OK
```

O Kokoro exige `misaki[ja]`/`misaki[zh]` pra esses dois idiomas; o projeto só tem `misaki[en]` mais o `espeak-ng` (que cobre es/fr/hi/it/pt). Sem tratamento, um PDF em japonês faria `KPipeline(lang_code='j')` estourar e derrubar o livro inteiro — a mesma classe de falha que a OS-018 investigou.

Por isso a implementação trata falha de construção de pipeline como "idioma indisponível" e degrada pro inglês, guardando `None` em cache pra não tentar reconstruir a cada chunk. Confirmado empiricamente:

```
idioma detectado para japones -> lang_code: 'j'
lang_code efetivo apos fallback: 'a'
```

O mapeamento de `ja`/`zh` foi **mantido** conforme a OS pede, pra que instalar as dependências extras no futuro passe a funcionar sem mudar código. Registrado em `PROJECT_STATE.md` seção 6 como pendência conhecida: um PDF nesses idiomas ainda gera pronúncia errada silenciosamente.

## 6. Desvios do escopo original

Um acréscimo, não um desvio: além do fallback pra idioma **sem mapeamento** que a OS pede, foi implementado fallback pra idioma **mapeado mas indisponível no ambiente** (seção 5.4). Não estava escrito na OS porque o problema só apareceu ao testar a construção real dos pipelines, mas segue o princípio que a própria OS define ("padrão seguro, não erro") e evita que um PDF em japonês derrube o livro inteiro.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Duas notas pro dono do projeto, nenhuma delas decisão deste agente:

1. Japonês e mandarim geram áudio com pronúncia errada silenciosamente (seção 5.4). Resolver é instalar `misaki[ja]`/`misaki[zh]` — ficou fora do escopo (esta OS é sobre detecção, não sobre ampliar a lista de idiomas suportados).
2. As vozes padrão por idioma foram escolhidas por um critério mecânico (primeira voz feminina), não por qualidade percebida — só o inglês (`af_heart`) tem uso real acumulado. Se alguma soar ruim na prática, trocar é editar uma entrada de `VOICE_BY_LANG_CODE`.

## 8. Link do PR

https://github.com/dinei84/listening/pull/17
