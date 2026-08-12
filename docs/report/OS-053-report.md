# OS-053 — Relatório de entrega

**Data:** 12/08/2026
**Branch:** `os/053-escolha-de-voz`
**Commit(s) relevante(s):** `686d358` (Red), `9a0977e` (Green)

## 1. Resumo do que foi feito

O usuário passou a escolher a voz do livro no envio, em vez de receber sempre a voz fixa do idioma. A voz percorre o caminho inteiro: `POST /books` aceita e valida o campo contra o idioma escolhido → `Book.voice` persiste no banco (com a migração da OS-052) → `worker` repassa ao `synthesize_text` → `Speaker.synthesize(voice=...)`. O player ganhou um seletor de voz que reage ao idioma e fica desabilitado em Automático.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `686d358` com 14 falhas antes do `9a0977e`
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou (340 → 355)
- [x] Contratos de `ARQUITETURA.md` respeitados — `Speaker.synthesize` já aceitava `voice` desde a OS-004; nenhum contrato mudou
- [x] Nenhuma chamada a API paga nos testes — tudo mockado (mesmo padrão das OS anteriores)
- [x] Type hints e docstring de uma linha em toda função pública — `synthesize_text` e `_synthesize_with_retry` atualizados
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-053-report.md`
- [x] PR aberto — https://github.com/dinei84/listening/pull/50

Específico (seção 7 da OS):

- [x] `Book.voice` persiste e volta do banco — `test_book_voice_persists_and_loads`, `test_book_voice_defaults_to_none`
- [x] A coluna aparece num `books.db` sem ela, sem apagar o banco — `test_init_db_adds_voice_column_to_legacy_books_table` + validação em banco legado real (seção 4)
- [x] Livro sem voz escolhida narra com a voz padrão do idioma — `test_synthesize_text_without_voice_uses_language_default` (passa `voice=None`, Speaker usa `VOICE_BY_LANG_CODE`)
- [x] Livro com voz escolhida narra com ela — `test_synthesize_text_passes_voice_to_speaker`, `test_worker_passes_book_voice_to_pipeline`
- [x] Voz desconhecida vira `None`, sem erro — `test_post_books_ignores_unknown_voice`
- [x] Voz de outro idioma vira `None`, sem erro — `test_post_books_rejects_voice_from_another_language`
- [x] Idioma Automático força voz `None` — `test_post_books_forces_none_voice_when_language_is_auto`
- [x] O catálogo de cada idioma começa pela voz padrão atual — `test_voice_catalog_starts_with_current_default_for_every_language`, `test_voice_catalog_english_default_comes_before_alloy`
- [x] O player lista as três vozes em Português e troca a lista ao mudar o idioma — `test_player_has_voice_select` + verificação manual em navegador (seção 4)
- [x] O seletor de voz fica desabilitado com idioma Automático — verificado no navegador real e codificado em `populateVoiceSelect()`
- [x] A voz é repassada mesmo quando a trava de custo degrada — `test_voice_is_passed_even_when_degraded_to_fallback`
- [x] Nenhum teste existente quebra (340 hoje → 355)

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_book_voice_persists_and_loads` | `tests/unit/test_db.py` | Sim |
| `test_book_voice_defaults_to_none` | idem | Sim |
| `test_init_db_adds_voice_column_to_legacy_books_table` | idem | Sim |
| `test_synthesize_text_passes_voice_to_speaker` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_synthesize_text_without_voice_uses_language_default` | idem | Sim |
| `test_worker_passes_book_voice_to_pipeline` | `tests/unit/test_worker.py` | Sim |
| `test_post_books_accepts_voice` | `tests/integration/test_api_books.py` | Sim |
| `test_post_books_rejects_voice_from_another_language` | idem | Sim |
| `test_post_books_ignores_unknown_voice` | idem | Sim |
| `test_post_books_forces_none_voice_when_language_is_auto` | idem | Sim |
| `test_voice_catalog_starts_with_current_default_for_every_language` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_voice_catalog_lists_portuguese_three_voices` | idem | Sim |
| `test_voice_catalog_english_default_comes_before_alloy` | idem | Sim |
| `test_player_has_voice_select` | `tests/integration/test_player.py` | Sim |
| `test_voice_is_passed_even_when_degraded_to_fallback` | `tests/unit/test_cost_control.py` | Sim |

Commit "Red" antes do "Green"? [x] Sim — `686d358` (14 falhas) antes de `9a0977e`.

## 4. Saída de comandos relevantes

Suíte completa:

```
355 passed, 1 warning in 12.62s
```

(Aviso é o `StarletteDeprecationWarning` pré-existente.)

`ruff check` nos arquivos da OS: `All checks passed!` — `black` reformatou `tests/unit/test_worker.py`, demais já estavam OK.

Migração validada em banco legado real (formato da OS-052, sem `voice`): `init_db` adiciona a coluna, a linha antiga sobrevive com `voice = None` e `language = "pt"` intactos; novo livro com `voice="pm_santa"` persiste e relê. Saída:

```
livro: Livro Antigo | language: pt | voice: None
colunas: [... 'voice']
OK: banco legado migrado sem perder linha
OK: voice persistida e relida
```

Verificação manual em navegador real (API + `python -m worker.tasks`): com idioma **Português**, o seletor de voz lista `pf_dora` (selecionada por padrão), `pm_alex` e `pm_santa`; ao trocar para **Inglês**, a lista troca para as 20 vozes em inglês; ao voltar para **Automático**, o seletor desabilita. Envio de um PDF com `pm_alex` selecionado resultou em `Book.voice == "pm_alex"` no banco.

## 5. Desvios do escopo original

**Um, de validação, que a OS não detalhou:** a regra "voz que não pertence ao idioma escolhido → None" precisava de um mapeamento `language` (formulário) → `lang_code` (Kokoro) → lista de vozes. Usei `LANG_CODE_BY_LANGUAGE` (já existente) + `VOICES_BY_LANG_CODE` (novo catálogo da OS) — exatamente os dois mapas que a OS seção 5 define, sem criar validação nova.

**Nenhum arquivo além do escopo foi tocado.** Os arquivos alterados são exatamente os 8 listados na seção 3 da OS + os testes.

## 6. Dúvidas / bloqueios

**Nenhum bloqueio arquitetural.** Duas observações registradas:

**O catálogo do player espelha o do KokoroSpeaker em JS (duplicação).** O player é HTML/CSS/JS puro (decisão #12, sem build step), então não há como ele importar o catálogo Python; a duplicação segue o mesmo padrão do seletor de idioma (que também é um `<select>` estático). Se os catálogos divergirem no futuro, a API é quem manda: uma voz que o player ofereça mas o backend não reconheça para o idioma vira `None` silenciosamente (mesma regra de "voz desconhecida"). Não atende a "um único ponto de verdade", mas segue a arquitetura decidida para o frontend.

**O `POST /books` valida a voz contra `LANG_CODE_BY_LANGUAGE`.** O inglês britânico (`b`) tem catálogo no KokoroSpeaker, mas não existe opção no seletor de idioma do player (que usa os valores de `LANG_CODE_BY_LANGUAGE`); as vozes `bf_*`/`bm_*` não são alcançáveis pelo formulário. Consistente com a OS-025 (o seletor de idioma também não expõe o britânico), apenas registrado.

## 7. Link do PR

https://github.com/dinei84/listening/pull/50