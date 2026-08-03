# OS-008 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** os/008-cleaner-chunker
**Commit(s) relevante(s):** 3188c65 (test: Red), f427cd0 (feat: Green)

## 1. Resumo do que foi feito

Implementado `processing/cleaner.py` (`clean_text()` — remove headers/footers repetidos entre páginas e corrige hifenização de quebra de linha, preservando parágrafos) e `processing/chunker.py` (`chunk_text()` — divide texto em chunks por sentença com `max_chars` configurável, nunca cortando uma sentença no meio), usando apenas `re`/`collections.Counter` da stdlib.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `3188c65` "Red" existe antes de `f427cd0` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (42 testes no total, todos passando)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (`cleaner`/`chunker` não são plugins — lógica fixa direto em `processing/`, conforme seção 1; regra da seção 6 item 5 respeitada — chunking por sentença, nunca corte fixo de caracteres)
- [x] Nenhuma chamada real a API paga dentro dos testes — `cleaner`/`chunker` não fazem I/O nem chamam nenhum plugin
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2)
- [x] Relatório criado em `docs/report/OS-008-report.md`
- [ ] PR aberto contra o branch principal, com título `[OS-008] processing/cleaner.py + processing/chunker.py` — a abrir na próxima etapa deste fluxo

### DoD específico da OS (seção 4 de `docs/os/OS-008-cleaner-chunker.md`)

- [x] `cleaner` remove uma linha que se repete em pelo menos duas páginas de um texto de fixture conhecido (assert no resultado exato)
- [x] `cleaner` corrige pelo menos um caso de hifenização de quebra de linha
- [x] `cleaner` preserva quebras de parágrafo que não são header/footer/hifenização
- [x] `cleaner` com entrada vazia devolve string vazia, sem erro
- [x] `chunker` nunca corta uma sentença no meio — testado com texto de tamanho conhecido, limites exatos dos chunks verificados
- [x] `chunker` respeita o tamanho máximo configurável quando possível (quando não há sentença isolada maior que o limite)
- [x] `chunker` com uma única sentença maior que o limite devolve essa sentença inteira como um chunk
- [x] `chunker` com entrada vazia devolve lista vazia, sem erro
- [x] Nenhuma dependência nova pesada de NLP adicionada a `requirements.txt` — usado apenas `re` e `collections.Counter` da stdlib, suficientes para separação de sentenças por pontuação (`.`/`!`/`?`) e contagem de linhas repetidas

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_clean_text_removes_repeated_header_across_pages` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_removes_repeated_footer_across_pages` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_fixes_hyphenation_across_line_break` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_preserves_paragraph_breaks` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_handles_empty_input` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_chunk_text_never_splits_a_sentence` | `tests/unit/processing/test_chunker.py` | Sim |
| `test_chunk_text_respects_max_chars_when_possible` | `tests/unit/processing/test_chunker.py` | Sim |
| `test_chunk_text_keeps_oversized_single_sentence_as_one_chunk` | `tests/unit/processing/test_chunker.py` | Sim |
| `test_chunk_text_handles_empty_input` | `tests/unit/processing/test_chunker.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Testes falhando antes da implementação (commit Red, `3188c65`):

```
tests/unit/processing/test_cleaner.py:1: in <module>
    from processing.cleaner import clean_text
E   ImportError: cannot import name 'clean_text' from 'processing.cleaner'

tests/unit/processing/test_chunker.py:1: in <module>
    from processing.chunker import chunk_text
E   ImportError: cannot import name 'chunk_text' from 'processing.chunker'
```

Suíte completa após a implementação (commit Green, `f427cd0`):

```
$ python -m pytest -q
..........................................                               [100%]
42 passed in 6.02s
```

`black --check` e `ruff check` nos arquivos tocados por esta OS: sem alterações pendentes, todos os checks passaram sem necessidade de reformatação.

## 5. Desvios do escopo original

Nenhum. Implementadas somente `processing/cleaner.py` e `processing/chunker.py`, sem tocar em `core/pipeline.py` (ligação explicitamente fora do escopo desta OS) nem em nenhum outro módulo.

Uma decisão de implementação dentro do espaço deixado em aberto pela OS (que definia a regra mas não o valor exato):

- **`DEFAULT_MAX_CHARS = 1000`** em `processing/chunker.py`, documentado no próprio código: grande o suficiente para reduzir o número de chamadas ao Speaker por capítulo (menos overhead), pequeno o suficiente para manter tempo de síntese e tamanho de `AudioChunk` por chunk previsíveis. Não é um valor validado empiricamente contra o Kokoro real — é um ponto de partida razoável, ajustável depois que `cleaner`/`chunker` forem ligados ao pipeline (próxima OS) e puderem ser observados com um livro real.
- Detecção de sentença via regex `(?<=[.!?])\s+` (lookbehind de pontuação seguida de espaço) — cobre `.`/`!`/`?` conforme pedido no escopo ("só precisa lidar com pontuação comum"), sem tentar tratar abreviações (ex: "Dr.", "etc.") como não-fim-de-sentença — não foi pedido pela OS e adicionaria complexidade linguística fora do escopo declarado.

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

A preencher após abertura do PR na próxima etapa.
