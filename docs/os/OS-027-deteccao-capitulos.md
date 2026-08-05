# OS-027 — Detecção de capítulos via TOC do PDF (com fallback sintético)

## 1. Objetivo

Hoje um livro inteiro vira um único `Chapter` (`Chapter(id=job.id, title=book.title, order=0, text=text)`, `worker/tasks.py`), sem nenhuma noção de capítulo real — `Book.chapters` existe no modelo mas nunca é persistido, e todo `AudioChunk` de um livro carrega o mesmo `chapter_id` fixo. O Visualizador (seletor de capítulos, item 30 do backlog em `PROJECT_STATE.md`) depende de capítulos de verdade existirem nos dados. Esta OS detecta a estrutura de capítulos do PDF — via TOC/bookmarks quando existir, com fallback sintético (agrupamento por página) quando não — e propaga isso até o `AudioChunk.chapter_id`.

**Aviso de tamanho, não é escopo inchado:** esta OS mexe na espinha dorsal do pipeline (como o texto é dividido antes de virar chunks), então toca mais arquivos centrais do que o normal (`core/pipeline.py`, `processing/cleaner.py` — só na forma de uso, não no contrato —, `worker/tasks.py`, `core/models.py`, `storage/db.py`, `api/routes_books.py`). Isso é esperado e faz parte do escopo declarado, não é motivo pra parar e reportar pela regra dos "~3 arquivos" do `AGENTS.md` seção 3.

## 2. Escopo

**Dentro do escopo:**

- **Detecção de capítulos** (função nova, sugestão `core/pipeline.py::detect_chapters(pdf_path: str) -> list[Chapter]`):
  - Usa `fitz.open(pdf_path).get_toc()` (PyMuPDF) — devolve `[nível, título, página]`. Considerar só o nível 1 (capítulos de topo) neste MVP; ignorar sub-seções — documentar essa escolha.
  - `get_toc()` é uma propriedade do **PDF em si** (bookmarks), não do extractor de texto configurado — funciona independente de o texto ser extraído por `PyMuPDFExtractor`, `TesseractOCR` ou `EasyOCRExtractor`.
  - Se `get_toc()` devolver lista vazia (comum em PDFs escaneados sem bookmarks), cair num fallback sintético: agrupar as páginas em blocos de tamanho fixo (decisão de implementação — ex: N páginas por bloco), com título genérico (`"Parte 1"`, `"Parte 2"`...). Documentar o critério escolhido e o porquê.
  - Cada `Chapter` detectado precisa saber seu intervalo de páginas (ver mudança de contrato, seção 3).

- **Extração e limpeza por capítulo, não mais do livro inteiro de uma vez:**
  - `clean_text()` (`processing/cleaner.py`) **não muda de contrato** — continua `pages: list[str] -> str`. O que muda é *como* é chamada: hoje roda uma vez para o livro inteiro (`extract_clean_text()`); esta OS passa a rodar **uma vez por capítulo**, usando só as `ExtractedPage`s daquele capítulo (fatiadas pelo intervalo de páginas detectado). Isso preserva a detecção de header/footer repetido (ela precisa de ≥2 páginas do mesmo conjunto pra funcionar — um capítulo de 1 página só não detecta repetição, aceitável).
  - `worker/tasks.py::process_job()` passa a: extrair todas as páginas uma vez (`extract_with_fallback`), detectar capítulos, e para cada capítulo (em ordem): fatiar as páginas daquele intervalo, limpar (`clean_text`), chunkar (`chunk_text`) e sintetizar — em vez do fluxo atual de "limpa tudo, chunka tudo, sintetiza tudo".

- **`AudioChunk.sequence` continua global e contínuo entre capítulos — não reseta por capítulo.** Isso é uma restrição técnica, não uma preferência: a chave primária de `audio_chunks` é `(book_id, sequence)` (OS-013), a checagem de consistência da retomada (OS-022, `_resume_inconsistency`) e o `chunks_total` da barra de progresso (OS-024, `count_text_chunks()`) assumem uma numeração única por livro inteiro. Ex: capítulo 1 pode gerar chunks `0..49`, capítulo 2 continua em `50..120`, etc. — só o `chapter_id` diferencia a que capítulo cada um pertence.
  - **Consequência a resolver:** `pipeline.count_text_chunks()` e a checagem de consistência de `worker/tasks.py::_resume_inconsistency()` hoje operam sobre o texto do livro inteiro numa chamada só. Precisam ser adaptados pra somar a contagem por capítulo (ex: soma de `count_text_chunks()` de cada capítulo limpo/chunkado individualmente) — a checagem de consistência da retomada (OS-022) e o total da OS-024 **não podem quebrar**.

- **Persistência de capítulos:** `storage/db.py` ganha uma tabela nova (`chapters`, ou nome equivalente) com `book_id, id, title, order, start_page, end_page`. Funções novas: `create_chapters(book_id, chapters)`, `list_chapters(book_id)`.
- **Endpoint novo:** `GET /books/{id}/chapters` — devolve a lista de capítulos (id, title, order, start_page, end_page; **sem** o campo `text` na resposta, por tamanho).

**Fora do escopo:**
- Sub-capítulos / níveis aninhados do TOC (só nível 1 nesta OS).
- Edição manual de capítulos pelo usuário.
- UI (seletor de capítulos) — isso é a OS-029.
- Progresso de leitura / "onde parei" — isso é a OS-028.

## 3. Contratos envolvidos

`Chapter` (`ARQUITETURA.md` seção 5) ganha dois campos novos, `start_page: int` e `end_page: int` — extensão do modelo, proposta aqui. `Chapter.text`, que já existe no modelo mas nunca foi usado de verdade, passa a guardar o texto limpo daquele capítulo específico (não mais o livro inteiro). Nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda.

**Coordenação com outras OS's em paralelo:** esta OS toca `core/pipeline.py` e `worker/tasks.py`, os mesmos arquivos que a OS-025 (seleção manual de idioma) também altera. Se as duas estiverem em andamento ao mesmo tempo, uma delas vai precisar rebasear sobre a outra — sinalizar no relatório qual ordem de merge foi seguida.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] PDF com TOC embutido: `detect_chapters()` devolve os capítulos reais (título + intervalo de páginas) do nível 1
- [ ] PDF sem TOC: cai no fallback sintético, sem quebrar
- [ ] Cada `AudioChunk` sintetizado carrega o `chapter_id` do capítulo correto (não mais um id único pro livro inteiro)
- [ ] `AudioChunk.sequence` continua único e contínuo por `book_id`, sem resetar entre capítulos
- [ ] `GET /books/{id}/chapters` devolve a lista de capítulos persistidos
- [ ] A checagem de consistência da retomada (OS-022) continua funcionando corretamente com o novo chunking por capítulo
- [ ] `chunks_total` da barra de progresso (OS-024) continua correto (soma de todos os capítulos) com o novo chunking
- [ ] Nenhum teste das OS-008/009/013/021/022/024 quebra

## 5. Testes exigidos (mínimo)

- `test_detect_chapters_reads_toc_when_present`
- `test_detect_chapters_falls_back_to_synthetic_grouping_when_no_toc`
- `test_worker_process_job_assigns_correct_chapter_id_per_audio_chunk`
- `test_worker_process_job_keeps_sequence_global_across_chapters`
- `test_get_books_chapters_returns_persisted_chapters`
- `test_resume_consistency_check_works_across_chapters` (regressão OS-022)
- `test_chunks_total_correct_with_multiple_chapters` (regressão OS-024)

Local sugerido: `tests/integration/test_pipeline_end_to_end.py`, `tests/unit/test_worker.py`, `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-027-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
