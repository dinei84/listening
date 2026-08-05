# OS-025 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/025-selecao-manual-idioma
**Commit(s) relevante(s):** 09b7cf9 (test: Red), a9b3161 (feat: Green)

## 1. Resumo do que foi feito

Seleção manual de idioma no upload do livro, com prioridade sobre a detecção automática da OS-020. `POST /books` aceita o campo de formulário opcional `language` (código tipo `langdetect`), validado contra as chaves de `LANG_CODE_BY_LANGUAGE`; o valor é persistido em `Book.language` (coluna nova `language` em `books`), repassado por `worker/tasks.py` (convertido pro lang_code do Kokoro) → `synthesize_text(lang_code=...)` → `KokoroSpeaker.synthesize(..., lang_code=...)`, que pula `_detect_lang_code()` mas continua passando por `_get_pipeline()` (fallback pra idioma indisponível no ambiente segue valendo). Sem escolha, tudo se comporta exatamente como antes (auto-detecção por chunk). O player ganhou um `<select>` com "Automático" (padrão) + os idiomas suportados.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `09b7cf9` "Red" antes de `a9b3161` "Green")
- [x] Todos os testes da OS passam localmente — 134 pass, 0 fail
- [x] Nenhum teste existente quebrou (123 anteriores + 11 novos = 134)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `Speaker.synthesize(text, voice=None, lang_code=None)` documentado na seção 4.2 antes de implementar; `Book.language` documentado na seção 5
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — `_build_pipeline()` mockado; FakeExtractor/FakeSpeaker nos testes de API/worker
- [x] Type hints e docstring de uma linha em toda função pública nova/alterada
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4 e 5)
- [x] Relatório criado em `docs/report/OS-025-report.md`
- [x] PR aberto contra o branch principal, título `[OS-025] ...`

### DoD específico da OS (`docs/os/OS-025-selecao-manual-idioma.md` seção 4)

