# OS-019 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/018-kokoro-limite-fonemas (continuação da OS-018, mesmo branch/PR #16 — não abriu branch nova, conforme instrução explícita da OS)
**Commit(s) relevante(s):** d05351e (test: Red), 32d6e79 (fix: KokoroSpeaker usa `pipeline()`), 6e5de3c (fix: `DEFAULT_MAX_CHARS` revertido para `1000`), 739f367 (docs: aviso no RUNBOOK)

## 1. Resumo do que foi feito

Corrigida a causa raiz do bug investigado na OS-018: `KokoroSpeaker.synthesize()` chamava `pipeline.generate_from_tokens(text, ...)` passando texto bruto em inglês, que o Kokoro trata como se já fosse uma transcrição fonética pronta (pula o G2P por completo). Trocado para `pipeline(text, voice=voice, speed=speed)` (`__call__` do `KPipeline`), que roda o G2P de verdade **e** já divide texto longo respeitando o limite de fonemas e fronteiras de frase — tornando a lógica de divisão/retry manual da OS-018 desnecessária (removida). `DEFAULT_MAX_CHARS` revertido de `480` para `1000`. `RUNBOOK.md` avisa sobre a necessidade de reenviar livros processados antes desta correção.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `d05351e` "Red" existe antes de `32d6e79` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (94 testes no total, todos passando — 95 da OS-018 menos os 3 testes de split/retry removidos, mais os 2 novos desta OS)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — contrato do `Speaker` (seção 4.2) inalterado, `synthesize()` continua devolvendo um único `AudioChunk`
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — `_get_pipeline()` sempre mockado, nenhum Kokoro real em `pytest`
- [x] Type hints e docstring de uma linha em toda função pública — `KokoroSpeaker` ficou mais simples (métodos internos da OS-018 removidos), `synthesize()` e `_get_pipeline()` mantêm o padrão já existente
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4, 5 e 6, incluindo a confirmação empírica)
- [x] Relatório criado em `docs/report/OS-019-report.md`
- [x] PR já aberto (#16, da OS-018) — atualizado com os commits desta OS, cobrindo as duas OS's juntas, conforme a nota no topo do arquivo da própria OS-019

### DoD específico da OS (`docs/os/OS-019-kokoro-api-correta.md` seção 4)

- [x] `KokoroSpeaker` chama `pipeline(text, voice=voice, speed=speed)`, não `pipeline.generate_from_tokens(...)` — confirmado por leitura de código e pelo teste `test_kokoro_speaker_calls_pipeline_directly_not_generate_from_tokens` (dublê sem o método `generate_from_tokens`; se o código ainda o chamasse, o teste falharia com `AttributeError`, como aconteceu no Red)
- [x] Lógica de divisão/retry da OS-018 removida — `_generate_audio` recursivo, `_split_in_half_by_word`, `PHONEME_LIMIT_ERROR`, `MAX_SPLIT_DEPTH` não existem mais no arquivo
- [x] `synthesize()` continua devolvendo um único `AudioChunk` mesmo quando o Kokoro devolve múltiplos `Result`s — testado (`test_kokoro_speaker_concatenates_multiple_results_into_single_audio_chunk`, 3 `Result`s viram 1 `AudioChunk` com a duração da soma)
- [x] `DEFAULT_MAX_CHARS` revisto — revertido para `1000` (razão original da OS-008), já que o limite de fonemas agora é responsabilidade do Kokoro
- [x] Relatório inclui a comparação de fonemas (texto bruto vs. G2P real) como evidência — seção 5
- [x] Testes mockam `__call__` do pipeline, nenhum teste chama o Kokoro real
- [x] `RUNBOOK.md` avisa sobre reenviar livros processados antes desta correção
- [x] `PROJECT_STATE.md` registra o achado (decisão #14, já registrada ao abrir a OS-019; seções 2/4/5/6 atualizadas nesta entrega confirmando a conclusão)
- [x] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada — todas as chamadas reais ao Kokoro (evidência da seção 5) foram feitas fora do `pytest`, manualmente

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro` (adaptado pro novo dublê) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_synthesize_writes_audio_file` (adaptado pro novo dublê) | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_calls_pipeline_directly_not_generate_from_tokens` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_concatenates_multiple_results_into_single_audio_chunk` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |

Removidos (lógica da OS-018 que deixou de existir): `test_kokoro_speaker_splits_and_retries_on_phoneme_limit_error`, `test_kokoro_speaker_returns_single_audio_chunk_after_split_retry`, `test_kokoro_speaker_gives_up_with_clear_error_if_split_does_not_help`.

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `d05351e` (`AttributeError: 'RecordingPipeline' object has no attribute 'generate_from_tokens'` em 4 dos 6 testes) antes de `32d6e79`.

## 4. Saída de comandos relevantes

Rodada de confirmação Red (antes da implementação): 4 de 6 testes falhando com `AttributeError: 'RecordingPipeline' object has no attribute 'generate_from_tokens'` — o dublê novo só tem `__call__`, então a implementação antiga (que ainda chamava `generate_from_tokens`) quebrava imediatamente.

Suíte completa após a implementação (Green), incluindo a reversão de `DEFAULT_MAX_CHARS`:

```
$ python -m pytest -q
94 passed, 1 warning in 6.65s
```

`black`/`ruff` em `plugins/speakers/kokoro_speaker.py`, `tests/unit/speakers/test_kokoro_speaker.py` e `processing/chunker.py`: sem alterações pendentes, `ruff` sem achados.

## 5. Evidência empírica (exigida pela seção 2/4 da OS)

**Comparação de fonemas — texto bruto vs. G2P real do Kokoro**, reproduzindo o achado que motivou a OS:

```python
>>> pipeline = kokoro.KPipeline(lang_code='a')
>>> raw_text = 'The quick brown fox jumps over the lazy dog.'
>>> _, tokens = pipeline.g2p(raw_text)
>>> for gs, ps, tks in pipeline.en_tokenize(tokens):
...     print(repr(ps))
'ðə kwˈɪk bɹˈWn fˈɑks ʤˈʌmps ˈOvəɹ ðə lˈAzi dˈɔɡ.'
```

Confirmado: o texto bruto (`'The quick brown fox jumps over the lazy dog.'`, 46 caracteres) e o G2P real (`'ðə kwˈɪk bɹˈWn fˈɑks ʤˈʌmps ˈOvəɹ ðə lˈAzi dˈɔɡ.'`, fonemas IPA) não têm nenhuma relação de conteúdo — são strings completamente diferentes. Antes desta OS, `KokoroSpeaker` enviava a primeira string pro modelo de inferência como se fosse a segunda.

**Confirmação de que `pipeline()` divide texto longo automaticamente**, respeitando o limite de fonemas sem lógica manual:

```python
>>> text = (dense_technical_paragraph * 4)[:1350]  # 1350 caracteres, texto técnico denso
>>> results = list(pipeline(text, voice='af_heart', speed=1.0))
>>> len(results)
4
>>> [len(r.phonemes) for r in results]
[417, 417, 417, 149]
```

4 pedaços, todos com `len(phonemes)` bem abaixo do limite de 510, gerados automaticamente pelo `__call__` do `KPipeline` (via `en_tokenize`), sem qualquer chamada a `_split_in_half_by_word` ou lógica equivalente — essa parte agora é responsabilidade do Kokoro, não do `KokoroSpeaker`. (A OS citava "3 pedaços de ~489 fonemas" como exemplo de uma execução anterior do dono do projeto; a execução desta validação, com um texto de composição um pouco diferente, produziu 4 pedaços — o número exato varia com o texto, o que importa é que a divisão acontece automaticamente e sempre respeita o limite.)

**Confirmação end-to-end via `KokoroSpeaker.synthesize()` real (não mockado)**, mesmo texto de 1350 caracteres:

```
synthesize OK, duration_seconds= 87.475 elapsed= 3.81s
```

Sintetizou com sucesso, devolvendo um único `AudioChunk`, sem nenhuma exceção — confirma que a integração ponta a ponta (não só a chamada isolada ao pipeline) funciona com a API corrigida.

## 6. Desvios do escopo original

Nenhum desvio de escopo.

## 7. Dúvidas / bloqueios

Nenhum bloqueio para fechar esta OS. Uma nota, não uma dúvida sobre esta OS: livros processados entre a OS-004 e esta correção têm pronúncia incorreta e precisam ser reenviados manualmente (já avisado em `RUNBOOK.md`) — reprocessamento automático está explicitamente fora do escopo desta OS.

## 8. Link do PR

https://github.com/dinei84/listening/pull/16 (mesmo PR da OS-018, atualizado com os commits desta OS e com título/descrição cobrindo as duas — conforme instrução no topo do arquivo da própria OS-019)
