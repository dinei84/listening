# OS-035 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/035-juntar-linhas-quebradas
**Commit(s) relevante(s):** 8566f85 (test: Red), 22ed440 (feat: Green)

## 1. Resumo do que foi feito

`processing/cleaner.py` ganhou `_join_wrapped_lines()`, que une linhas consecutivas quando a anterior **não** termina em `.`/`!`/`?`/`:`/`;`/aspas/`)` — desfazendo a quebra de diagramação do PDF e preservando linha em branco como fronteira de parágrafo. Roda **depois** da correção de hifenização. `processing/chunker.py` passou a não tratar como fim de sentença o ponto de abreviações comuns (`Dr.`, `pág.`, `etc.`...) nem de inicial de nome (`Robert C. Martin`). Medido com o G2P real: um parágrafo que virava **5 segmentos de síntese passou a virar 1**, sem perda de palavras.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `8566f85` "Red" antes de `22ed440` "Green")
- [x] Todos os testes da OS passam localmente — 210 pass, 0 fail
- [x] Nenhum teste existente quebrou (200 anteriores + 10 novos = 210)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato tocado; `clean_text()` e `chunk_text()` mantêm assinatura e semântica pública
- [x] Nenhuma chamada real a API paga dentro dos testes
- [x] Type hints e docstring de uma linha em toda função nova
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-035-report.md`
- [x] PR aberto contra o branch principal

### DoD específico da OS (seção 4)

- [x] Linhas que continuam a mesma frase são unidas, com espaço — `test_clean_text_joins_lines_that_continue_a_sentence`
- [x] Fronteira de parágrafo não é unida — `test_clean_text_preserves_paragraph_boundaries_when_joining` e o teste pré-existente `test_clean_text_preserves_paragraph_breaks`
- [x] Hifenização continua funcionando; palavra partida não vira duas — `test_clean_text_join_runs_after_hyphenation_fix` e o pré-existente `test_clean_text_fixes_hyphenation_across_line_break`
- [x] Parágrafo que virava N segmentos passa a virar 1 — medido, seção 4: **5 → 1**
- [x] Abreviações não criam falsa fronteira — `test_chunk_text_does_not_split_on_common_abbreviations`, `..._page_abbreviation`, `..._name_initial`
- [x] Nenhum teste das OS-008/009/021/022/024/027/034 quebra — suíte inteira verde
- [x] Nenhuma chamada de rede ou API paga na suíte

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_clean_text_joins_lines_that_continue_a_sentence` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_preserves_paragraph_boundaries_when_joining` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_keeps_break_after_sentence_end` (extra) | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_join_runs_after_hyphenation_fix` | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_joins_sentence_split_across_pages` (extra) | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_clean_text_does_not_join_after_colon_or_semicolon` (extra) | `tests/unit/processing/test_cleaner.py` | Sim |
| `test_chunk_text_does_not_split_on_common_abbreviations` | `tests/unit/processing/test_chunker.py` | Sim |
| `test_chunk_text_does_not_split_on_page_abbreviation` (extra) | `tests/unit/processing/test_chunker.py` | Sim |
| `test_chunk_text_does_not_split_on_name_initial` | `tests/unit/processing/test_chunker.py` | Sim |
| `test_chunk_text_still_splits_on_real_sentence_end` (regressão) | `tests/unit/processing/test_chunker.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `8566f85` (7 falhas: linhas não unidas, hifenização+junção, junção entre páginas, e três de abreviação) antes de `22ed440`.

## 4. Saída de comandos relevantes

Rodada Red:
```
7 failed, 13 passed in 0.06s   (tests/unit/processing/)
```

Suíte completa após a implementação (Green):
```
$ venv/bin/python -m pytest -q
210 passed, 1 warning in 11.20s
```

```
$ venv/bin/ruff check core/ storage/ worker/ api/ processing/ tests/
All checks passed!
$ venv/bin/black --check core/ storage/ worker/ api/ processing/ tests/
49 files would be left unchanged.
```

