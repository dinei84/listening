# OS-019 — Corrige o `KokoroSpeaker` para usar a API certa do Kokoro (G2P real)

> **Esta OS continua em cima do branch `os/018-kokoro-limite-fonemas` (PR #16), não parte de `main`.** A OS-018 corrigiu o sintoma (crash em texto longo) mas usando a API errada do Kokoro; esta OS corrige a causa raiz no mesmo branch, antes de qualquer merge. Não abrir branch nova.

## 1. Objetivo

`KokoroSpeaker.synthesize()` chama `pipeline.generate_from_tokens(text, ...)` passando texto bruto em inglês. Esse método, quando recebe uma `string`, **trata ela como se já fosse uma transcrição fonética (IPA)** — pula a etapa de G2P (grafema→fonema) por completo (ver `kokoro/pipeline.py`, docstring de `generate_from_tokens`: "Generate audio from either raw phonemes or pre-processed tokens"). Confirmado empiricamente: para o texto `"The quick brown fox jumps over the lazy dog."`, o G2P real do Kokoro produz `'ðə kwˈɪk bɹˈWn fˈɑks ʤˈʌmps ˈOvəɹ ðə lˈAzi dˈɔɡ.'` — completamente diferente do texto bruto que estava sendo enviado no lugar disso. **Todo áudio gerado pelo projeto desde a OS-004 provavelmente está mal pronunciado.** Os testes nunca pegaram isso porque só verificam propriedades estruturais do áudio (arquivo existe, duração > 0), nunca o conteúdo fonético.

Também descoberto: o método certo (`pipeline(text, voice=..., speed=...)`, ou seja, chamar o pipeline diretamente / `__call__`) já faz G2P real **e** já divide texto longo em pedaços que cabem no limite de 510 fonemas automaticamente, respeitando fronteiras de frase (`en_tokenize`) — testado com 1350 caracteres, devolveu 3 pedaços de ~489 fonemas cada, sem nenhuma divisão manual. Ou seja: a lógica de divisão recursiva por palavra que a OS-018 implementou (`_generate_audio`, `_split_in_half_by_word`, `PHONEME_LIMIT_ERROR`, `MAX_SPLIT_DEPTH`) fica **desnecessária** depois desta correção — o Kokoro já resolve isso sozinho, e melhor (respeitando fonemas/frases, não palavras arbitrárias).

## 2. Escopo

**Dentro do escopo:**
- `plugins/speakers/kokoro_speaker.py`:
  - Trocar a chamada de `pipeline.generate_from_tokens(text, voice=voice, speed=speed)` para `pipeline(text, voice=voice, speed=speed)` (o `__call__` do `KPipeline`).
  - Remover a lógica de divisão/retry adicionada na OS-018 (`_generate_audio` recursivo, `_split_in_half_by_word`, `PHONEME_LIMIT_ERROR`, `MAX_SPLIT_DEPTH`) — fica morta depois da correção, já que o Kokoro passa a lidar com texto longo internamente.
  - A agregação de áudio continua a mesma ideia: iterar os `Result`s devolvidos (agora por `pipeline()`, que pode devolver mais de um `Result` pra texto longo — cada um já é um pedaço válido, dentro do limite), concatenar `result.output.audio` de cada um, gravar um `.wav` só. `synthesize()` continua devolvendo um único `AudioChunk` — contrato do `Speaker` inalterado.
- `processing/chunker.py`: reconsiderar o `DEFAULT_MAX_CHARS = 480` da OS-018 — foi calibrado em cima do limite errado (limite de **caracteres brutos** da API mal usada, não fonemas de verdade). Com a correção, o Kokoro lida com texto longo internamente, então o valor de `DEFAULT_MAX_CHARS` deveria voltar a ser decidido pela razão original da OS-008 (nº de chamadas ao Speaker por capítulo, tamanho previsível de `AudioChunk` pra playback) — não pelo limite do engine. Reverter para `1000` (valor original da OS-008) a menos que haja uma razão nova e documentada pra escolher outro número.
- Testes: atualizar `tests/unit/speakers/test_kokoro_speaker.py` — os dublês de pipeline (`FakePipeline`, `SplitAwarePipeline`, `AlwaysRejectingPipeline`) simulavam `generate_from_tokens`; precisam simular `__call__` (`pipeline(text, voice=voice, speed=speed)`) em vez disso. Remover os testes específicos da lógica de split/retry da OS-018 (não existe mais) e adicionar um teste confirmando que múltiplos `Result`s devolvidos por uma chamada (simulando o Kokoro dividindo texto longo sozinho) são concatenados num único `AudioChunk`.
- **Evidência empírica no relatório:** reproduzir a comparação de fonemas (texto bruto vs. G2P real) que motivou esta OS, e confirmar que a nova implementação usa o G2P de verdade — mesmo padrão de validação empírica já usado nas OS-005/006/017/018.
- `RUNBOOK.md`: adicionar uma nota em "Problemas comuns" avisando que livros processados **antes** desta correção têm pronúncia incorreta e precisam ser reenviados.
- `PROJECT_STATE.md`: registrar esta descoberta como decisão/achado — é um bug de correção de áudio presente desde a OS-004, relevante o bastante pra ficar no histórico.

**Fora de escopo:**
- Qualquer verificação de qualidade de áudio via transcrição automática (Whisper ou similar) — adicionaria uma dependência pesada nova só pra essa validação; a evidência de que o G2P certo está sendo chamado (comparação de fonemas) já é suficiente.
- Reprocessar automaticamente livros já enviados — o dono do projeto reenvia manualmente (nota já adicionada ao `RUNBOOK.md`).
- Qualquer mudança em `core/pipeline.py`, `worker/tasks.py`, ou no campo `error_message` já adicionado pela OS-018 (esse ficou bom, não mexer).
- `split_pattern` do `__call__` (default `r'\n+'`) — o texto que chega em `synthesize()` vem de `processing.chunker.chunk_text()`, que junta sentenças com espaço, não quebra de linha; não deve haver divisão extra inesperada, mas vale um teste confirmando isso (ver seção 5), não uma mudança de comportamento.

## 3. Contratos envolvidos

Nenhuma mudança no contrato `Speaker` (`ARQUITETURA.md` seção 4.2). Correção interna de implementação.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `KokoroSpeaker` chama `pipeline(text, voice=voice, speed=speed)`, não `pipeline.generate_from_tokens(...)`
- [ ] Lógica de divisão/retry da OS-018 removida (código morto depois da correção)
- [ ] `synthesize()` continua devolvendo um único `AudioChunk`, mesmo quando o Kokoro internamente devolve múltiplos `Result`s pra texto longo
- [ ] `processing/chunker.py`: `DEFAULT_MAX_CHARS` revisto — reverter para `1000` ou justificar um valor diferente com uma razão que não seja "limite do engine" (isso o Kokoro resolve sozinho agora)
- [ ] Relatório inclui a comparação de fonemas (texto bruto vs. G2P real) como evidência de que a correção funciona
- [ ] Testes mockam `__call__` do pipeline (não mais `generate_from_tokens`), nenhum teste chama o Kokoro real
- [ ] `RUNBOOK.md` avisa sobre a necessidade de reenviar livros processados antes desta correção
- [ ] `PROJECT_STATE.md` registra o achado (bug de pronúncia presente desde a OS-004, corrigido aqui)
- [ ] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 5. Testes exigidos (mínimo)

- `test_kokoro_speaker_calls_pipeline_directly_not_generate_from_tokens`
- `test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro` (adaptar o existente pro novo dublê)
- `test_kokoro_speaker_concatenates_multiple_results_into_single_audio_chunk` (simula o Kokoro devolvendo 2+ `Result`s pra um texto longo, confirma que vira um `AudioChunk` só)
- `test_kokoro_speaker_synthesize_writes_audio_file` (adaptar o existente)

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-019-report.md` (template em `docs/report/REPORT_TEMPLATE.md`). Incluir a comparação de fonemas como evidência, mesmo padrão da descoberta que motivou esta OS.*
