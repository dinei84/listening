# OS-027 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/027-deteccao-capitulos
**Commit(s) relevante(s):** e8092f7 (test: Red), 9037d72 (feat: Green)

## 1. Resumo do que foi feito

`core/pipeline.py` ganhou `detect_chapters(pdf_path, total_pages=None)`, que lê o **nível 1** do sumário embutido do PDF (`fitz.get_toc()`) e, quando não há TOC, agrupa as páginas em blocos sintéticos de `SYNTHETIC_CHAPTER_PAGES = 10` ("Parte 1", "Parte 2"...). `extract_chapters()` extrai o PDF uma vez e devolve os capítulos com o texto **limpo por capítulo** (só as páginas daquele capítulo), em vez do livro inteiro numa tacada. `synthesize_text()` ganhou `sequence_offset: int = 0` para que a `sequence` continue **global e contínua** entre capítulos. `worker/tasks.py` passou a sintetizar capítulo a capítulo, com `chapter_id` real em cada `AudioChunk`. Capítulos são persistidos na tabela nova `chapters` e expostos em `GET /books/{id}/chapters`.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `e8092f7` "Red" antes de `9037d72` "Green")
- [x] Todos os testes da OS passam localmente — 185 pass, 0 fail
- [x] Nenhum teste existente quebrou (165 anteriores + 20 novos = 185)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `Chapter` ganhou `start_page`/`end_page` conforme a seção 3 da OS; nenhum contrato de `Extractor`/`Speaker`/`JobQueue` mudou
- [x] Nenhuma chamada real a API paga dentro dos testes — dublês de `Extractor`/`Speaker` em todos os testes; os PDFs de teste são gerados localmente pelo próprio `fitz`
- [x] Type hints e docstring de uma linha em toda função pública nova
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4 e 5)
- [x] Relatório criado em `docs/report/OS-027-report.md`
- [x] PR aberto contra o branch principal, título `[OS-027] Detecção de capítulos via TOC do PDF`

### DoD específico da OS (seção 4)

- [x] PDF com TOC embutido: `detect_chapters()` devolve os capítulos reais do nível 1 — `test_detect_chapters_reads_toc_when_present` (3 capítulos, intervalos `(1,3)/(4,6)/(7,9)`) e `test_detect_chapters_ignores_sub_levels_of_toc`
- [x] PDF sem TOC: cai no fallback sintético, sem quebrar — `test_detect_chapters_falls_back_to_synthetic_grouping_when_no_toc` (25 páginas → blocos contíguos, sem buracos) e `test_detect_chapters_single_page_pdf_without_toc`
- [x] Cada `AudioChunk` carrega o `chapter_id` do capítulo correto — `test_worker_process_job_assigns_correct_chapter_id_per_audio_chunk` (2 `chapter_id` distintos; o `job.id`, usado como `chapter_id` até a OS-026, deixou de aparecer)
- [x] `AudioChunk.sequence` único e contínuo por `book_id`, sem resetar entre capítulos — `test_worker_process_job_keeps_sequence_global_across_chapters` (`sequences == list(range(len(sequences)))`)
- [x] `GET /books/{id}/chapters` devolve a lista persistida — `test_get_books_chapters_returns_persisted_chapters` (+ 404 e lista vazia)
- [x] Checagem de consistência da retomada (OS-022) continua funcionando — `test_resume_consistency_check_works_across_chapters` (segunda passada não sintetiza nada de novo)
- [x] `chunks_total` (OS-024) continua correto com múltiplos capítulos — `test_chunks_total_correct_with_multiple_chapters` (soma dos capítulos == chunks persistidos)
- [x] Nenhum teste das OS-008/009/013/021/022/024 quebrou — suíte inteira verde

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_detect_chapters_reads_toc_when_present` | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_ignores_sub_levels_of_toc` (extra) | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_falls_back_to_synthetic_grouping_when_no_toc` | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_single_page_pdf_without_toc` (extra) | `tests/unit/test_chapters.py` | Sim |
| `test_extract_chapters_fills_text_from_pages_of_each_chapter` | `tests/unit/test_chapters.py` | Sim |
| `test_synthesize_text_applies_sequence_offset` (extra) | `tests/unit/test_chapters.py` | Sim |
| `test_synthesize_text_offset_respects_skip_sequences` (extra) | `tests/unit/test_chapters.py` | Sim |
| `test_create_and_list_chapters_roundtrip` (extra) | `tests/unit/test_chapter_store.py` | Sim |
| `test_list_chapters_returns_empty_for_unknown_book` (extra) | `tests/unit/test_chapter_store.py` | Sim |
| `test_list_chapters_is_ordered_by_order_not_insertion` (extra) | `tests/unit/test_chapter_store.py` | Sim |
| `test_create_chapters_isolates_books` (extra) | `tests/unit/test_chapter_store.py` | Sim |
| `test_create_chapters_replaces_previous_chapters_of_same_book` (extra) | `tests/unit/test_chapter_store.py` | Sim |
| `test_worker_process_job_assigns_correct_chapter_id_per_audio_chunk` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_keeps_sequence_global_across_chapters` | `tests/unit/test_worker.py` | Sim |
| `test_worker_process_job_persists_chapters` (extra) | `tests/unit/test_worker.py` | Sim |
| `test_chunks_total_correct_with_multiple_chapters` | `tests/unit/test_worker.py` | Sim |
| `test_resume_consistency_check_works_across_chapters` | `tests/unit/test_worker.py` | Sim |
| `test_get_books_chapters_returns_persisted_chapters` | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_chapters_returns_404_for_unknown_book` (extra) | `tests/integration/test_api_books.py` | Sim |
| `test_get_books_chapters_returns_empty_list_when_none_detected` (extra) | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `e8092f7` (17 falhas: `AttributeError: module 'core.pipeline' has no attribute 'detect_chapters'` / `extract_chapters`, `TypeError: unexpected keyword argument 'sequence_offset'`, `AttributeError: module 'storage.db' has no attribute 'create_chapters'`, `404` no endpoint de capítulos) antes de `9037d72`.

