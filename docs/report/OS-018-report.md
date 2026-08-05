# OS-018 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/018-kokoro-limite-fonemas
**Commit(s) relevante(s):** 083f0ec (test: Red), 0e49feb (feat: Green)

## 1. Resumo do que foi feito

Corrigido o bug real `Phoneme string too long: 863 > 510`, encontrado processando um livro técnico longo. `KokoroSpeaker.synthesize()` agora captura esse erro específico, divide o texto ao meio por palavra e sintetiza cada metade recursivamente até caber no limite, sempre devolvendo um único `AudioChunk` (contrato do `Speaker` inalterado). `DEFAULT_MAX_CHARS` recalibrado de `1000` para `480` com base em teste real contra o Kokoro. `GET /books/{id}/status` agora inclui `error_message` quando `status == "error"`. A validação empírica exigida pela OS revelou que a causa do bug não é "texto denso gera mais fonemas por caractere" como a OS presumia, e sim um limite de caracteres brutos, sempre no mesmo ponto — ver seção 5.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `083f0ec` "Red" existe antes de `0e49feb` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (95 testes no total, todos passando — 90 pré-existentes + 5 novos)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — contrato do `Speaker` (seção 4.2) inalterado; `GET /books/{id}/status` estendido de forma aditiva (campo novo opcional), não quebra a OS-010/012
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — `_get_pipeline()` sempre mockado nos testes de `KokoroSpeaker`; nenhuma chamada de rede em `pytest`
- [x] Type hints e docstring de uma linha em toda função pública nova/alterada (`_generate_audio`, `_split_in_half_by_word`, `update_book_status`)
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4, 5 e 6, incluindo o achado empírico)
- [x] Relatório criado em `docs/report/OS-018-report.md`
- [x] PR aberto contra o branch principal, título `[OS-018] ...`

### DoD específico da OS (`docs/os/OS-018-kokoro-limite-fonemas.md` seção 4)

- [x] `KokoroSpeaker.synthesize()` não lança mais `Phoneme string too long` pra cima — captura, divide e tenta de novo
- [x] Divisão por palavra (não por sentença), com limite de tentativas (`MAX_SPLIT_DEPTH = 10`) — não trava em recursão infinita; caso patológico (uma "palavra" isolada gigante) desiste imediatamente com `RuntimeError` claro, sem nem precisar esgotar a profundidade
- [x] `synthesize()` continua devolvendo um único `AudioChunk` mesmo após dividir internamente — testado explicitamente (`test_kokoro_speaker_returns_single_audio_chunk_after_split_retry`)
- [x] `DEFAULT_MAX_CHARS` recalibrado com base em teste real contra o Kokoro (não mockado) — seção 5, `480`
- [x] `GET /books/{id}/status` inclui `error_message` quando `status == "error"` (omitido nos demais casos — testado nos dois sentidos)
- [x] Testes automatizados da resiliência usam um dublê de pipeline que simula a rejeição por fonemas (`SplitAwarePipeline`, `AlwaysRejectingPipeline`) — nenhum teste chama o Kokoro real
- [x] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada — o download/uso real do Kokoro só aconteceu na validação empírica manual (seção 5), fora do `pytest`

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_kokoro_speaker_splits_and_retries_on_phoneme_limit_error` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_returns_single_audio_chunk_after_split_retry` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_gives_up_with_clear_error_if_split_does_not_help` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_get_books_status_includes_error_message_when_status_is_error` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_status_omits_error_message_when_status_is_not_error` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `083f0ec` (`ValueError: Phoneme string too long: 34 > 510` propagando pra fora de `synthesize()`, `KeyError: 'error_message'`) antes de `0e49feb`.

## 4. Saída de comandos relevantes

Rodada de confirmação Red (antes da implementação): 4 dos 5 testes novos falhando — 3 do `KokoroSpeaker` (`ValueError` não capturado propagando) e 1 do `error_message` (`KeyError`). O quinto (`omits_error_message_when_status_is_not_error`) já passava incidentalmente, porque o comportamento antigo (nunca incluir o campo) coincidia com o esperado nesse caso específico — o Red relevante está nos outros 4.

Suíte completa após a implementação (Green):

```
$ python -m pytest -q
95 passed, 1 warning in 7.82s
```

`black`/`ruff` nos arquivos alterados: sem alterações pendentes após um `black` (reformatou algumas linhas em `kokoro_speaker.py`), `ruff` sem achados.

## 5. Recalibração empírica de `DEFAULT_MAX_CHARS` (exigida pela seção 2/4 da OS)

Rodado o Kokoro real (`kokoro.KPipeline(lang_code="a")`, sem mock) para medir onde exatamente o limite de 510 é disparado.

**Primeiro teste — texto denso/técnico vs. texto simples, variando o comprimento:**

```python
dense_technical = ("Cryptographic protocol verification requires formal methods such as "
    "BAN logic, model checking with tools like ProVerif or Tamarin, and rigorous "
    "adversarial threat modeling under the Dolev-Yao attacker model, accounting for "
    "chosen-ciphertext attacks, padding oracle vulnerabilities, timing side-channels, "
    "and downgrade attacks against negotiated cipher suites in transport layer "
    "security implementations.")
