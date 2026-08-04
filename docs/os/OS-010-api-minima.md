# OS-010 — API mínima (POST /books, GET /books/{id}/status)

## 1. Objetivo

Expor o pipeline já existente (extração → limpeza → chunking → síntese) via HTTP, com processamento **síncrono** (a requisição bloqueia até terminar) e persistência mínima em **SQLite** — decisão #4 confirmada pelo dono do projeto (ver `PROJECT_STATE.md` decisão #10). Fila assíncrona (decisão #3) continua em aberto e fora do escopo desta OS, conforme o roadmap de `ARQUITETURA.md` seção 8 (API vem antes da fila).

## 2. Escopo

**Dentro do escopo:**
- `storage/db.py` — usar `sqlite3` da stdlib (sem ORM, sem dependência nova): funções para inicializar o schema, criar um `Book`, buscar um `Book` por id, e atualizar o `status` de um `Book`. Arquivo do banco fica fora do controle de versão (adicionar ao `.gitignore`).
- `api/main.py` — app FastAPI mínimo, monta as rotas de `routes_books.py`.
- `api/routes_books.py`:
  - `POST /books`: recebe upload de um PDF (`UploadFile`), salva em disco, cria um `Book` (status inicial `uploaded`), roda o pipeline **na própria requisição** (sem fila): `extract_clean_text()` → um único `Chapter` sintético contendo todo o texto limpo (esta OS não faz detecção de capítulos) → `synthesize_text()`. Se tudo der certo, marca o `Book` como `ready`; se qualquer etapa falhar, marca como `error` **sem deixar a exceção estourar como 500 não tratado** — a requisição ainda deve responder normalmente com o id do livro e status `error`. Devolve o `id` e o `status` do `Book`.
  - `GET /books/{id}/status`: busca o `Book` no SQLite pelo id e devolve o `status`. 404 se o id não existir.
- Adicionar `python-multipart` a `requirements.txt` (necessário para o FastAPI processar upload multipart) — conferir a versão real no PyPI antes de travar, como já é praxe no projeto desde a OS-001.

**Fora do escopo:**
- Fila assíncrona / processamento em background (`worker/`) — decisão #3 continua em aberto.
- `storage/audio_store.py` e qualquer endpoint para baixar/tocar o áudio gerado — esta OS só precisa provar que `Book` chega a `ready`, não servir o resultado.
- Detecção de capítulos — sempre um único capítulo sintético cobrindo o texto todo.
- Autenticação, rate limiting, ou qualquer coisa de produção multiusuário — é um app pessoal.
- `GET /books` (listagem) — só os dois endpoints pedidos.

## 3. Contratos envolvidos

Nenhum contrato de `Extractor`/`Speaker` muda. A API consome `core.pipeline` (`extract_clean_text`, `synthesize_text`) exatamente como esses já existem — não deve reimplementar nem contornar a orquestração.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `storage/db.py` inicializa um schema SQLite com pelo menos uma tabela de `books` (id, title, original_filename, status, created_at)
- [ ] `POST /books` cria um `Book`, roda o pipeline síncrono e devolve `id` + `status`
- [ ] `POST /books` com um PDF que falha no processamento devolve resposta normal (não 500 não tratado) com `status == "error"`
- [ ] `GET /books/{id}/status` devolve o `status` persistido do livro
- [ ] `GET /books/{id}/status` devolve 404 para um id que não existe
- [ ] O arquivo do banco SQLite está no `.gitignore`
- [ ] `python-multipart` adicionado a `requirements.txt` com versão real conferida no PyPI
- [ ] Testes usam `fastapi.testclient.TestClient` e mockam `core.pipeline` (via `registry`/`config`, como já é padrão desde a OS-007) — nenhum teste roda Tesseract/Kokoro de verdade
- [ ] Testes usam um banco SQLite temporário (não o arquivo real do projeto) — não deixar lixo de teste no repositório
- [ ] Nenhuma chamada de rede ou API paga

## 5. Testes exigidos (mínimo)

- `test_db_init_creates_books_table`
- `test_db_create_and_get_book_roundtrip`
- `test_db_update_book_status`
- `test_post_books_creates_book_and_returns_ready_status`
- `test_post_books_returns_error_status_when_pipeline_fails`
- `test_get_books_status_returns_persisted_status`
- `test_get_books_status_returns_404_for_unknown_id`

Local sugerido: `tests/unit/test_db.py` e `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-010-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
