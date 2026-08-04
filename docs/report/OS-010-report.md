# OS-010 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** os/010-api-minima
**Commit(s) relevante(s):** 94a0afd (test: Red), c5582ed (feat: Green), 0c74a4a (build: requirements.txt + .gitignore)

## 1. Resumo do que foi feito

`storage/db.py` implementado com `sqlite3` puro da stdlib (schema `books`, `create_book`/`get_book`/`update_book_status`), e `api/main.py`/`api/routes_books.py` expõem `POST /books` (upload de PDF, roda `extract_clean_text()` → `Chapter` sintético único → `synthesize_text()` na própria requisição, marca `Book` como `ready` ou `error`) e `GET /books/{id}/status` (404 se não existir).

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `94a0afd` "Red" existe antes de `c5582ed` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (54 testes no total, todos passando)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (nenhum contrato de `Extractor`/`Speaker` mudou; a API consome `core.pipeline.extract_clean_text`/`synthesize_text` exatamente como já existiam, sem reimplementar orquestração)
- [x] Nenhuma chamada real a API paga dentro dos testes — tudo com dublês fake de `Extractor`/`Speaker`, via `TestClient`
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2)
- [x] Relatório criado em `docs/report/OS-010-report.md`
- [x] PR aberto contra o branch principal, com título `[OS-010] API mínima (POST /books, GET /books/{id}/status)`

### DoD específico da OS (seção 4 de `docs/os/OS-010-api-minima.md`)

- [x] `storage/db.py` inicializa um schema SQLite com tabela `books` (id, title, original_filename, status, created_at)
- [x] `POST /books` cria um `Book`, roda o pipeline síncrono e devolve `id` + `status`
- [x] `POST /books` com um PDF que falha no processamento devolve resposta normal (200, não 500) com `status == "error"` — captura ampla e intencional em `except Exception` (comentada e com `# noqa: BLE001`, já que o objetivo é nunca deixar a exceção do pipeline estourar como 500)
- [x] `GET /books/{id}/status` devolve o `status` persistido do livro
- [x] `GET /books/{id}/status` devolve 404 para um id que não existe
- [x] O arquivo do banco SQLite (`books.db`) e a pasta `uploads/` estão no `.gitignore`
- [x] `python-multipart` adicionado a `requirements.txt` com versão real conferida no PyPI (`0.0.32`, latest no momento — instalado e confirmado via `pip show`)
- [x] Testes usam `fastapi.testclient.TestClient` e mockam `core.pipeline` via `registry`/`config` (mesmo padrão desde a OS-007) — nenhum teste roda Tesseract/Kokoro de verdade
- [x] Testes usam um banco SQLite temporário (`tmp_path`, via monkeypatch de `storage.db.DEFAULT_DB_PATH`) — nada de lixo de teste no repositório; a pasta de uploads também foi isolada em `tmp_path` pelo mesmo motivo (não fazia parte do DoD literal, mas a mesma regra de "não deixar lixo" se aplicava)
- [x] Nenhuma chamada de rede ou API paga

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_db_init_creates_books_table` | `tests/unit/test_db.py` | Sim |
| `test_db_create_and_get_book_roundtrip` | `tests/unit/test_db.py` | Sim |
| `test_db_update_book_status` | `tests/unit/test_db.py` | Sim |
| `test_post_books_creates_book_and_returns_ready_status` | `tests/integration/test_api_books.py` | Sim |
| `test_post_books_returns_error_status_when_pipeline_fails` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_status_returns_persisted_status` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_status_returns_404_for_unknown_id` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Testes falhando antes da implementação (commit Red, `94a0afd`):

```
tests/integration/test_api_books.py: ImportError: cannot import name 'app' from 'api.main'
tests/unit/test_db.py::test_db_init_creates_books_table
  AttributeError: module 'storage.db' has no attribute 'init_db'
tests/unit/test_db.py::test_db_create_and_get_book_roundtrip
  AttributeError: module 'storage.db' has no attribute 'init_db'
tests/unit/test_db.py::test_db_update_book_status
  AttributeError: module 'storage.db' has no attribute 'init_db'
```

Instalação e verificação de versão do `python-multipart`:

```
$ pip install python-multipart==0.0.32
Successfully installed python-multipart-0.0.32
$ pip index versions python-multipart
python-multipart (0.0.32)
Available versions: 0.0.32, 0.0.31, ...
```

Suíte completa após a implementação (commit Green, `c5582ed`, e após ajustes de lint):

```
$ python -m pytest -q
......................................................                   [100%]
54 passed, 1 warning in 5.94s
```

O único warning é pré-existente ao ambiente (não introduzido por esta OS): `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` — decorre da versão do FastAPI/Starlette já travada em `requirements.txt` desde a OS-001, não uma regressão desta OS. Registrado aqui para visibilidade, não corrigido (trocar o cliente de teste ou a versão do FastAPI está fora do escopo desta OS).

`black --check` e `ruff check` nos arquivos tocados por esta OS: sem alterações pendentes, todos os checks passaram. `ruff check .` no repositório inteiro aponta 3 erros pré-existentes em `scripts/spike_ocr_confidence.py` (da OS-005, `except Exception` blindo) — confirmado via `git diff main -- scripts/spike_ocr_confidence.py` (sem diferenças), portanto não introduzidos por esta OS e fora do escopo declarado para corrigir.

## 5. Desvios do escopo original

Nenhum desvio do escopo declarado. Implementadas somente as três coisas pedidas: `storage/db.py`, `api/main.py`, `api/routes_books.py`, mais a atualização de `requirements.txt`/`.gitignore` explicitamente exigida pela própria OS.

Duas decisões de implementação dentro do espaço deixado em aberto:

- **Lint (`ruff`) neste ambiente tem `flake8-datetimez` (DTZ) e `flake8-blind-except` (BLE) ativos por padrão** (não há `pyproject.toml`/`ruff.toml` no repo — é o comportamento padrão da versão instalada). Isso nunca apareceu nas OS's anteriores porque nenhuma usava `datetime.now()` nem `except Exception`. Resolvido usando `datetime.now(UTC)` (e `tzinfo=UTC` no fixture de teste) e um `except Exception:  # noqa: BLE001` comentado explicando que a captura ampla é intencional (requisito explícito da OS: "sem deixar a exceção estourar como 500 não tratado"). Nenhum contrato de `core/models.py` mudou — `Book.created_at` continua `datetime`, agora só populado como timezone-aware onde antes nunca tinha sido instanciado com um valor real.
- **Local dos PDFs enviados:** a OS não especificava onde salvar o arquivo em disco, só que deveria salvar. Usei `api/routes_books.UPLOAD_DIR = Path("uploads")` (pasta na raiz do projeto, criada sob demanda, adicionada ao `.gitignore`), seguindo o mesmo padrão de "dado de runtime não versionado" já usado para `books.db`. Testes isolam essa pasta em `tmp_path` via monkeypatch, do mesmo jeito que isolam o banco.

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

https://github.com/dinei84/listening/pull/8
