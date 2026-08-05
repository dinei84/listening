# OS-028 — Persistência de progresso de leitura no servidor

## 1. Objetivo

Hoje "onde parei" existe só no `localStorage` do navegador (`player/app.js`, `STORAGE_KEY`) — some ao trocar de navegador/dispositivo, e não é visível como um "localizador" de verdade, só um banner silencioso de "retomar?" ao reabrir. Esta OS persiste a posição de leitura atual no servidor (`books.db`), pra ela sobreviver entre sessões/dispositivos e alimentar o indicador de posição do Visualizador (OS-029).

**Sem dependência técnica dura da OS-027:** esta OS não precisa que capítulos existam pra funcionar — progresso é `book_id + sequence + posição em segundos`, independente de capítulo. A ordem sugerida (depois da OS-027) é só por conveniência de produto (mostrar "capítulo X" no indicador junto com a posição), não uma dependência de dados. Pode ser executada antes da OS-027 se for mais conveniente.

## 2. Escopo

**Dentro do escopo:**
- `core/models.py`: `ReadingProgress` novo — `book_id: str`, `sequence: int`, `position_seconds: float`, `updated_at: datetime`.
- `storage/db.py` (ou módulo novo `storage/progress_store.py`, mesmo padrão de um storage por conceito já usado em `audio_store.py`): tabela nova `reading_progress` (chave primária `book_id` — guarda só a posição **atual**, sobrescreve a cada atualização, sem histórico). Funções: `save_progress(book_id, sequence, position_seconds, db_path=None) -> None` e `get_progress(book_id, db_path=None) -> ReadingProgress | None`.
- `api/routes_books.py` (ou router novo `api/routes_progress.py`): `PUT /books/{id}/progress` (recebe `sequence` + `position_seconds`, grava/sobrescreve) e `GET /books/{id}/progress` (devolve o progresso salvo, 404 se nunca gravado pra esse livro).
- `player/app.js`: `saveState()` passa a chamar `PUT /books/{id}/progress` (mantendo o mesmo throttle de hoje, `SAVE_THROTTLE_MS`), em vez de (ou além de) gravar só no `localStorage`. Ao abrir um livro, busca `GET /books/{id}/progress` para decidir se mostra o banner de retomar — **servidor é a fonte de verdade; `localStorage` pode continuar existindo como cache/fallback, mas não é mais autoritativo.** Documentar essa decisão no relatório.

**Fora do escopo:**
- Histórico de progresso (só a posição atual, sempre sobrescrita).
- Sincronização em tempo real entre abas/dispositivos abertos simultaneamente (sem WebSocket — só leitura sob demanda, ao abrir o livro).
- Indicador visual de posição / seletor de capítulos na UI — isso é a OS-029.

## 3. Contratos envolvidos

Nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda. `core/models.py` ganha um modelo novo (`ReadingProgress`) — atualizar `ARQUITETURA.md` seção 5.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `PUT /books/{id}/progress` grava a posição, sobrescrevendo qualquer valor anterior do mesmo livro
- [ ] `GET /books/{id}/progress` devolve a última posição salva; 404 se nunca foi salva
- [ ] Player grava a posição no servidor durante a reprodução (mesmo throttle de hoje)
- [ ] Ao reabrir um livro, o player usa o progresso do servidor (não só `localStorage`) para decidir se oferece retomar
- [ ] 404 em `PUT`/`GET /books/{id}/progress` para um `book_id` inexistente

## 5. Testes exigidos (mínimo)

- `test_save_progress_persists_position`
- `test_save_progress_overwrites_previous_value_for_same_book`
- `test_get_progress_returns_404_when_never_saved`
- `test_put_books_progress_returns_404_for_unknown_book`

Local sugerido: `tests/unit/test_progress_store.py` (ou onde o módulo de storage escolhido viver), `tests/integration/test_api_books.py`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-028-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
