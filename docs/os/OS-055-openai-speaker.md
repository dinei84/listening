# OS-055 — `OpenAISpeaker` como Speaker de produção

## 1. Objetivo

Implementar o contrato `Speaker` para a OpenAI, para que o app tenha um segundo motor de verdade. É pré-requisito do roteamento híbrido (OS-056): sem dois motores registrados, não há para onde rotear.

## 2. Por que esta OS existe separada

O spike da OS-041/041B comparou quatro motores, mas **nenhum virou `Speaker`**. Até hoje:

```python
SPEAKERS = { "kokoro": KokoroSpeaker }   # plugins/registry.py
```

Todo teste de expressividade feito no app usou Kokoro, porque não havia alternativa registrada. O item 52 do backlog registra isso, e `plugins/speakers/cloud_speaker.py` existe com **0 bytes** desde sempre, sugerindo uma capacidade que não existe.

**Esta OS entrega valor sozinha:** com ela, `speaker: openai` no `config.yaml` faz o livro inteiro ser narrado pelo motor que o dono avaliou como superior — sem depender da OS-056.

## 3. Escopo

Alterados:

- `plugins/speakers/openai_speaker.py` — novo (o `cloud_speaker.py` vazio deve ser **apagado**, não reaproveitado: nome genérico para um adaptador específico).
- `plugins/registry.py` — registrar `"openai"`.
- `core/config.py` e `config.yaml` — bloco de configuração do Speaker pago.
- Testes correspondentes.

Fora de escopo:

- **Roteamento entre motores.** É a OS-056.
- **Azure, ElevenLabs e Chatterbox.** O contrato fica pronto para eles; implementá-los é OS por motor, quando houver decisão.
- **Escolha de voz da OpenAI pelo usuário.** A OS-053 fez isso para o Kokoro; estender ao novo motor exige catálogo próprio e é outra responsabilidade. Esta OS usa uma voz configurável em `config.yaml`.

## 4. Contratos envolvidos

Nenhum contrato muda — esta OS **implementa** um que já existe:

| Membro | O que a OpenAI exige |
|---|---|
| `cost_per_char` | **1,608e-05**, derivado do custo real medido: US$ 0,015 por 933 caracteres (painel da OpenAI, 11/08/2026). Livro de 533k chars → **US$ 8,58** |
| `max_request_chars` | **4096** — limite documentado da API. É o que faz a OS-043 dividir o texto antes de chamar |
| `synthesize(text, voice, lang_code)` | `POST /v1/audio/speech` |

A OS-043 já preparou o pipeline para Speaker remoto: `max_request_chars` faz o `_split_by_char_limit` agir, e `TransientSpeakerError`/`PermanentSpeakerError` alimentam o retry com backoff. Esta OS só precisa **classificar** os erros HTTP corretamente.

## 5. Detalhes já resolvidos no spike, que devem ser reaproveitados

O adaptador de `scripts/spike_tts_cloud.py` foi exercido com credencial real e tem duas lições que **não podem ser perdidas**:

- **Formato:** `response_format: "wav"` devolve RIFF com cabeçalho. Concatenar respostas inteiras mete cabeçalho no meio do áudio — o PCM precisa ser extraído de cada uma. Foi exatamente o erro que produziu estática na ElevenLabs.
- **`instructions`:** a `gpt-4o-mini-tts` aceita uma descrição em linguagem natural de *como* falar, e ela **não é faturada** no `input`. É a alavanca de estilo mais direta entre os provedores e deve ser configurável.

## 6. Classificação de erro, que a OS-043 exige

| HTTP | Classe | Motivo |
|---|---|---|
| 429, 5xx, timeout, erro de rede | `TransientSpeakerError` | retentável com backoff |
| 401, 403 | `PermanentSpeakerError` | credencial inválida; retentar só queima tempo |
| 400 | `PermanentSpeakerError` | texto rejeitado |

Sem chave configurada, o Speaker **não deve ser construído** — a config cai no Kokoro, como o `fallback_speaker` da OS-042 já prevê.

## 7. Decisão de produto registrada: falha rápida com aviso

Decidido pelo dono em 13/08/2026, depois de um `CUDA out of memory` derrubar um livro: **falhar rápido e avisar, em vez de degradar silenciosamente.** Vale para esta OS: falta de chave ou credencial inválida deve produzir mensagem clara no `Book.error_message`, não uma degradação que o usuário descobre pelo ouvido.

## 8. Critérios de aceite

- [ ] `OpenAISpeaker` implementa os três membros do contrato
- [ ] `cost_per_char` é 1,608e-05 e a estimativa da OS-042 usa ele sem alteração
- [ ] `max_request_chars` é 4096 e o pipeline divide o texto antes de chamar
- [ ] Texto acima de 4096 é sintetizado em pedaços e concatenado **sem cabeçalho no meio**
- [ ] 429 e 5xx viram `TransientSpeakerError`
- [ ] 401 vira `PermanentSpeakerError` com mensagem clara
- [ ] `instructions` é configurável e enviado quando presente
- [ ] Sem chave, o Speaker não é registrado e a config cai no Kokoro
- [ ] `cloud_speaker.py` (0 bytes) é apagado
- [ ] **Nenhum teste faz chamada paga** — o ponto que toca a rede é isolado e mockado
- [ ] Nenhum teste existente quebra (365 hoje)

## 9. Testes exigidos (mínimo)

- `test_openai_speaker_implements_contract`
- `test_openai_cost_per_char_matches_measured_price`
- `test_openai_declares_request_char_limit`
- `test_openai_splits_and_concatenates_without_nested_wav_header`
- `test_openai_maps_429_to_transient_error`
- `test_openai_maps_500_to_transient_error`
- `test_openai_maps_401_to_permanent_error`
- `test_openai_sends_instructions_when_configured`
- `test_registry_omits_openai_without_api_key`
- `test_estimate_cost_uses_openai_price`

## 10. Relatório

Ver `docs/report/OS-055-report.md`.
