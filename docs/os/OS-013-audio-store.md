# OS-013 — storage/audio_store.py + servir áudio pela API

## 1. Objetivo

Persistir os `AudioChunk` que o pipeline já gera (hoje descartados pelo `worker/tasks.py` — achado na revisão da OS-012, corrigido aqui) e expor um jeito de listar e baixar o áudio de um livro pela API. Pré-requisito direto do player web (próxima OS): sem isso não existe o que tocar.

## 2. Escopo

**Dentro do escopo:**
- `storage/audio_store.py`:
  - Uma tabela própria (ex: `audio_chunks`, mesmo padrão de `plugins/queues/sqlite_queue.py` — schema próprio, idempotente) com `book_id` (o `AudioChunk` do Pydantic não tem esse campo; é um detalhe de armazenamento, não muda o contrato do `Speaker`), `chapter_id`, `sequence`, `file_path`, `duration_seconds`, `engine_used`.
  - Uma função para **persistir** uma lista de `AudioChunk` associada a um `book_id`: ao salvar, mover (ou copiar) o arquivo de áudio do local temporário onde o `Speaker` gravou (`KokoroSpeaker` usa `tempfile.gettempdir()`, sem garantia de retenção) para um diretório estável controlado pelo projeto — ex: `storage/audio/{book_id}/{sequence}.wav`. O `file_path` persistido aponta pro novo local, não pro temporário.
  - Uma função para **listar** os `AudioChunk`s de um `book_id`, ordenados por `sequence`.
- `worker/tasks.py`: capturar o retorno de `pipeline.synthesize_text()` (hoje descartado — `pipeline.synthesize_text(text, chapter_id=chapter.id)` sem atribuir a nada) e persistir via `storage.audio_store` antes de marcar o `Book` como `ready`.
- `api/routes_books.py` (ou um novo `api/routes_audio.py`, à escolha de quem implementar):
  - `GET /books/{id}/audio`: lista os chunks persistidos (sequence, duration_seconds, e uma forma de baixar cada um), ordenados. 404 se o livro não existir.
  - `GET /books/{id}/audio/{sequence}`: serve os bytes do arquivo daquele chunk (`Content-Type` de áudio apropriado). 404 se o livro ou o chunk não existir.
- Diretório estável de áudio (`storage/audio/` ou equivalente) no `.gitignore`, mesmo padrão já usado para `uploads/`/`books.db`.

**Fora do escopo:**
- O player web em si (HTML/JS) — próxima OS.
- Streaming com range requests (retomar do meio do arquivo) — servir o arquivo inteiro já é suficiente para o player básico poder tocar.
- Transcodificação/compressão de áudio.
- Deletar áudio antigo ou qualquer política de retenção.

## 3. Contratos envolvidos

Nenhuma mudança nos contratos de `Extractor`/`Speaker`/`JobQueue`. O modelo Pydantic `AudioChunk` (`core/models.py`) não muda — `book_id` é um detalhe de como `storage/audio_store.py` guarda os dados, não um campo novo no modelo.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `storage/audio_store.py` persiste uma lista de `AudioChunk` associada a um `book_id`
- [ ] Ao persistir, o arquivo é movido/copiado do local temporário do `Speaker` para um diretório estável do projeto; o `file_path` persistido aponta pro novo local, não pro temporário
- [ ] `worker/tasks.py` persiste os `AudioChunk` retornados por `synthesize_text()` antes de marcar o `Book` como `ready` (corrige o retorno hoje descartado)
- [ ] Existe uma função para listar os `AudioChunk`s de um `book_id`, ordenados por `sequence`
- [ ] `GET /books/{id}/audio` devolve a lista ordenada de chunks; 404 se o livro não existir
- [ ] `GET /books/{id}/audio/{sequence}` serve os bytes do áudio daquele chunk; 404 se o livro ou o chunk não existir
- [ ] O diretório estável de áudio está no `.gitignore`
- [ ] Testes usam dublês fake de `Extractor`/`Speaker` — nenhuma chamada real a Tesseract/Kokoro; arquivo de áudio de teste é um `.wav` sintético pequeno (mesmo padrão desde a OS-004), não precisa ser gerado pelo Kokoro de verdade
- [ ] Testes usam diretórios/banco temporários (`tmp_path`) — nenhum lixo no repositório
- [ ] Nenhuma chamada de rede ou API paga

## 5. Testes exigidos (mínimo)

- `test_audio_store_persists_chunks_with_book_id`
- `test_audio_store_moves_file_to_stable_location`
- `test_audio_store_list_chunks_returns_ordered_by_sequence`
- `test_worker_process_job_persists_audio_chunks`
- `test_get_books_audio_returns_ordered_chunk_list`
- `test_get_books_audio_returns_404_for_unknown_book`
- `test_get_book_audio_chunk_serves_file_bytes`
- `test_get_book_audio_chunk_returns_404_for_unknown_sequence`

Local sugerido: `tests/unit/test_audio_store.py`, atualização de `tests/unit/test_worker.py` e `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-013-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
