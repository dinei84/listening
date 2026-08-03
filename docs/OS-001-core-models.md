# OS-001 — Modelos de dados base (core/models.py)

## 1. Objetivo

Criar os modelos de dados centrais (`ExtractedPage`, `Chapter`, `AudioChunk`, `Book`, `Job`) que todo o resto do sistema vai usar, conforme definidos em `ARQUITETURA.md` seção 5.

## 2. Escopo

**Dentro do escopo:**
- Criar `core/models.py` com as classes Pydantic exatamente como especificado em `ARQUITETURA.md` seção 5.
- Validações básicas de cada campo (ex: `status` só aceita os valores do enum definido).

**Fora do escopo:**
- Nenhuma lógica de negócio (pipeline, extractors, speakers) — isso é OS futura.
- Nenhuma integração com banco de dados — os modelos são apenas estruturas de dados puras nesta etapa.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 5 (Modelos de dados). Esta OS implementa o contrato já definido — não propõe nenhum novo.

## 4. Critérios de aceite

- [ ] `Book.status` aceita apenas os valores: `uploaded, extracting, processing, synthesizing, ready, error`
- [ ] `Job.status` aceita apenas os valores: `queued, running, done, failed`
- [ ] Instanciar `Book` sem `chapters` resulta em lista vazia por padrão, não erro
- [ ] `ExtractedPage.confidence` tem valor padrão `1.0`

## 5. Testes exigidos (mínimo)

- `test_book_rejects_invalid_status`
- `test_job_rejects_invalid_status`
- `test_book_defaults_to_empty_chapters_list`
- `test_extracted_page_defaults_confidence_to_one`

## 6. Relatório

*A preencher pelo agente ao concluir a OS.*
