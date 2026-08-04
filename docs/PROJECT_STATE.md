# PROJECT_STATE.md

Fonte única de verdade sobre o estado atual do projeto. Deve ser atualizado a cada OS concluída — quem faz a atualização é o próprio agente que finalizou a OS, como último passo antes de abrir o PR.

Se um agente novo entra no projeto, este é o primeiro arquivo que ele lê, antes de `ARQUITETURA.md` e `AGENTS.md`.

---

## 1. Visão em uma linha

App pessoal que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, otimizado para baixo custo.

## 2. Status atual

**Fase:** OS-011 concluída — contrato `JobQueue` (ABC com `enqueue`/`claim_next`/`mark_done`/`mark_failed`/`get_job`) e `SQLiteJobQueue`, com `claim_next()` atomicamente seguro (transação `BEGIN IMMEDIATE`, testado com reivindicação dupla). `plugins/registry.py` ganhou `QUEUES`, `core/config.py`/`config.yaml` ganharam `queue: sqlite`. Fila ainda não está ligada em `worker/tasks.py` nem em `POST /books` — isso é a próxima OS. 10 testes novos (64 no total do projeto).

**Última OS concluída:** OS-011 — contrato JobQueue + SQLiteJobQueue.

**OS em andamento:** nenhuma.

**Próxima OS a abrir:** ligar `JobQueue` em `worker/tasks.py` e na API (`POST /books` passa a enfileirar).

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
| `plugins/speakers/base.py` | concluído (testado) | OS-004 | Classe abstrata `Speaker` com `synthesize()` e `cost_per_char` |
| `plugins/speakers/kokoro_speaker.py` | concluído (testado) | OS-004 | `KokoroSpeaker` com mock de inferência nos testes |
| `processing/cleaner.py` | concluído (testado) | OS-008 | `clean_text(pages)` remove linhas repetidas em ≥2 páginas (header/footer) e corrige hifenização de quebra de linha; preserva parágrafos |
| `processing/chunker.py` | concluído (testado) | OS-008 | `chunk_text(text, max_chars=1000)` divide por sentença via `re`, nunca corta sentença ao meio (sentença isolada maior que `max_chars` vira chunk próprio) |
| `api/` (FastAPI) | concluído (testado) | OS-010 | `api/main.py` (app + lifespan que roda `db.init_db()`) e `api/routes_books.py` (`POST /books`, `GET /books/{id}/status`) — pipeline síncrono no request, falha vira `status="error"` sem 500 |
| `plugins/queues/base.py` | concluído (testado) | OS-011 | `JobQueue` (ABC) — `enqueue`, `claim_next`, `mark_done`, `mark_failed`, `get_job`, copiado verbatim de `ARQUITETURA.md` seção 4.3 |
| `plugins/queues/sqlite_queue.py` | concluído (testado) | OS-011 | `SQLiteJobQueue` — tabela `jobs` no mesmo arquivo de `storage/db.py` (`books.db`); `claim_next()` atômico via `BEGIN IMMEDIATE` + `UPDATE ... WHERE status='queued'` |
| `worker/` (fila) | não iniciado | OS-001 | Stub vazio — `JobQueue`/`SQLiteJobQueue` prontos (OS-011), mas ainda não consumidos; implementação real é a próxima OS |
| `storage/` | em andamento | OS-011 | `db.py` concluído (testado, OS-010) — `sqlite3` puro, tabela `books`; tabela `jobs` de `plugins/queues/sqlite_queue.py` vive no mesmo arquivo; `audio_store.py` continua stub vazio |
| `player/` (frontend) | não iniciado | OS-001 | Stub vazio — implementação real é OS-007+ |

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
12. Ligar `JobQueue` em `worker/tasks.py` e mudar `POST /books` para enfileirar em vez de processar inline
13. Player web básico

## 6. Riscos e bloqueios conhecidos

- Decisão #3 (fila de jobs) resolvida na decisão #11: `SQLiteJobQueue` como plugin, contrato pronto para trocar para Redis depois sem reescrever pipeline/API/worker.
- Confidence do PaddleOCR foi levantado por documentação oficial (`rec_score` / `rec_scores`) sem validação empírica local no spike — validar quando `PaddleOCR` ganhar OS própria.
- Threshold `0.85` (decisão #9) é uma margem de segurança, não um ponto fino validado empiricamente — as fixtures do spike não cobriram degradação intermediária. Se `TesseractOCR` em produção mostrar falsos positivos/negativos de fallback, revisitar com mais dados.

## 7. Como este arquivo deve ser mantido

- Atualizar a seção 2 (status atual) e 4 (componentes) a cada OS concluída.
- Mover item do backlog (seção 5) para "implementado" só depois que o DoD da OS foi cumprido, não quando o código foi só escrito.
- Nunca editar o log de decisões (seção 3) retroativamente — só adicionar.
