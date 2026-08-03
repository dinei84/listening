# OS-004 — Speaker base + KokoroSpeaker (TTS local)

## 1. Objetivo

Implementar o contrato `Speaker` (hoje um stub vazio) e sua primeira implementação concreta, `KokoroSpeaker`, usando o engine de TTS local Kokoro (`kokoro==0.9.4`, já em `requirements.txt`) — o caminho padrão e sem custo do pipeline, conforme `ARQUITETURA.md` seção 4.2.

## 2. Escopo

**Dentro do escopo:**
- `plugins/speakers/base.py` — classe abstrata `Speaker` com `synthesize(text: str, voice: str | None = None) -> AudioChunk` e a property abstrata `cost_per_char -> float`, exatamente como especificado em `ARQUITETURA.md` seção 4.2.
- `plugins/speakers/kokoro_speaker.py` — `KokoroSpeaker(Speaker)`:
  - `cost_per_char` retorna `0.0` (engine local).
  - `synthesize()` chama o engine Kokoro, salva o áudio gerado em disco (usar `soundfile`, já em `requirements.txt`) e retorna um `AudioChunk` com `engine_used="kokoro"` e `duration_seconds` calculado a partir do áudio gerado.
  - `AudioChunk.chapter_id` e `AudioChunk.sequence` podem ficar com valores de placeholder (ex: string vazia / `0`) nesta OS — quem preenche esses campos de verdade é o `core/pipeline.py`, que ainda não existe (OS futura). O foco aqui é a síntese em si, não a integração com pipeline.

**Fora do escopo:**
- `PiperSpeaker`, `CloudSpeaker` — OS's futuras.
- `plugins/registry.py` — wiring do registry é de uma OS futura, quando houver mais de um speaker concreto para registrar.
- `core/pipeline.py` — nenhuma orquestração é chamada aqui.
- Qualquer chamada de rede ou API paga.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.2 (Speaker). Esta OS implementa o contrato já definido — não propõe nenhum novo. Se a assinatura precisar mudar durante a implementação, isso exige atualizar `ARQUITETURA.md` primeiro, não decidir sozinho.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `Speaker` não pode ser instanciada diretamente (é uma ABC com `synthesize()` e `cost_per_char` abstratos)
- [ ] `KokoroSpeaker.cost_per_char == 0.0`
- [ ] `KokoroSpeaker.synthesize()` retorna um `AudioChunk` com `engine_used == "kokoro"`
- [ ] `KokoroSpeaker.synthesize()` produz um arquivo de áudio no `file_path` retornado
- [ ] **Nenhum teste invoca o modelo Kokoro real** — a chamada de inferência (carregar pesos, gerar áudio) deve ser mockada; testes que precisarem de um arquivo de áudio de verdade para validar leitura/duração podem gerar um `.wav` sintético curto via `soundfile` diretamente no teste, sem passar pelo Kokoro
- [ ] Nenhum teste escreve fora de um diretório temporário (`tmp_path` do pytest) — não deixar arquivo de áudio gerado no repositório

## 5. Testes exigidos (mínimo)

- `test_speaker_cannot_be_instantiated_directly`
- `test_kokoro_speaker_cost_per_char_is_zero`
- `test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro`
- `test_kokoro_speaker_synthesize_writes_audio_file`

Local sugerido: `tests/unit/speakers/test_kokoro_speaker.py` (diretório já existe).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-004-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
