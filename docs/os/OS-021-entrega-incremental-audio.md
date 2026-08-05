# OS-021 — Entrega incremental de áudio

## 1. Objetivo

Achado processando um livro de 1212 páginas (Security Engineering) em uso real: depois de 11 minutos de worker rodando, **zero** `AudioChunk` persistido — `worker/tasks.py` só chama `storage.audio_store.persist_chunks()` **uma vez**, depois que `pipeline.synthesize_text()` termina de sintetizar o livro **inteiro**. Pra um livro grande isso significa esperar o processamento completo (potencialmente muito longo, com a síntese neural real desde a OS-019) antes de qualquer áudio existir. Esta OS muda isso: cada `AudioChunk` é persistido assim que fica pronto, não só no final.

## 2. Escopo

**Dentro do escopo:**
- `core/pipeline.py::synthesize_text()` ganha um parâmetro novo, opcional: `on_chunk: Callable[[AudioChunk], None] | None = None`. Depois de sintetizar cada chunk (dentro do loop que já existe), se `on_chunk` foi passado, chamar `on_chunk(audio_chunk)` imediatamente — antes de seguir pro próximo chunk. **O retorno da função continua sendo a lista completa no final, comportamento e assinatura existentes inalterados quando `on_chunk` não é passado** — nenhum chamador/teste já existente (desde a OS-009) deve precisar mudar.
- `worker/tasks.py::process_job()`: passar um `on_chunk` que persiste cada `AudioChunk` via `storage.audio_store` (`persist_chunks(job.book_id, [chunk])`, ou uma função nova `persist_chunk(book_id, chunk)` singular — decisão de implementação, documentar a escolhida) assim que ele chega, em vez de coletar tudo numa lista e persistir uma vez só no final.
- `worker/tasks.py::process_job()`: atualizar `Book.status` para `"synthesizing"` **antes** de começar o loop de síntese (usa o valor já existente no `Literal` de `Book.status` em `core/models.py`, definido desde a OS-002, nunca usado até agora). Só muda pra `"ready"` depois que a síntese inteira terminar com sucesso (comportamento de sucesso/erro no final continua o mesmo de hoje).
- Confirmar (com teste de integração) que `GET /books/{id}/audio` — que já existe e **não checa o status do livro**, só lista o que tem na tabela `audio_chunks` — passa a devolver chunks parciais enquanto o livro ainda está `synthesizing`. Não deveria exigir nenhuma mudança de código nesse endpoint, só validar que o comportamento já existente funciona com a persistência incremental.

**Fora de escopo:**
- Mudar o `player/` pra realmente **tocar** os chunks parciais antes do livro ficar `ready` (hoje o player só busca áudio quando o status vira `ready` — ver `pollUntilReady()` em `player/app.js`). Essa OS só habilita a capacidade no backend; ligar isso na UI é uma OS seguinte, mesmo padrão já usado (OS-013 → OS-014, OS-015 → OS-016).
- Retomar processamento interrompido (`Job` órfão em `running` depois de o worker cair) — depende desta OS existir primeiro, é a OS-022.
- Qualquer mudança no contrato `Speaker` ou `JobQueue`.
- Barra de progresso ou contagem de "X de Y chunks prontos" na API/UI — pode ser um approfundamento futuro; esta OS só garante que o áudio existe incrementalmente, não que o progresso é comunicado numericamente.

## 3. Contratos envolvidos

`core/pipeline.py::synthesize_text()` ganha um parâmetro novo **opcional**, com valor padrão que preserva o comportamento atual — não é uma mudança quebrando o contrato estabelecido na OS-009. Nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `synthesize_text()` aceita `on_chunk` opcional, chamado imediatamente após cada `AudioChunk` ser sintetizado
- [ ] Sem `on_chunk`, `synthesize_text()` se comporta exatamente como antes (todos os testes da OS-009 continuam passando sem modificação)
- [ ] `worker/tasks.py` persiste cada `AudioChunk` via `on_chunk`, não mais numa chamada só no final
- [ ] `Book.status` vira `"synthesizing"` antes do primeiro chunk, `"ready"` só depois que todos terminarem com sucesso
- [ ] Teste confirma que chunks já persistidos aparecem em `GET /books/{id}/audio` **antes** do job terminar (livro ainda `synthesizing`)
- [ ] Teste confirma a persistência incremental de verdade (não só que o resultado final está certo) — ex: dublê de `Speaker` que demora entre chunks, verificar que o primeiro já está no banco antes do segundo ser sintetizado
- [ ] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 5. Testes exigidos (mínimo)

- `test_synthesize_text_calls_on_chunk_for_each_chunk`
- `test_synthesize_text_returns_full_list_when_on_chunk_is_none` (regressão — comportamento existente preservado)
- `test_worker_process_job_persists_chunks_incrementally`
- `test_worker_process_job_sets_book_status_to_synthesizing_before_ready`
- `test_get_books_audio_returns_partial_chunks_while_synthesizing`

Local sugerido: `tests/integration/test_pipeline_end_to_end.py` (para `synthesize_text`), `tests/unit/test_worker.py` e `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-021-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
