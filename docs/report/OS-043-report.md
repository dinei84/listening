# OS-043 — Relatório de entrega (pipeline para `Speaker` remoto)

**Data:** 2026-08-06
**Branch:** `os/043-pipeline-speaker-remoto` (criado a partir de `os/042-trava-de-custo`, que ainda não foi mergeado — os arquivos centrais são compartilhados)
**Commit(s) relevante(s):** `test: cobre limite declarado e retry do Speaker remoto (OS-043) — Red` e `feat: implementa limite por engine e retry com backoff do Speaker remoto (OS-043) — Green`

## 1. Resumo do que foi feito

Removidas as duas suposições "locais" do pipeline, antes de qualquer Speaker pago existir:

**(a) Limite declarado pelo Speaker.** O contrato `Speaker` ganhou `max_request_chars: int | None = None` (extensão aditiva, mesmo padrão das OS-021/022/025) — quem não declara mantém o comportamento atual. O `KokoroSpeaker` não declara (`None`), então continua dividindo por fonemas com o G2P dele internamente; o pipeline envia o texto inteiro numa chamada e o áudio produzido é idêntico (regressão provada por teste). Um Speaker cloud futuro declara o limite em caracteres e o pipeline divide o texto do chunk em pedaços que respeitam o limite (nunca cortando palavra), concatenando os áudios num único `AudioChunk`.

**(b) Retry com backoff para falha transitória.** O contrato ganhou `SpeakerError`/`TransientSpeakerError`/`PermanentSpeakerError`. Em `core/pipeline.py::synthesize_text()`, `TransientSpeakerError` (rede/timeout/429/5xx) é retentado com backoff exponencial configurável (`retry.max_attempts`/`base_delay_seconds`/`max_delay_seconds` em `config.yaml`); `PermanentSpeakerError` (credencial/texto/4xx não-429) e demais exceções sobem na hora, sem gastar tentativas. Esgotado o retry, o worker marca o `Book` como `error` com mensagem explícita de que o áudio já persistido está preservado (retomável via OS-022). Nenhuma chamada de rede real na suíte.

## 2. Checklist de DoD

### DoD específico da OS (`docs/os/OS-043-pipeline-para-speaker-remoto.md` seção 4)

- [x] Um `Speaker` pode declarar limite próprio de tamanho por chamada; quem não declara mantém o comportamento atual — `max_request_chars` aditivo, `None` = comportamento antigo; teste `test_speaker_can_declare_own_size_limit` + regressões de todos os testes existentes (que usam speakers sem declaração) passam
- [x] O `KokoroSpeaker` produz **exatamente o mesmo resultado de hoje** — regressão explícita das OS-034/037; teste `test_kokoro_speaker_output_unchanged` (verifica `max_request_chars is None` e que o texto inteiro vai numa chamada, com o pipeline do Kokoro dublado)
- [x] Falha transitória na síntese de um chunk é repetida com backoff, sem derrubar o livro — `_synthesize_with_retry` com backoff exponencial; teste `test_transient_failure_is_retried_with_backoff` (3 chamadas, sleeps `[base, base×2]`)
- [x] Falha permanente falha de imediato, sem gastar tentativas — `PermanentSpeakerError` não é capturado pelo retry; teste `test_permanent_failure_fails_immediately` (1 chamada, 0 sleeps)
- [x] Tentativas e espera são configuráveis — bloco `retry` em `config.yaml` → `Config.retry_max_attempts`/`retry_base_delay_seconds`/`retry_max_delay_seconds`; teste `test_retry_count_is_configurable` (max_attempts=2 → exatamente 2 chamadas)
- [x] Esgotadas as tentativas, os chunks já persistidos continuam no banco e a mensagem diz isso — worker captura `TransientSpeakerError` esgotado e monta mensagem explícita de preservação; teste `test_retry_exhausted_keeps_persisted_chunks` (chunk 0 pré-persistido continua, `error_message` contém "preservado")
- [x] Nenhuma chamada de rede real na suíte — dublês `FlakySpeaker`/`AlwaysFailingSpeaker`/`PermanentFailSpeaker`/`RecordingSpeaker`; `time.sleep` sempre monkeypatchado nos testes de retry
- [x] Nenhum teste das OS-021/022/024/032/034/037 quebra — 258 testes passando (ver seção 3)

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit dos testes falhando existe no histórico do branch) — commit `... — Red` com `ImportError` no collection (contrato não existia), depois `... — Green`
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 258 passed
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `max_request_chars` e as exceções adicionados ao contrato `Speaker` (`base.py`) como **extensão aditiva** (padrão das OS-021/022/025); `ARQUITETURA.md` seção 4.2 atualizada
- [x] Nenhuma chamada real a API paga dentro dos testes — tudo mockado
- [x] Type hints e docstring de uma linha em toda função pública — `max_request_chars`, exceções, `_split_by_char_limit`/`_merge_wav_files`/`_synthesize_with_retry` (helpers com docstring), `Config` com defaults
- [x] `PROJECT_STATE.md` atualizado (status do componente + achados)
- [x] Relatório criado em `docs/report/OS-043-report.md` (nunca dentro do arquivo da própria OS)
- [x] PR aberto contra o branch principal, com título no formato `[OS-043] descrição curta`

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_speaker_can_declare_own_size_limit` | `tests/unit/test_speaker_remote.py` | Sim |
| `test_kokoro_speaker_output_unchanged` | `tests/unit/test_speaker_remote.py` | Sim |
| `test_transient_failure_is_retried_with_backoff` | `tests/unit/test_speaker_remote.py` | Sim |
| `test_permanent_failure_fails_immediately` | `tests/unit/test_speaker_remote.py` | Sim |
| `test_retry_exhausted_keeps_persisted_chunks` | `tests/unit/test_speaker_remote.py` | Sim |
| `test_retry_count_is_configurable` | `tests/unit/test_speaker_remote.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? **Sim** — `git log` mostra `test: cobre limite declarado e retry do Speaker remoto (OS-043) — Red` seguido de `feat: implementa ... — Green`.

