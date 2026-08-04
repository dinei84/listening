# OS-013 — Relatório de entrega

**Data:** 2026-08-04
**Branch:** os/013-audio-store
**Commit(s) relevante(s):** ff41fb3 (test: Red), f2852bf (feat: Green), 51f0589 (build: .gitignore)

## 1. Resumo do que foi feito

`storage/audio_store.py` persiste os `AudioChunk` gerados pelo pipeline: `persist_chunks()` move o arquivo do local temporário do `Speaker` para `storage/audio/{book_id}/{sequence}.wav` e grava os metadados numa tabela `audio_chunks` própria; `list_chunks()`/`get_chunk()` leem de volta. `worker/tasks.py` agora captura o retorno de `synthesize_text()` (antes descartado) e chama `persist_chunks()` antes de marcar o `Book` como `ready`. Novo `api/routes_audio.py` expõe `GET /books/{id}/audio` (lista ordenada) e `GET /books/{id}/audio/{sequence}` (serve os bytes do arquivo).

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `ff41fb3` "Red" existe antes de `f2852bf` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (77 testes no total, todos passando)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (nenhuma mudança em `Extractor`/`Speaker`/`JobQueue`; `AudioChunk` do Pydantic não muda — `book_id` é só detalhe de armazenamento em `storage/audio_store.py`)
- [x] Nenhuma chamada real a API paga dentro dos testes — dublês fake de `Extractor`/`Speaker`, arquivo de áudio de teste é um `.wav` sintético (bytes dummy escritos em disco, não gerado pelo Kokoro)
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2 + seção 6)
- [x] Relatório criado em `docs/report/OS-013-report.md`
- [x] PR aberto contra o branch principal, com título `[OS-013] storage/audio_store.py + servir áudio pela API`

### DoD específico da OS (seção 4 de `docs/os/OS-013-audio-store.md`)

- [x] `storage/audio_store.py` persiste uma lista de `AudioChunk` associada a um `book_id`
- [x] Ao persistir, o arquivo é movido (`shutil.move`) do local temporário do `Speaker` para um diretório estável do projeto (`storage/audio/{book_id}/{sequence}{extensão}`); o `file_path` persistido aponta pro novo local, não pro temporário
- [x] `worker/tasks.py` persiste os `AudioChunk` retornados por `synthesize_text()` antes de marcar o `Book` como `ready`
- [x] Existe `list_chunks(book_id)` para listar os `AudioChunk`s de um `book_id`, ordenados por `sequence`
- [x] `GET /books/{id}/audio` devolve a lista ordenada de chunks; 404 se o livro não existir
- [x] `GET /books/{id}/audio/{sequence}` serve os bytes do áudio daquele chunk; 404 se o livro ou o chunk não existir
- [x] O diretório estável de áudio (`storage/audio/`) está no `.gitignore`
- [x] Testes usam dublês fake de `Extractor`/`Speaker` — nenhuma chamada real a Tesseract/Kokoro; arquivo de áudio de teste é um `.wav` sintético pequeno (bytes fixos gravados via `tempfile.mkstemp`), não gerado pelo Kokoro de verdade
- [x] Testes usam diretórios/banco temporários (`tmp_path`) — nenhum lixo no repositório (confirmado: `storage/audio/`, `uploads/`, `books.db` ausentes do working tree após rodar a suíte completa)
- [x] Nenhuma chamada de rede ou API paga

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_audio_store_persists_chunks_with_book_id` | `tests/unit/test_audio_store.py` | Sim |
| `test_audio_store_moves_file_to_stable_location` | `tests/unit/test_audio_store.py` | Sim |
| `test_audio_store_list_chunks_returns_ordered_by_sequence` | `tests/unit/test_audio_store.py` | Sim |
| `test_worker_process_job_persists_audio_chunks` | `tests/unit/test_worker.py` | Sim |
| `test_get_books_audio_returns_ordered_chunk_list` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_audio_returns_404_for_unknown_book` | `tests/integration/test_api_books.py` | Sim |
| `test_get_book_audio_chunk_serves_file_bytes` | `tests/integration/test_api_books.py` | Sim |
| `test_get_book_audio_chunk_returns_404_for_unknown_sequence` | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Testes falhando antes da implementação (commit Red, `ff41fb3`) — 16 erros de coleta/setup, todos pela mesma causa raiz:

