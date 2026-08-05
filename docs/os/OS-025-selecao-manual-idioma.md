# OS-025 — Seleção manual de idioma

## 1. Objetivo

A OS-020 deu detecção automática de idioma ao `KokoroSpeaker`, mas sem nenhuma forma de o usuário forçar um idioma manualmente — se a detecção errar (texto curto, mistura de idiomas, PDF com muitas palavras estrangeiras), não há como corrigir sem editar código. Esta OS adiciona uma seleção manual **opcional** no upload, que ganha prioridade sobre a detecção automática; sem escolha, o comportamento de hoje (auto-detecção por chunk, OS-020) continua idêntico.

## 2. Escopo

**Dentro do escopo:**
- `plugins/speakers/base.py` (`Speaker`, ABC): `synthesize()` ganha parâmetro novo opcional `lang_code: str | None = None` — extensão aditiva do contrato (`ARQUITETURA.md` seção 4.2), mesmo padrão de parâmetro opcional já usado nas OS-021/022 em `core/pipeline.py`. Sem `lang_code`, o comportamento de cada Speaker existente (hoje só `KokoroSpeaker`) fica inalterado.
- `plugins/speakers/kokoro_speaker.py`: `synthesize(text, voice=None, lang_code=None)` — se `lang_code` vier preenchido, pula `_detect_lang_code()` e usa esse valor direto (ainda passando por `_get_pipeline()`, reaproveitando o fallback já existente pra idioma indisponível no ambiente, ex: japonês/mandarim — risco já registrado em `PROJECT_STATE.md` seção 6). O `lang_code` aqui é o código do Kokoro (`a`, `p`, `e`...), não o código do `langdetect` (`en`, `pt`...) — reaproveitar `LANG_CODE_BY_LANGUAGE` como tabela de tradução entre o que a API/UI expõe (`en`, `pt`, `es`...) e o que o Kokoro entende.
- `core/models.py`: `Book` ganha `language: str | None = None` (código tipo `langdetect`: `en`, `pt`, `es`... — `None` = automático).
- `storage/db.py`: coluna `language TEXT` em `books` (mesma nota de risco de schema sem migração da OS-024 — avisar no `RUNBOOK.md`).
- `api/routes_books.py::create_book`: aceita campo de formulário opcional `language`. Validar contra as chaves de `LANG_CODE_BY_LANGUAGE`, ou deixar passar livre e cair no fallback pra inglês do `KokoroSpeaker` se inválido — decisão de implementação, documentar a escolhida no relatório.
- `core/pipeline.py::synthesize_text()`: ganha parâmetro opcional `lang_code: str | None = None`, repassado a cada chamada de `speaker.synthesize()`.
- `worker/tasks.py::process_job()`: repassa `book.language` (convertido pro lang_code do Kokoro) pra `synthesize_text()`.
- `player/index.html`/`app.js`: `<select>` no formulário de upload com "Automático" (padrão) + os idiomas de `LANG_CODE_BY_LANGUAGE` (en/es/fr/hi/it/pt/ja/zh) — nota: japonês/mandarim aparecem na lista mas degradam pro inglês neste ambiente (achado já conhecido da OS-020); não esconder da UI, é uma limitação de ambiente, não da feature em si.

**Fora do escopo:**
- Seleção de idioma por capítulo/trecho — é por livro inteiro, escolhida no upload.
- Mudar o idioma de um livro já processado — precisa reenviar o PDF.
- Resolver a limitação de japonês/mandarim neste ambiente (instalar `misaki[ja]`/`misaki[zh]`) — fora de escopo, risco aberto já registrado.

## 3. Contratos envolvidos

`Speaker.synthesize()` (`ARQUITETURA.md` seção 4.2) ganha `lang_code: str | None = None` — extensão aditiva, proposta aqui, mesmo padrão já aprovado nas OS-021/022 (parâmetro opcional, default preserva o comportamento atual). Atualizar a seção 4.2 com a assinatura nova. `Book` (seção 5) ganha `language: str | None = None`.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Upload sem escolher idioma continua com detecção automática por chunk, comportamento idêntico ao de hoje (regressão da OS-020 não quebra)
- [ ] Upload com idioma escolhido força esse `lang_code` em todos os chunks do livro, sem chamar `_detect_lang_code()`
- [ ] Idioma inválido/desconhecido enviado no upload não derruba o livro (cai num comportamento padrão — documentar qual foi escolhido)
- [ ] `Speaker.synthesize()` chamado sem `lang_code` continua se comportando exatamente como antes (testes das OS-004/019/020 não quebram)
- [ ] UI mostra a lista de idiomas suportados, com "Automático" pré-selecionado como padrão

## 5. Testes exigidos (mínimo)

- `test_kokoro_speaker_synthesize_uses_forced_lang_code_when_given`
- `test_kokoro_speaker_synthesize_falls_back_to_detection_when_lang_code_is_none` (regressão)
- `test_synthesize_text_passes_lang_code_to_speaker`
- `test_create_book_persists_chosen_language`
- `test_worker_process_job_passes_book_language_to_pipeline`

Local sugerido: `tests/unit/speakers/test_kokoro_speaker.py`, `tests/integration/test_pipeline_end_to_end.py`, `tests/integration/test_api_books.py`, `tests/unit/test_worker.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-025-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