## 4. Saída de comandos relevantes

```
$ venv/bin/python -m pytest -q
258 passed, 1 warning in 13.09s

$ venv/bin/python -m ruff check core/ worker/ plugins/ tests/unit/test_speaker_remote.py
All checks passed!

$ venv/bin/python -m black --check core/pipeline.py core/config.py plugins/speakers/base.py worker/tasks.py tests/unit/test_speaker_remote.py
All done! ✨ 🍰 ✨
```

## 5. Decisões de implementação documentadas

1. **Onde mora o retry:** em `core/pipeline.py::synthesize_text()`, em volta da chamada `speaker.synthesize()` (via helper `_synthesize_with_retry`), como a OS indicava como candidato natural. O `KokoroSpeaker` nunca dispara retry porque não lança `TransientSpeakerError`.
2. **Backoff exponencial com teto:** `delay = min(base_delay × 2^(n-1), max_delay)`. Configurável no bloco `retry` do `config.yaml`; o `Config` dataclass carrega com defaults (3 tentativas, 1s base, 30s teto).
3. **Divisão por limite nunca corta palavra:** `_split_by_char_limit` agrupa palavras até o limite; palavra isolada maior que o limite vai inteira (caso de borda raro, mesmo espírito da divisão por fonemas do Kokoro). Os áudios dos pedaços são concatenados num único `AudioChunk` via `_merge_wav_files` (PCM16, mesmo sample rate), preservando a granularidade de `sequence`/retomada da OS-021/022.
4. **Esgotar o retry = `error` com preservação:** recomendação da OS seguida literalmente. O worker monta a mensagem: `"<erro> — falha de rede persistente após N tentativas. O áudio já sintetizado e persistido está preservado; reprocesse o livro para retomar do ponto em que parou."` A retomada usa o `skip_sequences` da OS-022 (nenhum chunk é apagado).
5. **`PermanentSpeakerError` não gasta tentativas:** só `TransientSpeakerError` é capturado pelo loop de retry. Exceções genéricas (não-SpeakerError) também sobem imediatamente — comportamento antigo preservado.

## 6. Desvios do escopo original

Nenhum desvio de escopo. Nota de processo: o branch foi criado a partir de `os/042-trava-de-custo` (e não de `main`) porque o PR #37 (OS-042) ainda está aberto e a OS-043 toca os mesmos arquivos (`synthesize_text`, `process_job`, `config.yaml`, FakeConfig de testes). Isso não muda o conteúdo da OS-043, mas o PR desta OS incorporará as mudanças da OS-042 até o merge daquele.

## 7. Dúvidas / bloqueios

- **Regressão visual do `KokoroSpeaker`:** a prova de "mesmo resultado de hoje" é via dublê do `KPipeline` (padrão da suíte), não com o Kokoro real gerando áudio. O teste confirma que `max_request_chars is None` e que o pipeline envia o texto inteiro numa chamada — a lógica de fonemas (OS-034/037) fica intocada no speaker. Não há achado de áudio divergente.
- **Formato de áudio para concatenação (OS-043 item (a)):** `_merge_wav_files` concatena arquivos PCM16 no mesmo sample rate. Um Speaker cloud futuro que devolva MP3/OGG precisará devolver PCM/WAV (ou o merge ganhar decodificação) — registrado aqui para a OS de implementação do Speaker pago, não decidido agora.

## 8. Link do PR

https://github.com/dinei84/listening/pull/38