```
tests/unit/test_audio_store.py: ModuleNotFoundError / ImportError — 'storage.audio_store' vazio
tests/unit/test_worker.py: AttributeError: <module 'storage.audio_store' ...> has no attribute 'DEFAULT_DB_PATH'
tests/integration/test_api_books.py: AttributeError: <module 'storage.audio_store' ...> has no attribute 'DEFAULT_DB_PATH'
```

Suíte completa após a implementação (commit Green, `f2852bf`, e após formatação):

```
$ python -m pytest -q
........................................................................ [ 93%]
.....                                                                    [100%]
77 passed, 1 warning in 5.90s
```

O warning é o mesmo `StarletteDeprecationWarning` pré-existente já registrado nos relatórios da OS-010/011/012 (não introduzido por esta OS).

`black --check` e `ruff check` nos arquivos tocados por esta OS: sem alterações pendentes, todos os checks passaram. `ruff check .` no repositório inteiro mostra os mesmos 3 erros pré-existentes em `scripts/spike_ocr_confidence.py` (da OS-005) já registrados no relatório da OS-010 — confirmado via `git status`/histórico que este branch não toca nesse arquivo.

## 5. Desvios do escopo original

Nenhum. Implementados apenas `storage/audio_store.py`, a mudança em `worker/tasks.py` (captura o retorno de `synthesize_text()`), o novo `api/routes_audio.py` (registrado em `api/main.py`) e a entrada no `.gitignore`. Nenhuma mudança em `plugins/`, contratos de `Extractor`/`Speaker`/`JobQueue`, streaming/range requests, transcodificação ou política de retenção — tudo explicitamente fora de escopo, conforme a OS.

Decisões de implementação dentro do espaço deixado em aberto:

- **Rota nova (`api/routes_audio.py`) em vez de adicionar em `api/routes_books.py`.** A OS deixava as duas opções em aberto ("à escolha de quem implementar"). Escolhi separar porque `routes_books.py` já cobre criação/status do livro, e misturar rotas de áudio ali tornaria o arquivo responsável por duas coisas (metadados do livro vs. servir arquivos binários) — mais fácil de navegar/testar separado, sem custo real de complexidade adicional (é só um `APIRouter` a mais, registrado em `api/main.py`).
- **Tabela `audio_chunks` no mesmo arquivo `books.db`** (chave primária composta `(book_id, sequence)`), com `storage/audio_store.py` mantendo seu próprio `DEFAULT_DB_PATH = "books.db"` desacoplado de `storage/db.py`/`plugins/queues/sqlite_queue.py` — mesmo padrão e mesma justificativa já registrados nos relatórios da OS-011/OS-012 (simplicidade de um único arquivo SQLite para um projeto pessoal; troca isolada se algum dia virar problema).
- **`media_type="audio/wav"` fixo** em `GET /books/{id}/audio/{sequence}`, em vez de inferir a partir da extensão do arquivo. Justificado porque o único `Speaker` que existe hoje (`KokoroSpeaker`) sempre grava `.wav` via `soundfile`; generalizar para múltiplos formatos seria especular sobre um `Speaker` que ainda não existe (`PiperSpeaker`/`CloudSpeaker` continuam fora do registry).
- **Nome do arquivo persistido usa a extensão original do arquivo de origem** (`f"{sequence}{source.suffix}"`, ex: `0.wav`), não um `.wav` hardcoded — mantém `storage/audio_store.py` agnóstico ao formato de saída de qualquer `Speaker` futuro, sem exigir mudança nesta OS.

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

https://github.com/dinei84/listening/pull/11