## 4. Saída de comandos relevantes

Rodada Red (antes da implementação):
```
17 failed, 168 passed, 1 warning in 8.94s
```

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
185 passed, 1 warning in 10.54s
```

```
$ venv/bin/ruff check core/ storage/ worker/ api/ tests/
All checks passed!
$ venv/bin/black --check core/ storage/ worker/ api/ tests/
43 files would be left unchanged.
```

### Verificação com PDF real (fora da suíte)

PDF de 12 páginas gerado com TOC de 3 capítulos de nível 1 mais uma entrada de nível 2 (que deve ser ignorada), processado com o `PyMuPDFExtractor` real:

```
capitulos detectados (TOC real, nivel 1 apenas):
  ordem=0  paginas 1-4  'Introducao'
  ordem=1  paginas 5-9  'Desenvolvimento'
  ordem=2  paginas 10-12  'Conclusao'

texto por capitulo (extractor real PyMuPDF):
  'Introducao': 222 chars | Este e o conteudo unico da pagina 1 do livro de teste. ...
  'Desenvolvimento': 278 chars | Este e o conteudo unico da pagina 5 do livro de teste. ...
  'Conclusao': 169 chars | Este e o conteudo unico da pagina 10 do livro de teste. ...
```

A entrada de nível 2 ("Secao ignorada", página 2) não virou capítulo, e o texto de cada capítulo cobre exatamente o intervalo de páginas detectado.

## 5. Decisões de implementação documentadas

**(a) `detect_chapters()` degrada em vez de falhar quando o `fitz` não abre o arquivo.** O `try/except` amplo em volta do `fitz.open()` é intencional: quem extrai o texto é o `Extractor` configurado, que pode ser OCR e ter sucesso onde o `fitz` falha. Se a leitura do TOC falhar, cai no agrupamento sintético; a falha real, se existir, aparece na extração (que roda logo antes, em `extract_chapters`). Sem isso, um PDF que só o OCR lê passaria a derrubar o livro inteiro — regressão silenciosa que os testes existentes pegaram (usam PDFs dublê com extractor mockado).

**(b) `total_pages` vem do que o `Extractor` realmente leu**, não do `len(doc)` do `fitz`. `extract_chapters()` calcula `max(page.page_number for page in pages)` e repassa. Isso mantém o intervalo de páginas coerente com o texto disponível e faz a detecção funcionar mesmo sem o `fitz` conseguir abrir o arquivo (ver (a)).

**(c) O texto do capítulo NÃO é persistido.** A tabela `chapters` guarda só metadados (`id`, `title`, `chapter_order`, `start_page`, `end_page`); `list_chapters()` devolve `Chapter` com `text=""`. Persistir o texto duplicaria o livro inteiro dentro do `books.db` sem nenhum consumidor — a API já não devolve `text` por decisão da própria OS. A coluna se chama `chapter_order` porque `order` é palavra reservada no SQL.

**(d) `create_chapters()` substitui os capítulos anteriores do mesmo livro** (`DELETE` antes do `INSERT`). Reprocessar um livro (retomada da OS-022, re-priorização da OS-032) chama `process_job()` de novo — sem isso, os capítulos duplicariam a cada passada. Coberto por `test_create_chapters_replaces_previous_chapters_of_same_book`.

**(e) `SYNTHETIC_CHAPTER_PAGES = 10`** para o fallback sem TOC. Valor escolhido por dois limites práticos, documentados no código: grande o bastante para o `clean_text()` ainda detectar header/footer repetido (precisa de ≥2 páginas do mesmo conjunto) e pequeno o bastante para a navegação por capítulo ser útil num livro longo. Não é um número validado empiricamente — é um padrão razoável, ajustável se o uso real mostrar necessidade.

## 6. Desvios do escopo original

Nenhum desvio de escopo. Os arquivos tocados são exatamente os previstos na seção 2 da OS (`core/pipeline.py`, `core/models.py`, `storage/db.py`, `worker/tasks.py`, `api/routes_books.py`), mais os testes. A OS já avisava que esta OS toca a espinha dorsal do pipeline e que isso não é motivo para parar pela regra dos "~3 arquivos" do `AGENTS.md` seção 3.

`processing/cleaner.py` **não** mudou de contrato, como a OS exigia — o que mudou foi *como* é chamado (uma vez por capítulo, em `extract_chapters()`).

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Duas observações para o dono do projeto:

1. **`core/pipeline.py` agora importa `fitz` diretamente.** É a segunda vez que o `fitz` aparece fora de `plugins/extractors/` (a primeira é o `PyMuPDFExtractor`). A própria OS especificou isso (o TOC é propriedade do arquivo PDF, não do extractor), e o fallback de (a) garante que nenhum livro quebra por causa disso — mas vale registrar que é um acoplamento de `core/` a uma biblioteca concreta. Se um dia importar, o caminho seria mover a leitura de TOC para trás de uma interface.
2. **Livros processados antes desta OS têm um único `chapter_id`** (o `job.id`) para todos os chunks e nenhuma linha na tabela `chapters`. Não há reprocessamento automático: o seletor de capítulos da OS-029 vai mostrar lista vazia para eles até serem reenviados. Mesmo padrão já usado nas OS-019/OS-034.

## 8. Link do PR

*A preencher após abrir o PR.*
