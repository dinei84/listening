# OS-042 — Relatório de entrega (trava de custo)

**Data:** 2026-08-06
**Branch:** `os/042-trava-de-custo`
**Commit(s) relevante(s):** `test: cobre a trava de custo da OS-042 (estimativa, confirmação, teto) — Red` e `feat: implementa trava de custo da OS-042 (estimativa, confirmação, teto/degrade) — Green`

## 1. Resumo do que foi feito

Ligado o gancho `Speaker.cost_per_char` (dormante desde a OS-004) e implementadas as duas proteções da OS: **estimativa com confirmação explícita** e **teto de segurança**. `core/pipeline.py::estimate_cost()` calcula o custo a partir do texto real extraído (sanitizado, como a síntese o recebe) × `cost_per_char` do Speaker configurado; o worker persiste a estimativa no `Book` **antes** de qualquer chamada ao Speaker e aplica o gate: estimativa > 0 sem confirmação deixa o livro em `pending_confirmation` (a confirmação re-enfileira um Job novo); estimativa acima do teto `max_cost_per_book` degrada para a voz local (`fallback_speaker`) mesmo confirmado — o Speaker pago nunca roda nesse caso. UI mostra a estimativa + botão de confirmar e o aviso de degradação. Livro de custo zero (Kokoro) processa direto, sem mudança de comportamento — regressão coberta por teste.

## 2. Checklist de DoD

### DoD específico da OS (`docs/os/OS-042-trava-de-custo.md` seção 4)

- [x] A estimativa é calculada a partir do texto real extraído e do `cost_per_char` do `Speaker` configurado — `estimate_cost()` soma `len(sanitize_text(texto)) × cost_per_char` por capítulo; teste `test_estimate_cost_uses_speaker_cost_per_char`
- [x] Livro com estimativa **zero** (Kokoro) processa direto, sem confirmação e sem mudança de comportamento — regressão do fluxo atual; teste `test_zero_cost_book_processes_without_confirmation`
- [x] Livro com estimativa **maior que zero** não é sintetizado antes de confirmação explícita — fica em `pending_confirmation`, nenhum `AudioChunk` criado; testes `test_paid_book_is_not_synthesized_before_confirmation` e `test_paid_book_waits_for_confirmation_after_worker`
- [x] Estimativa acima do teto de `config.yaml` não processa mesmo confirmada; o comportamento escolhido está documentado — **comportamento escolhido: degradar para a voz local** (recomendação da OS); `cost_degraded` persistido e `speaker_name="kokoro"` (fallback) na síntese; Speaker pago nunca chamado; teste `test_estimate_above_cap_does_not_process_even_when_confirmed`. Ver seção 5 para a justificativa documentada
- [x] O usuário vê o valor estimado antes de confirmar, e vê o motivo quando o teto barra — UI: `pending_confirmation` mostra estimativa + "Confirmar custo estimado" (na lista e no player); livro degradado mostra "Processado com voz local — o custo estimado ultrapassou o teto configurado."
- [x] A estimativa acontece **antes** de qualquer chamada ao `Speaker` — teste `test_estimate_happens_before_any_speaker_call` (o Speaker dublê falha se a estimativa não estiver persistida quando for chamado)
- [x] Nenhuma chamada de rede ou API paga na suíte — dublês `PaidSpeaker`/`LocalSpeaker`/`EstimateAwareSpeaker`; nenhum teste chama API externa
- [x] Nenhum teste das OS-021/022/024/032 quebra — 252 testes passando (ver seção 3)

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit dos testes falhando existe no histórico do branch) — commit `... — Red` com os 6 testes da OS falhando; depois o `... — Green`
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 252 passed (247 anteriores + 5 novos de API/status)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `Speaker.cost_per_char` respeitado; `synthesize_text()` ganhou `speaker_name` como extensão **aditiva** (mesmo padrão das OS-021/022/025), sem alterar `plugins/speakers/base.py`; `ARQUITETURA.md` seção 4.2 atualizada
- [x] Nenhuma chamada real a API paga (OCR cloud, TTS cloud) dentro dos testes — tudo mockado
- [x] Type hints e docstring de uma linha em toda função pública — `estimate_cost()`, `synthesize_text()`, setters de `db.py`, rota `confirm_book_cost()`, fixture helpers
- [x] `PROJECT_STATE.md` atualizado (status do componente + decisões novas, se houver)
- [x] Relatório criado em `docs/report/OS-042-report.md` (nunca dentro do arquivo da própria OS)
- [x] PR aberto contra o branch principal, com título no formato `[OS-042] descrição curta`

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_estimate_cost_uses_speaker_cost_per_char` | `tests/unit/test_cost_control.py` | Sim |
| `test_zero_cost_book_processes_without_confirmation` | `tests/unit/test_cost_control.py` | Sim |
| `test_paid_book_is_not_synthesized_before_confirmation` | `tests/unit/test_cost_control.py` | Sim |
| `test_confirmed_book_proceeds_to_synthesis` | `tests/unit/test_cost_control.py` | Sim |
| `test_estimate_above_cap_does_not_process_even_when_confirmed` | `tests/unit/test_cost_control.py` | Sim |
| `test_estimate_happens_before_any_speaker_call` | `tests/unit/test_cost_control.py` | Sim |
| `test_status_exposes_cost_estimate_fields` | `tests/integration/test_api_books.py` | Sim |
| `test_paid_book_waits_for_confirmation_after_worker` | `tests/integration/test_api_books.py` | Sim |
| `test_confirm_endpoint_confirms_and_reprocesses` | `tests/integration/test_api_books.py` | Sim |
| `test_confirm_endpoint_returns_404_for_unknown_book` | `tests/integration/test_api_books.py` | Sim |
| `test_confirm_endpoint_returns_409_for_book_not_waiting` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? **Sim** — `git log` mostra `test: cobre a trava de custo da OS-042 ... — Red` seguido de `feat: implementa trava de custo da OS-042 ... — Green`.

## 4. Saída de comandos relevantes

```
$ venv/bin/python -m pytest -q
252 passed, 1 warning in 12.17s