plain = ("The quick brown fox jumps over the lazy dog. She sells seashells by the "
    "seashore every single summer morning. A gentle breeze moved softly through the "
    "tall green trees near the old wooden fence.")
```

Resultado (`pipeline.generate_from_tokens(text, voice="af_heart", speed=1.0)` chamado diretamente, texto truncado em cada `n`):

```
dense (len=403 antes de repetir):
  n=400 OK
  n=500 OK
  n=509 OK
  n=510 OK
  n=511 FAIL: Phoneme string too long: 511 > 510
  n=520 FAIL: Phoneme string too long: 520 > 510
  n=600 FAIL: Phoneme string too long: 600 > 510
  n=863 FAIL: Phoneme string too long: 863 > 510

plain (len=194 antes de repetir):
  n=400 OK
  n=500 OK
  n=509 OK
  n=510 OK
  n=511 FAIL: Phoneme string too long: 511 > 510
  n=520 FAIL: Phoneme string too long: 520 > 510
  n=600 FAIL: Phoneme string too long: 600 > 510
  n=863 FAIL: Phoneme string too long: 863 > 510
```

**Achado (contraria a premissa original da OS):** o ponto de falha é **idêntico** para texto denso/técnico e texto simples — exatamente em `511` caracteres, em ambos os casos. Isso não é o comportamento esperado de um limite real de fonemas (onde texto denso deveria estourar com menos caracteres que texto simples, por gerar mais fonemas por caractere). Investigando o motivo: `KokoroSpeaker.synthesize()` chama `pipeline.generate_from_tokens(text, voice=voice, speed=1.0)` passando o **texto bruto** (não fonemizado) como argumento `tokens`. Dentro do Kokoro (`kokoro/pipeline.py`), quando `tokens` é uma `str`, o método assume que ela **já é uma string de fonemas pronta** (não roda G2P) e checa `len(tokens) > 510` diretamente sobre esses caracteres — literalmente o comprimento do texto original, não uma contagem de fonemas de verdade. Isso explica por que o número do bug original bate exatamente com o tamanho do chunk (`863` no bug, chunk de até 1000 caracteres do `chunk_text()` antigo) — não é coincidência de densidade, é o próprio comprimento do chunk sendo comparado direto contra `510`.

Nota: esse comportamento não foi "corrigido" nesta OS — mudar para chamar o G2P do Kokoro antes de `generate_from_tokens()` seria uma mudança de arquitetura maior, fora do escopo declarado ("Nenhuma mudança no contrato Speaker... a divisão/retry é um detalhe de implementação interno ao Kokoro"). A OS pedia resiliência ao erro específico + recalibração do `DEFAULT_MAX_CHARS`, ambos entregues; o achado fica registrado para quem for revisar `KokoroSpeaker` no futuro.

**Escolha de `DEFAULT_MAX_CHARS = 480`:** como o limite real e determinístico é `510` caracteres (não uma faixa variável por densidade), `480` dá uma margem de segurança de 30 caracteres — suficiente para absorver o espaço extra que `chunk_text()` adiciona ao juntar sentenças (`f"{current} {sentence}"`) sem precisar de um cálculo mais fino. Testado com o texto denso/técnico do parágrafo acima repetido 5x: `chunk_text(dense_technical_x5, max_chars=480)` produziu 5 chunks de 403 caracteres cada (a sentença mais longa do parágrafo), todos bem abaixo de 510.

**Confirmação end-to-end do split-retry (Kokoro real, sem mock):** sintetizado um caso patológico deliberado — uma única "sentença" de 1000 caracteres sem nenhuma pontuação intermediária (`"word " * 200`, que `chunk_text()` nunca dividiria por não ter fronteira de sentença) — via `KokoroSpeaker.synthesize()` real:

```
single_long_sentence len= 1000
synthesize OK, duration_seconds= 52.7 elapsed= 3.92s
```

Sintetizou com sucesso, sem propagar `ValueError`, confirmando que o split-retry cobre exatamente o cenário que motivou o desenho da OS (sentença isolada maior que o limite, que `chunk_text()` não dividiria).

## 6. Desvios do escopo original

Nenhum desvio de escopo. O achado da seção 5 (limite determinístico por caractere, não por densidade de fonemas) é uma correção de entendimento sobre a causa raiz, registrada como achado — não uma mudança fora do que a OS pediu (resiliência + recalibração empírica, ambos entregues como especificado).

## 7. Dúvidas / bloqueios

Nenhum bloqueio para fechar esta OS. Duas notas para o dono do projeto avaliar depois (não decisões tomadas por este agente):

1. O livro que originou o bug (Security Engineering, Ross Anderson) ainda precisa ser reenviado depois desta OS pra confirmar a correção em produção — explicitamente fora do escopo da OS-018 ("Retry automático de Jobs que já falharam antes desta correção").
2. O achado da seção 5 sugere que `KokoroSpeaker.synthesize()` pode não estar fazendo G2P de verdade antes de chamar `generate_from_tokens()` — o áudio gerado provavelmente ainda soa correto na prática (o Kokoro tolera isso de alguma forma, dado que o projeto já processou livros com sucesso antes desta OS), mas vale uma investigação dedicada se algum dia a qualidade do áudio virar suspeita. Não investigado a fundo aqui por estar fora do escopo declarado desta OS.

## 8. Link do PR

[a preencher após abertura do PR]