### Verificação empírica com o G2P real (exigida pela seção 6 da OS)

PDF gerado com `fitz` (parágrafo real diagramado em coluna estreita, como um livro), extraído pelo `PyMuPDFExtractor` real e medido com `kokoro.KPipeline(lang_code='p', model=False)` — só o G2P, sem baixar o modelo pesado:

```
quebras de linha ANTES da limpeza: 5
quebras de linha DEPOIS (OS-035):  0

chunk 0: 1 segmento(s) de sintese
   'A engenharia de seguranca trata de construir sistemas que permanecam c'

palavras antes=45  depois=45  ->  integridade: True
```

**Antes desta OS o mesmo parágrafo produzia 5 segmentos** (medido na investigação que originou a OS, registrado na seção 2 dela) — cada fronteira de segmento é uma pausa audível no meio da frase. A contagem de palavras idêntica antes/depois prova que a junção não perdeu nem duplicou texto.

## 5. Decisões de implementação documentadas

**(a) Quais terminações mantêm a quebra.** `_LINE_ENDINGS_THAT_KEEP_BREAK = (".", "!", "?", ":", ";", '"', "”", "»", ")")`. Além do fim de frase óbvio, `:` e `;` foram incluídos porque marcam pausa intencional (listas, enumerações) — unir ali atropelaria a prosódia. Aspas de fechamento e `)` também encerram unidade de leitura. Coberto por `test_clean_text_does_not_join_after_colon_or_semicolon`.

**(b) A junção roda depois de `_fix_hyphenation()`.** Ordem invertida quebraria a palavra partida: `"demons-"` + `"tracao"` viraria `"demons- tracao"` (com espaço) em vez de `"demonstracao"`. Coberto por `test_clean_text_join_runs_after_hyphenation_fix`.

**(c) Frase que atravessa páginas também é unida.** `clean_text()` recebe todas as páginas do capítulo e junta as linhas depois de concatená-las, então uma frase interrompida pela quebra de página é remendada naturalmente. Coberto por `test_clean_text_joins_sentence_split_across_pages`.

**(d) Abreviações: lista local em vez de spaCy/NLTK.** `_ABBREVIATIONS` tem ~38 entradas PT/EN, mais duas regras genéricas: palavra de **uma letra** antes do ponto (inicial de nome, `Robert C. Martin`) e numeração. A OS já vetava spaCy/NLTK (modelo de ~50MB + segunda toolchain, contra as decisões #12/#13) — a lista resolve os casos frequentes com custo zero. **Limitação conhecida e aceita:** uma abreviação fora da lista continua criando falsa fronteira; o efeito é uma pausa a mais, não perda de conteúdo.

**(e) `_split_sentences()` remenda em vez de complicar o regex.** Em vez de um regex único com lookbehind negativo para cada abreviação (ilegível e frágil), o texto é dividido como antes e as fronteiras falsas são costuradas de volta. Mais fácil de ler e de estender.

## 6. Desvios do escopo original

Nenhum. Os arquivos tocados são exatamente `processing/cleaner.py` e `processing/chunker.py`, mais os testes, como a seção 3 da OS previa.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Duas observações para o dono do projeto:

1. **Livros já processados não se beneficiam automaticamente.** O áudio deles foi gerado com as pausas artificiais; só reenviando. Mesmo padrão já registrado nas OS-019/027/034 — vale acrescentar ao aviso do `RUNBOOK.md` se você quiser reprocessar em lote.
2. **Esta OS não toca no sotaque do português.** Ela remove as pausas artificiais (o "picotado"), que era o sintoma dominante; a pronúncia aproximada do espeak-ng continua sendo o risco aberto na seção 6 do `PROJECT_STATE.md`, endereçado parcialmente pela OS-037.

## 8. Link do PR

*A preencher após abrir o PR.*