$ venv/bin/python -m ruff check core/ storage/ worker/ api/ tests/unit/test_cost_control.py
All checks passed!

$ venv/bin/python -m black --check core/models.py core/config.py core/pipeline.py storage/db.py worker/tasks.py api/routes_books.py tests/unit/test_cost_control.py
All done! ✨ 🍰 ✨
```

## 5. Decisões de implementação documentadas

1. **Comportamento acima do teto: degradar (não recusar).** A OS oferece as duas opções e recomenda degradar ("entregar o livro com voz local é melhor que não entregar"). Escolhido o degradar: acima de `max_cost_per_book`, o livro é marcado `cost_degraded` e sintetizado com `fallback_speaker` (padrão `kokoro`) — o Speaker pago **nunca** é chamado, mesmo que o usuário confirme. A mensagem de aviso aparece na UI. `cost_per_char == 0.0` identifica a voz local; o nome do fallback fica em `config.yaml` (`fallback_speaker`) para não acoplar o worker a um nome específico.
2. **`synthesize_text()` ganhou `speaker_name` como parâmetro aditivo** (None = Speaker configurado). Necessário para a degradação usar a voz local sem tocar no contrato `Speaker` (`plugins/speakers/base.py` não mudou). Mesmo padrão de extensão aditiva das OS-021/022/025.
3. **Confirmação re-enfileira um Job novo, em vez de retomar o mesmo.** Quando o livro entra em `pending_confirmation`, o Job da rodada de extração+estimativa é encerrado (`mark_done`); o `POST /books/{id}/confirm` marca `cost_confirmed`, volta o status a `uploaded` e enfileira um Job novo. Motivo: `claim_next()` só enxerga `queued`, e deixar o mesmo Job em `running`/`queued` faria o worker re-processar sem confirmação (ou parar de reivindicar). A re-extração na rodada pós-confirmação é o mesmo comportamento já existente da retomada (OS-022), que sempre re-extrai.
4. **Estimativa em dólar dos provedores, exibida com `USD`.** `cost_per_char` dos speakers cloud (OS-041) está em USD; a UI formata como moeda USD. O teto `max_cost_per_book` é na mesma unidade (documentado no `config.yaml`).
5. **LLM (OS-038) deve reaproveitar este mesmo mecanismo** quando existir — o registro está na OS-042 ("Fora do escopo"), e o `estimate_cost`/`pending_confirmation`/teto é genérico o bastante para o custo de LLM se plugar no mesmo fluxo.

## 6. Desvios do escopo original

Nenhum. As 4 decisões da seção 5 são de implementação dentro do escopo declarado (a OS explicitamente delega a decisão teto = recusar vs degradar). Nenhum arquivo de produção fora dos módulos esperados foi alterado (`core/`, `storage/`, `worker/`, `api/`, `player/`, `config.yaml`).

## 7. Dúvidas / bloqueios

- **Schema sem migração (dívida conhecida, repetida):** a tabela `books` ganhou `estimated_cost`, `cost_confirmed` e `cost_degraded`. Qualquer `books.db` local criado antes da OS-042 quebrará com `table books has no column named estimated_cost` — apagar `books.db` (RUNBOOK.md seção 6/8) recria o schema. Não é decisão nova: é a dívida registrada em `PROJECT_STATE.md` seção 6, e esta OS não a resolve (candidata a OS própria).
- **Teto de custo em unidade USD:** o `max_cost_per_book` de `config.yaml` usa a mesma unidade de `cost_per_char` (USD nos provedores cloud da OS-041). Com o Kokoro (custo zero) o teto é irrelevante hoje; o primeiro Speaker pago que adotar outra moeda precisa documentar/ajustar a unidade junto com o valor do teto.

## 8. Link do PR

https://github.com/dinei84/listening/pull/37
