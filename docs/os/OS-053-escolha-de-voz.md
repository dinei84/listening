# OS-053 — Escolha de voz pelo usuário

## 1. Objetivo

Deixar o usuário escolher a voz do livro no envio, em vez de receber sempre a única voz fixa por idioma.

## 2. Contexto e decisões já tomadas

O dono ouviu as três vozes disponíveis em português e decidiu expô-las como opção de produto. Duas decisões foram tomadas **antes** desta OS e não estão em aberto:

- **Sem mistura de vozes.** O blend funciona (o `KPipeline` aceita tensor combinado, confirmado por teste na OS-041B) e três proporções foram avaliadas, mas foram descartadas: voz de catálogo é mais previsível e explicável para o usuário final.
- **O seletor mostra só as vozes do idioma escolhido.** Evita o caso absurdo de voz portuguesa lendo texto em inglês.

O pré-requisito de schema foi pago pela OS-052: `ensure_column` já existe, então `voice` entra como **coluna normal** em `books`, igual ao `language` da OS-025, sem exigir apagar o `books.db`.

## 3. Escopo

Alterados:

- `core/models.py` — `Book.voice`.
- `storage/db.py` — coluna, migração e persistência.
- `plugins/speakers/kokoro_speaker.py` — catálogo de vozes selecionáveis por idioma.
- `core/pipeline.py` — repassar a voz ao `Speaker`.
- `worker/tasks.py` — repassar `book.voice`.
- `api/routes_books.py` — aceitar e validar o campo.
- `player/index.html` e `player/app.js` — seletor que reage ao idioma.
- Testes correspondentes.

Fora de escopo:

- **Mistura de vozes.** Decisão do dono (seção 2).
- **Trocar a voz de um livro já processado.** Exigiria re-sintetizar o áudio inteiro e invalidar os `AudioChunk` persistidos, mexendo na retomada da OS-022. A voz é escolhida no envio.
- **Voz por capítulo.** Não há caso de uso.
- **Vozes de outro Speaker.** Só o `KokoroSpeaker` está registrado (ver item 52 do backlog); o catálogo é dele.

## 4. Contratos envolvidos

`Speaker.synthesize(text, voice=None, lang_code=None)` **já aceita `voice`** desde a OS-004 — o parâmetro existe e nunca foi usado. Esta OS liga o fio que faltava; **nenhum contrato muda.**

O que falta é o caminho: `worker` → `pipeline.synthesize_text` → `_synthesize_with_retry` → `speaker.synthesize`. Hoje o `voice` se perde no meio e o `KokoroSpeaker` sempre cai no `VOICE_BY_LANG_CODE`.

## 5. Catálogo real, levantado do repositório do modelo

Vozes por `lang_code` em `hexgrad/Kokoro-82M` (levantado 12/08/2026):

| Idioma | code | Vozes |
|---|---|---|
| português | `p` | **pf_dora**, pm_alex, pm_santa |
| inglês americano | `a` | **af_heart** + 19 outras |
| inglês britânico | `b` | **bf_alice** + 7 outras |
| espanhol | `e` | **ef_dora**, em_alex, em_santa |
| francês | `f` | **ff_siwis** |
| hindi | `h` | **hf_alpha**, hf_beta, hm_omega, hm_psi |
| italiano | `i` | **if_sara**, im_nicola |
| japonês | `j` | **jf_alpha** + 4 outras |
| chinês | `z` | **zf_xiaoxiao** + 7 outras |

Em negrito, a voz que o `VOICE_BY_LANG_CODE` já usa hoje.

**Regra de ordenação que é contrato desta OS:** a lista de cada idioma começa pela voz atual. Ela vira o padrão de quem não escolhe, e o comportamento de todo livro já existente fica idêntico. Ordenar alfabeticamente **quebraria** isso — em inglês, `af_alloy` viria antes de `af_heart`.

## 6. Regras de validação

Espelham o `language` da OS-025, que trata valor inválido como ausente em vez de erro:

- `voice` ausente ou desconhecida → `None`, e o Speaker usa o padrão do idioma. Nunca 4xx.
- `voice` que **não pertence ao idioma escolhido** → `None`. Uma voz portuguesa num livro marcado como inglês é escolha inconsistente, não intenção.
- `language` ausente (**Automático**) → `voice` é forçada a `None`. O idioma só é conhecido depois da detecção, então não há como validar a voz contra ele; oferecer escolha aqui produziria voz de um idioma lendo texto de outro. **No player, o seletor de voz fica desabilitado enquanto o idioma for Automático.**

## 7. Critérios de aceite

- [ ] `Book.voice` persiste e volta do banco
- [ ] A coluna aparece num `books.db` sem ela, sem apagar o banco (via `ensure_column` da OS-052)
- [ ] Livro sem voz escolhida narra com a voz padrão do idioma — comportamento de hoje inalterado
- [ ] Livro com voz escolhida narra com ela: a voz chega ao `speaker.synthesize`
- [ ] Voz desconhecida vira `None`, sem erro
- [ ] Voz de outro idioma vira `None`, sem erro
- [ ] Idioma Automático força voz `None`
- [ ] O catálogo de cada idioma começa pela voz padrão atual
- [ ] O player lista as três vozes em Português e troca a lista ao mudar o idioma
- [ ] O seletor de voz fica desabilitado com idioma Automático
- [ ] A voz é repassada mesmo quando a trava de custo degrada para o `fallback_speaker` (OS-042)
- [ ] Nenhum teste existente quebra (340 hoje)

## 8. Testes exigidos (mínimo)

- `test_book_voice_persists_and_loads`
- `test_init_db_adds_voice_column_to_legacy_books_table`
- `test_synthesize_text_passes_voice_to_speaker`
- `test_synthesize_text_without_voice_uses_language_default`
- `test_worker_passes_book_voice_to_pipeline`
- `test_post_books_accepts_voice`
- `test_post_books_rejects_voice_from_another_language`
- `test_post_books_ignores_unknown_voice`
- `test_post_books_forces_none_voice_when_language_is_auto`
- `test_voice_catalog_starts_with_current_default_for_every_language`
- `test_player_has_voice_select`

## 9. Relatório

Ver `docs/report/OS-053-report.md`.
