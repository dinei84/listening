# PROJECT_STATE.md

Fonte única de verdade sobre o estado atual do projeto. Deve ser atualizado a cada OS concluída — quem faz a atualização é o próprio agente que finalizou a OS, como último passo antes de abrir o PR.

Se um agente novo entra no projeto, este é o primeiro arquivo que ele lê, antes de `ARQUITETURA.md` e `AGENTS.md`.

---

## 1. Visão em uma linha

App pessoal que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, otimizado para baixo custo.

## 2. Status atual

**Fase:** OS-017 concluída — `plugins/extractors/easyocr_extractor.py` implementa `EasyOCRExtractor` (terceiro elo da cadeia de OCR, decisão #13), registrado em `plugins/registry.py` (`EXTRACTORS["easyocr"]`) e `easyocr==1.7.2` em `requirements.txt`. **Achado importante da validação empírica exigida pela OS (rodando o EasyOCR de verdade, não mockado):** no fixture "legível" (`clear_text_pdf.pdf`), a confiança real observada foi `0.7644` — **abaixo** do threshold `0.85` reaproveitado por analogia na decisão #13. Ou seja, aplicando a heurística de fallback (decisão #9) literalmente, esse texto legível cairia para o próximo elo da cadeia (`CloudOCRFallback`) mesmo tendo sido lido corretamente. Ver seção 6 para detalhes e a recomendação registrada (não é uma decisão de arquitetura tomada por este agente).

**Última OS concluída:** OS-017 — `EasyOCRExtractor`.

**OS em andamento:** OS-018 — corrige bug real encontrado em uso (`Phoneme string too long: 863 > 510` ao processar um livro técnico longo), ver `docs/os/OS-018-kokoro-limite-fonemas.md`.

**Próxima OS a abrir após OS-018:** a definir — candidatos: (a) revisitar o threshold `0.85` para `EasyOCRExtractor` à luz do achado empírico da OS-017, antes de (b) ligar `EasyOCRExtractor` na cadeia de fallback de `core/pipeline.py`.

## 3. Decisões já tomadas (Architecture Decision Log)

Registrar aqui toda decisão relevante, na ordem em que foram tomadas. Nunca apagar uma entrada — se uma decisão for revertida, adicionar uma nova entrada explicando o motivo, mantendo o histórico.

| # | Data | Decisão | Motivo |
|---|------|---------|--------|
| 1 | definir na 1ª OS | Arquitetura plugável para Extractor e Speaker via interface + registry | Permite trocar OCR/TTS sem reescrever pipeline; ver `ARQUITETURA.md` seção 1 |
| 2 | definir na 1ª OS | TTS local (Kokoro) como padrão, cloud como opção sob demanda | Controle de custo — ver brainstorm original |
| 3 | em aberto | Fila de jobs: Celery+Redis vs solução mais simples (SQLite como fila) | Pendente — depende do volume de uso real (projeto pessoal, não precisa de infra pesada) |
| 4 | em aberto | Banco de dados: SQLite (MVP) com migração futura para Postgres | Pendente confirmação |
| 5 | em aberto | Heurística de fallback de OCR (quando cair de Tesseract → PaddleOCR → cloud) | Precisa de uma OS dedicada de spike/pesquisa |
| 6 | 2026-08-03 | Atualizações de governança (`AGENTS.md`, `README.md`, `TEMPLATE.md` etc.) feitas aqui no repositório de arquitetura precisam ser baixadas e commitadas manualmente no repositório de código — não há sincronização automática | Descoberto durante a OS-001: mudanças ficaram como "não commitadas" no repo de código e quase foram atribuídas erroneamente a um agente de execução. Toda vez que a documentação de governança for atualizada aqui, o próximo agente deve confirmar via `git diff` contra o último commit se os docs já estão sincronizados antes de assumir que uma mudança veio de execução indevida |
| 7 | 2026-08-03 | Estrutura de documentação do repositório de código usa `docs/os/` e `docs/report/` em minúsculo (não `docs/OS/`/`docs/REPORT/`) | Encontrada divergência de caixa entre o que a governança definia e o que existia no repo de código; corrigido por renomeação para bater com a convenção documentada em `README.md` |
| 8 | 2026-08-03 | Proposta (OS-005): considerar OCR "confiança baixa" quando `avg_confidence_words_normalized < 0.85` **ou** `words_counted == 0`; nesses casos, cair para o próximo extractor da cadeia (`TesseractOCR` → `PaddleOCR` → `CloudOCRFallback`) | Spike empírico com Tesseract 5.3.4 em 4 fixtures mostrou cenários de alta confiança (~0.90-0.96) e falha total (`words_counted == 0`, confiança 0.0) em imagem muito degradada. PaddleOCR confidence pesquisado em documentação oficial (`rec_score` / `rec_scores`) mas **não validado empiricamente** neste ambiente |
| 9 | 2026-08-03 | **Decisão #8 aprovada pelo dono do projeto, sem alterações.** A heurística `avg_confidence_words_normalized < 0.85` ou `words_counted == 0` é agora oficial e foi incorporada em `ARQUITETURA.md` seção 4.1. Isso resolve a decisão #5 | Aprovação explícita em conversa, após revisão que confirmou a reprodutibilidade dos números do spike. Ressalva conhecida (não invalida a aprovação): as fixtures usadas cobriram bem sucesso (~0.90-0.96) e falha total (0.0), mas não um caso de degradação intermediária — `0.85` é uma margem de segurança, não um ponto fino validado empiricamente |
| 10 | 2026-08-03 | **Decisão #4 confirmada: SQLite para a API mínima (OS-010), processamento síncrono no request (sem fila).** A decisão #3 (Celery/Redis vs. algo mais simples) continua em aberto — só passa a importar quando a API precisar mesmo ser assíncrona | Confirmado pelo dono do projeto. Segue o roadmap de `ARQUITETURA.md` seção 8, que já colocava a API (passo 2) antes da fila assíncrona (passo 4). Evita resolver a decisão #3 antes da hora, mantendo a filosofia de baixa infraestrutura do `HANDOFF.md` |
| 11 | 2026-08-03 | **Decisão #3 resolvida: fila de jobs em SQLite (`SQLiteJobQueue`), tratada como plugin.** Contrato `JobQueue` novo, proposto e aprovado pelo dono do projeto, incorporado em `ARQUITETURA.md` seção 4.3. Celery+Redis fica descartado por agora, mas a interface já existe para que uma futura `RedisJobQueue` seja só uma nova classe + entrada no registry, sem reescrever `core/pipeline.py`/`api/`/`worker/tasks.py` | Segue a mesma regra de ouro de plugin já usada para Extractor/Speaker (`ARQUITETURA.md` seção 1: "pode ser substituído por algo melhor no futuro, é plugin"). Dono do projeto pediu explicitamente para não fechar a porta pra Redis mais tarde, sem adicionar a complexidade dele agora |
| 12 | 2026-08-04 | **Player web em HTML/CSS/JS puro, sem build step (sem React).** `ARQUITETURA.md` seção 3 tinha "React" só como comentário informal na árvore de pastas original — nunca foi decisão formal. Atualizado para refletir a escolha real | Confirmado pelo dono do projeto. Mesma filosofia de baixa infraestrutura já aplicada o projeto inteiro (sem ORM, sem Celery, stdlib sempre que dá) — React exigiria npm/node_modules/bundler, uma segunda toolchain só pro player "básico" |
| 13 | 2026-08-04 | **Terceiro extractor da cadeia de OCR é `EasyOCRExtractor` (torch), não `PaddleOCR` como no roadmap original.** `paddlepaddle` sozinho baixa ~195MB (framework de deep learning novo); `torch` já está instalado via Kokoro, e `EasyOCR` o usa em vez de trazer um segundo framework do zero. `ARQUITETURA.md` seções 3, 4.1, 4.4 e 8 atualizadas (`paddle_ocr.py`→`easyocr_extractor.py`, `"paddleocr"`→`"easyocr"` no registry). Fórmula de confidence: mesma faixa 0.0–1.0 do PaddleOCR original, então reaproveita o threshold `0.85` (decisão #9) por analogia ao Tesseract — **não é uma nova validação empírica**, é uma decisão de engenharia justificada pela semelhança de formato do confidence, a confirmar/ajustar quando `EasyOCRExtractor` tiver uso real | Confirmado pelo dono do projeto. Mesma filosofia de baixa infraestrutura (decisão #12, `HANDOFF.md` seção 2) — evitar uma segunda dependência pesada de deep learning quando a primeira (torch, via Kokoro) já cobre a mesma necessidade |

> Toda OS que tomar uma decisão de arquitetura nova ou alterar uma decisão existente deve atualizar esta tabela.

## 4. Componentes e status individual

| Componente | Status | Última OS | Observações |
|---|---|---|---|
| `core/models.py` | concluído (testado) | OS-002 | 5 modelos Pydantic implementados com validações de status |
| `core/pipeline.py` | concluído (testado) | OS-009 | `extract_with_fallback()`, `extract_clean_text()` (extração + `clean_text()`) e `synthesize_text(text, chapter_id, max_chars=None)` — chama o Speaker uma vez por chunk (`chunk_text()`), `sequence` incremental, `chapter_id` em todos, texto vazio não chama o Speaker |
| `core/config.py` | concluído (testado) | OS-011 | `load_config()` lê `config.yaml` e retorna `Config(extractor, speaker, queue)` |
| `plugins/registry.py` | concluído (testado) | OS-011 | `EXTRACTORS = {"pymupdf", "tesseract"}`, `SPEAKERS = {"kokoro"}`, `QUEUES = {"sqlite": SQLiteJobQueue}`, conforme `ARQUITETURA.md` seção 4.4 |
| `plugins/extractors/base.py` | concluído (testado) | OS-003 | Classe abstrata `Extractor` com `supports()` e `extract()` |
| `plugins/extractors/pymupdf_extractor.py` | concluído (testado) | OS-003 | `PyMuPDFExtractor` com suporte a PDF nativo e image-only |
| `plugins/extractors/tesseract_ocr.py` | concluído (testado) | OS-006 | `TesseractOCR` com fórmula de confidence aprovada (decisão #9) |
| `plugins/extractors/easyocr_extractor.py` | concluído (testado) | OS-017 | `EasyOCRExtractor` — terceiro elo da cadeia de OCR (decisão #13). `_get_reader()` lazy (mesmo padrão de `KokoroSpeaker._get_pipeline`), mockado por completo nos testes automatizados. Validação empírica real (fora dos testes) encontrou confiança `0.7644` para texto legível — abaixo do threshold `0.85` reaproveitado da decisão #9/#13; ver seção 6 e `docs/report/OS-017-report.md` |
| `plugins/speakers/base.py` | concluído (testado) | OS-004 | Classe abstrata `Speaker` com `synthesize()` e `cost_per_char` |
| `plugins/speakers/kokoro_speaker.py` | concluído (testado) | OS-004 | `KokoroSpeaker` com mock de inferência nos testes |
| `processing/cleaner.py` | concluído (testado) | OS-008 | `clean_text(pages)` remove linhas repetidas em ≥2 páginas (header/footer) e corrige hifenização de quebra de linha; preserva parágrafos |
| `processing/chunker.py` | concluído (testado) | OS-008 | `chunk_text(text, max_chars=1000)` divide por sentença via `re`, nunca corta sentença ao meio (sentença isolada maior que `max_chars` vira chunk próprio) |
| `api/` (FastAPI) | concluído (testado) | OS-015 | `api/main.py` (app + lifespan que roda `db.init_db()` e `audio_store.init_db()`), `api/routes_books.py` (`POST /books`, `GET /books` — listagem, OS-015 — `GET /books/{id}/status`) e `api/routes_audio.py` (`GET /books/{id}/audio`, `GET /books/{id}/audio/{sequence}`) |
| `plugins/queues/base.py` | concluído (testado) | OS-011 | `JobQueue` (ABC) — `enqueue`, `claim_next`, `mark_done`, `mark_failed`, `get_job`, copiado verbatim de `ARQUITETURA.md` seção 4.3 |
| `plugins/queues/sqlite_queue.py` | concluído (testado) | OS-011 | `SQLiteJobQueue` — tabela `jobs` no mesmo arquivo de `storage/db.py` (`books.db`); `claim_next()` atômico via `BEGIN IMMEDIATE` + `UPDATE ... WHERE status='queued'` |
| `worker/tasks.py` | concluído (testado) | OS-013 | `process_job(job)` roda o pipeline, persiste os `AudioChunk` via `storage.audio_store.persist_chunks()` e marca `Book`/`Job` como `ready`/`done` ou `error`/`failed`; `run_worker(poll_interval, max_iterations)` faz polling; `python -m worker.tasks` para rodar manualmente |
| `storage/` | concluído (testado) | OS-015 | `db.py` (OS-010, `list_books()` adicionado na OS-015), `uploads.py` (OS-012) e `audio_store.py` (OS-013 — `persist_chunks`/`list_chunks`/`get_chunk`, tabela `audio_chunks` no mesmo `books.db`, arquivos em `storage/audio/{book_id}/{sequence}.wav`) concluídos e testados; tabela `jobs` de `plugins/queues/sqlite_queue.py` também no mesmo arquivo |
| `player/` (frontend) | concluído (testado) | OS-016 | HTML/CSS/JS puro (decisão #12): upload, polling, playback sequencial, play/pause, velocidade, resume via `localStorage` (OS-014) + seção "Meus livros" consumindo `GET /books`, clique abre via `openBook()`, botão "Atualizar lista", auto-atualiza após upload (OS-016). Servido por `api/main.py` (`StaticFiles` em `/`). `test_player_static_files_are_served` passa; verificação manual em navegador real de ambas as OS's feita na revisão (`docs/report/OS-014-report.md` seção 6.1, `docs/report/OS-016-report.md` seção 6.1) |

Valores possíveis de status: `não iniciado` · `em andamento` · `implementado sem testes` · `concluído (testado)` · `bloqueado`.

## 5. Backlog priorizado (próximas OS candidatas)

1. **OS-001 — Bootstrap do repositório e instalação de dependências** — status: concluída
2. **OS-002 — `core/models.py`** — modelos de dados base — status: concluída
3. **OS-003 — `plugins/extractors/base.py` + `PyMuPDFExtractor`** — status: concluída
4. **OS-004 — `plugins/speakers/base.py` + `KokoroSpeaker`** — status: concluída
5. **OS-005 — Spike: heurística de confiança de OCR** (decisão #5) — status: concluída, heurística aprovada (decisão #9)
6. **OS-006 — `plugins/extractors/tesseract_ocr.py`** — `TesseractOCR` usando a heurística aprovada — status: concluída
7. **OS-007 — `core/pipeline.py`** — orquestração síncrona mínima ligando extractor → speaker (+ preenche `plugins/registry.py` e `core/config.py`) — status: concluída
8. **OS-008 — `processing/cleaner.py` + `processing/chunker.py`** — status: concluída
9. **OS-009 — Ligar cleaner/chunker em `core/pipeline.py`** — substitui a síntese de texto inteiro numa chamada só — status: concluída
10. **OS-010 — API mínima** (`POST /books`, `GET /books/{id}/status`, síncrona, SQLite) — status: concluída
11. **OS-011 — Contrato `JobQueue` + `SQLiteJobQueue`** — status: concluída
12. **OS-012 — Liga `JobQueue` em `worker/tasks.py` e na API** — `POST /books` passa a enfileirar em vez de processar inline — status: concluída
13. **OS-013 — `storage/audio_store.py` + servir áudio pela API** — status: concluída
14. **OS-014 — Player web básico** (play/pause, velocidade, retomar posição — HTML/CSS/JS puro) — status: concluída, verificação manual em navegador feita na revisão (ver `docs/os/OS-014-player-web-basico.md` e `docs/report/OS-014-report.md` seção 6.1)
15. **OS-015 — `GET /books` (listagem)** — status: concluída
16. **OS-016 — Liga a listagem de livros na UI do player** — status: concluída, verificação manual em navegador feita na revisão (ver `docs/os/OS-016-listagem-no-player.md` e `docs/report/OS-016-report.md` seção 6.1)
17. **OS-017 — `plugins/extractors/easyocr_extractor.py`** (terceiro elo da cadeia de OCR, decisão #13) — status: concluída, com achado empírico sobre o threshold `0.85` (ver seção 6 e `docs/report/OS-017-report.md`)
18. **OS-018 — Corrige falha de síntese em texto denso** ("Phoneme string too long") — bug real encontrado em uso, ver `docs/os/OS-018-kokoro-limite-fonemas.md` — status: aberta, aguardando execução
19. Revisitar o threshold de confiança `0.85` especificamente para `EasyOCRExtractor`, à luz do achado da OS-017 — recomendado antes do item 20
20. Ligar `EasyOCRExtractor` na cadeia de fallback de `core/pipeline.py`

## 6. Riscos e bloqueios conhecidos

- **Em aberto (bug real, achado em uso pelo dono do projeto):** enviar "Security Engineering" (Ross Anderson, livro técnico longo) resultou em `Book.status == "error"`. Causa raiz encontrada consultando `jobs.error_message` direto no SQLite (não havia jeito de ver isso pela API nem pelo log do worker — `worker/tasks.py` não loga a exceção em lugar nenhum, só guarda no banco): `Phoneme string too long: 863 > 510`. `processing/chunker.py` divide por caracteres (`DEFAULT_MAX_CHARS = 1000`) sem saber quantos fonemas isso vira no Kokoro; texto denso/técnico gera mais fonemas por caractere, um chunk dentro do limite de caracteres pode estourar o limite de 510 fonemas do Kokoro, e como a síntese é sequencial sem tolerância a falha parcial, um chunk problemático derruba o livro inteiro. Corrigido pela OS-018 (`docs/os/OS-018-kokoro-limite-fonemas.md`): resiliência no `KokoroSpeaker` (divide e tenta de novo) + recalibração empírica de `DEFAULT_MAX_CHARS` + `error_message` exposto em `GET /books/{id}/status`.
- **Resolvido:** a verificação manual em navegador exigida pelos DoDs da OS-014 e da OS-016 foi concluída em ambos os casos na revisão pós-entrega, com acesso a navegador real. Único item não exercitado fim a fim nas duas: o clique no seletor nativo de arquivo do SO (barreira de segurança do próprio browser, não do player) — o endpoint que ele chama foi validado via `curl`/`DataTransfer`+`requestSubmit()` e o código revisado. Detalhes em `docs/report/OS-014-report.md` seção 6.1 e `docs/report/OS-016-report.md` seção 6.1.
- Nova ferramenta de dev: `.claude/launch.json` configurado para subir a API (`uvicorn api.main:app`) via preview do navegador em sessões futuras. Lembrar de também rodar `python -m worker.tasks` numa janela separada para o processamento acontecer de verdade.
- Decisão #3 (fila de jobs) resolvida na decisão #11: `SQLiteJobQueue` como plugin, contrato pronto para trocar para Redis depois sem reescrever pipeline/API/worker.
- Achado na revisão pré-OS-013 (`worker/tasks.py` descartava o retorno de `synthesize_text()`, nenhum `AudioChunk` persistido) — corrigido pela OS-013: `worker/tasks.py` agora chama `storage.audio_store.persist_chunks()` antes de marcar o `Book` como `ready`.
- Decisão #13: o terceiro extractor da cadeia de OCR passa a ser `EasyOCRExtractor` (reaproveita o `torch` já instalado via Kokoro), não `PaddleOCR` (~195MB de `paddlepaddle`, framework novo). A fórmula de confidence reaproveita o threshold `0.85` por analogia ao Tesseract.
- **Em aberto (achado da OS-017):** validação empírica real do `EasyOCRExtractor` (2 fixtures, `docs/report/OS-017-report.md`) mostrou confiança `0.7644` para o fixture "legível" (`clear_text_pdf.pdf`) — **abaixo** do threshold `0.85` reaproveitado da decisão #9. O texto foi lido corretamente (`"THE QUICK BROWN FOX JUMPS OVER 13 LAZY De"`), mas uma região específica ("De", provavelmente leitura parcial de uma palavra final) teve confiança `0.49`, puxando a média das 3 regiões para baixo. Aplicado literalmente, o threshold atual faria esse texto legível cair desnecessariamente para `CloudOCRFallback`. Fixture "ilegível" (`unreadable_text_pdf.pdf`) teve confiança real `~0.0000152` (não exatamente `0.0`, mas na prática equivalente — ainda bem abaixo do threshold). Este agente não decidiu um novo threshold (não é decisão de arquitetura de agente de execução, ver `AGENTS.md` seção 1) — recomendação registrada no relatório para o dono do projeto avaliar antes de ligar `EasyOCRExtractor` em `core/pipeline.py`.
- Threshold `0.85` (decisão #9) é uma margem de segurança, não um ponto fino validado empiricamente — as fixtures do spike não cobriram degradação intermediária. Se `TesseractOCR` em produção mostrar falsos positivos/negativos de fallback, revisitar com mais dados.

## 7. Como este arquivo deve ser mantido

- Atualizar a seção 2 (status atual) e 4 (componentes) a cada OS concluída.
- Mover item do backlog (seção 5) para "implementado" só depois que o DoD da OS foi cumprido, não quando o código foi só escrito.
- Nunca editar o log de decisões (seção 3) retroativamente — só adicionar.