- [x] Upload sem escolher idioma continua com detecção automática por chunk, comportamento idêntico ao de hoje — `test_synthesize_text_passes_none_lang_code_by_default`, `test_worker_process_job_passes_none_lang_code_without_book_language`, `test_create_book_without_language_defaults_to_auto` e a suíte inteira da OS-020 verde
- [x] Upload com idioma escolhido força esse `lang_code` em todos os chunks do livro, sem chamar `_detect_lang_code()` — `test_kokoro_speaker_synthesize_uses_forced_lang_code_when_given` (texto em inglês com `lang_code="p"` usa o pipeline `p` e a voz `pf_dora`, provando que a detecção foi pulada) + `test_synthesize_text_passes_lang_code_to_speaker` + `test_worker_process_job_passes_book_language_to_pipeline` (`["p", "p", "p"]` nos 3 chunks)
- [x] Idioma inválido/desconhecido enviado no upload não derruba o livro — escolha documentada: validação contra as chaves de `LANG_CODE_BY_LANGUAGE`; valor fora da lista degrada para `Book.language = None`, que é o mesmo que "Automático" (detecção por chunk). `test_create_book_with_invalid_language_falls_back_to_auto`
- [x] `Speaker.synthesize()` chamado sem `lang_code` continua se comportando exatamente como antes — `test_kokoro_speaker_synthesize_falls_back_to_detection_when_lang_code_is_none` (regressão da OS-020) + toda a suíte antiga dos speakers verde
- [x] UI mostra a lista de idiomas suportados, com "Automático" pré-selecionado como padrão — `<select id="language-select">` em `player/index.html` com `<option value="">Automático</option>` primeiro; `test_player_upload_form_has_language_select_with_auto_default`; verificação manual em navegador pendente (seção 6)

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_kokoro_speaker_synthesize_uses_forced_lang_code_when_given` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_synthesize_falls_back_to_detection_when_lang_code_is_none` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_synthesize_text_passes_lang_code_to_speaker` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_synthesize_text_passes_none_lang_code_by_default` (extra) | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_create_book_persists_chosen_language` | `tests/integration/test_api_books.py` | Sim |
| `test_create_book_without_language_defaults_to_auto` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_create_book_with_invalid_language_falls_back_to_auto` (extra, critério de aceite) | `tests/integration/test_api_books.py` | Sim |
| `test_worker_process_job_passes_book_language_to_pipeline` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_passes_none_lang_code_without_book_language` (extra) | `tests/unit/test_worker.py` | Sim |
| `test_db_create_and_get_book_roundtrip_persists_language` (extra) | `tests/unit/test_db.py` | Sim |
| `test_player_upload_form_has_language_select_with_auto_default` (extra, critério de aceite) | `tests/integration/test_player.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `09b7cf9` (9 falhas: `TypeError: synthesize() got an unexpected keyword argument 'lang_code'` no speaker e no pipeline, `AttributeError: 'Book' object has no attribute 'language'` na API/DB, `AssertionError: [None, None, None] == ['p', 'p', 'p']` no worker, e `AssertionError` no teste de UI) antes de `a9b3161`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação):
```
9 failed, 125 passed, 1 warning in 7.92s
```

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
134 passed, 1 warning in 7.95s
```

```
$ venv/bin/black --check plugins/ core/ storage/ api/ worker/ tests/
(reformatou 2 arquivos de teste; re-rodado e tudo estável)
$ venv/bin/ruff check plugins/ core/ storage/ api/ worker/ tests/
All checks passed!
```

`player/app.js` não passa pelo black (é JS; verificado por revisão de código).

## 5. Decisões de implementação

**Validação do `language` (decisão que a OS deixou em aberto, seção 2):** escolhida a validação contra as chaves de `LANG_CODE_BY_LANGUAGE` (`api/routes_books.py`), com valor inválido degradando para `Book.language = None`. Motivo: é o comportamento mais previsível ("inválido = automático", igual ao caso "não informado") e evita que um valor arbitrário viaje até o engine. A alternativa "deixar passar livre e cair no fallback pra inglês do `KokoroSpeaker`" foi descartada porque um lang_code desconhecido que por acaso construísse um pipeline quebraria no lookup `VOICE_BY_LANG_CODE` (KeyError) — ou seja, o fallback pro inglês só existe para idiomas **mapeados** que falham na construção, não para códigos desconhecidos.

**Tradução `language` → lang_code do Kokoro no worker:** `worker/tasks.py` faz `LANG_CODE_BY_LANGUAGE.get(book.language)` (None → automático) e repassa o código do Kokoro pra `synthesize_text()`, conforme a OS define (o `lang_code` do contrato `Speaker` é o código do engine, não o do `langdetect`). Isso importa `LANG_CODE_BY_LANGUAGE` de `plugins.speakers.kokoro_speaker` na API e no worker — um acoplamento a uma constante de plugin concreto que a própria OS instrui a "reaproveitar" (a tabela de tradução existe lá e não foi movida; não é import de classe de plugin, que continua proibido pela regra da seção 4.4, e sim de uma constante de mapeamento). Documentado aqui por transparência.

**Chinês na UI:** `LANG_CODE_BY_LANGUAGE` tem `zh-cn` e `zh-tw` (ambos → `z`); a UI expõe os dois como "Chinês (simplificado)" e "Chinês (tradicional)" para o valor enviado ser sempre uma chave válida. Japonês/mandarim continuam degradando pro inglês neste ambiente (achado da OS-020) — aparecem na lista de propósito, é limitação de ambiente, não da feature.

## 6. Verificação da UI (seletor de idioma)

Este projeto não tem suíte de testes JS (decisão #12, player em JS puro, sem build step). As mudanças em `player/index.html` (`<select>`) e `player/app.js` (`uploadBook()` anexando o campo `language`) foram validadas por revisão de código + `test_player_upload_form_has_language_select_with_auto_default` (verifica que o HTML servido contém o select com "Automático" como padrão). **Pendente: verificação manual em navegador real** de escolher um idioma, enviar um PDF de verdade e ouvir o áudio no idioma correto (mesma receita Playwright/Chrome real da OS-030; registrado em `PROJECT_STATE.md` seção 6).

## 7. Desvios do escopo original

Nenhum. Os arquivos tocados (11) estão todos dentro do escopo declarado na seção 2 da OS; o contrato `Speaker` foi alterado conforme a seção 3 da própria OS autoriza.

## 8. Dúvidas / bloqueios

Nenhum. Notas pro dono (nenhuma decisão deste agente):

1. O acoplamento da API/worker à constante `LANG_CODE_BY_LANGUAGE` de `kokoro_speaker.py` (seção 5) — se o projeto um dia tiver um segundo Speaker, essa constante provavelmente deverá virar algo neutro (ex: em `core/`), mas isso é decisão de arquitetura e fica registrado como observação.
2. A verificação manual do seletor de idioma em navegador real continua pendente (seção 6).

## 9. Link do PR

https://github.com/dinei84/listening/pull/24
