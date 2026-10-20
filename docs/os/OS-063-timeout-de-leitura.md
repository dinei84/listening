# OS-063 — Timeout de leitura mata o livro

## 1. Objetivo

Classificar o timeout de leitura da OpenAI como falha transitória, para o retry
da OS-043 agir — hoje ele escapa de toda a classificação e derruba o livro.

Bug achado na **primeira rodada real de um livro inteiro**, em 20/10/2026.

## 2. Escopo

### O defeito, reproduzido

```
TimeoutError e subclasse de URLError? False
socket.timeout e TimeoutError?        True

RESULTADO: ESCAPOU sem classificacao -> TimeoutError: The read operation timed out
```

`OpenAISpeaker._call_api` captura `urllib.error.HTTPError` e
`urllib.error.URLError`. Mas o timeout de **leitura** acontece no
`response.read()`, **depois** de a conexão estar estabelecida — e aí o
`http.client` levanta `TimeoutError` cru, que **não** é subclasse de `URLError`.

Sem classificação, ele passa pelo `_synthesize_with_retry` (que só captura
`TransientSpeakerError`), sobe até o worker e marca o livro como `error`.

### Por que os testes não pegaram

`test_openai_network_failure_is_transient` levanta
`urllib.error.URLError("conexão recusada")` — falha de **conexão**, que de fato é
`URLError`. O caso real é outro: conexão aberta, resposta lenta. É a quinta vez
neste projeto que algo passa em teste mockado e falha em uso real.

### Impacto medido na rodada

| | |
|---|---|
| trechos sintetizados antes de morrer | **10 de 641** |
| motor usado | **100% Kokoro** — nenhuma chamada paga completou |
| gasto em TTS | US$ 0,00 |
| tempo até a falha | 3 min |

O primeiro chunk roteado para a OpenAI foi o primeiro a falhar, e levou o livro
inteiro junto.

### Alterados

- `plugins/speakers/openai_speaker.py` — classificação do erro.
- Testes correspondentes.

### Fora de escopo

- **Caminho para retomar um livro em `error`.** Não existe hoje: `confirm` exige
  `pending_confirmation` e `prioritize` devolve 409 para `error`. Nesta rodada não
  custa nada (os 10 trechos são Kokoro, gratuitos, e reenviar refaz em ~1 min),
  mas é lacuna real — **registrar no backlog**, não resolver aqui.
- ~~**A mesma exposição no `LLMNormalizer`.**~~ **Verificado durante a execução:
  não tem.** Ele envolve a chamada em `except Exception` e degrada para o texto
  original com aviso (`llm_normalizer.py:88`), então um timeout ali custa a
  normalização daquele trecho, não o livro. A suposição registrada ao abrir a OS
  estava errada, e não virou item de backlog.
- **Revisar o valor de 120 s do timeout.** Com chunk de até 1.000 caracteres, 120 s
  é folgado; o problema não é o valor, é o que acontece quando ele estoura.

## 3. Contratos envolvidos

Nenhum contrato muda. A OS-043 já define que `TransientSpeakerError` é retentado
com backoff e `PermanentSpeakerError` não — esta OS só faz um erro que estava
**fora das duas categorias** cair na categoria certa.

## 4. Critérios de aceite

- [ ] `TimeoutError` de leitura vira `TransientSpeakerError`
- [ ] `socket.timeout` (que é o mesmo objeto) também
- [ ] Falha de conexão (`URLError`) continua transitória, como já era
- [ ] `HTTPError` continua sendo classificado antes, por status (não pode virar genérico)
- [ ] 401 continua `PermanentSpeakerError`
- [ ] 429 por falta de crédito continua `PermanentSpeakerError`
- [ ] Erro de rede de qualquer natureza (`OSError`) é transitório, não escapa
- [ ] A mensagem do erro diz que vale retentar
- [ ] Nenhum teste existente quebra (522 hoje)

## 5. Testes exigidos (mínimo)

- `test_openai_read_timeout_is_transient`
- `test_openai_socket_timeout_is_transient`
- `test_openai_generic_oserror_is_transient`
- `test_openai_connection_failure_is_still_transient`
- `test_openai_http_error_is_classified_before_generic_oserror`
- `test_openai_insufficient_quota_is_still_permanent`

## 6. Relatório

Ver `docs/report/OS-063-report.md`.
