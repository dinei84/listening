# OS-049 — Relatório de entrega

**Data:** 11/08/2026
**Branch:** `os/049-estrutura-do-documento`
**Commit(s) relevante(s):** `8b61826` (Red), `67468f8` (Green)

## 1. Resumo do que foi feito

`PyMuPDFExtractor.extract()` passou a usar `get_text("dict")` e a separar os blocos do PDF com linha em branco. Com isso, título de seção deixa de ser narrado como continuação da prosa, e a pausa de parágrafo entregue pela OS-045 — que até aqui **nunca disparava em PDF real** — passa a existir. O contrato `Extractor` não foi alterado.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `8b61826` com 3 falhas antes de `67468f8`
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou (307 → 313)
- [x] Contratos de `ARQUITETURA.md` respeitados — `Extractor` inalterado (ver seção 3 da OS)
- [x] Nenhuma chamada a API paga nos testes — extração é local
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-049-report.md`
- [x] PR aberto — https://github.com/dinei84/listening/pull/43

Específico (seção 4 da OS):

- [x] Título não concatenado com o parágrafo seguinte — `test_pymupdf_heading_is_not_glued_to_next_paragraph`
- [x] Blocos separados por linha em branco — `test_pymupdf_separates_blocks_with_blank_line`
- [x] `\n` simples dentro do bloco — `test_pymupdf_keeps_single_newline_inside_block`
- [x] Hifenização ainda recolada pelo `clean_text` — `test_pymupdf_hyphenated_word_still_joined_by_cleaner`
- [x] `chunk_text` produz fronteira de parágrafo em PDF real — verificado no livro: **0 → 68** no Prefácio
- [x] `confidence`, `source`, `page_number` e tipo de `text` inalterados — `test_pymupdf_extract_contract_unchanged`
- [x] Uma `ExtractedPage` por página — teste existente segue passando
- [x] `page_range` funcionando — teste existente segue passando
- [x] Nenhum teste existente quebra

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_pymupdf_separates_blocks_with_blank_line` | `tests/unit/extractors/test_pymupdf_extractor.py` | Sim |
| `test_pymupdf_heading_is_not_glued_to_next_paragraph` | idem | Sim |
| `test_pymupdf_keeps_single_newline_inside_block` | idem | Sim |
| `test_pymupdf_hyphenated_word_still_joined_by_cleaner` | idem | Sim |
| `test_chunker_produces_paragraph_from_extracted_pdf` | idem | Sim |
| `test_pymupdf_extract_contract_unchanged` | idem | Sim |

Fixture nova: `tests/fixtures/structured_layout_sample.pdf` — título em bloco próprio, parágrafo de duas linhas no **mesmo** bloco com palavra hifenizada partida entre elas, e segundo parágrafo à parte. A hifenização está lá de propósito: trava a compatibilidade com a OS-035.

Commit "Red" antes do "Green"? [x] Sim.

## 4. Saída de comandos relevantes

Medição que motivou a OS (página 13 do "Programador Pragmático"):

```
=== O QUE O PIPELINE VIA (get_text simples) ===
'PREFÁCIO xiii\ntraz com ele. Onde isso aconteceu...\nCÓDIGO-FONTE E OUTROS RECURSOS\nGrande parte do código...'

=== O QUE O PDF CARREGA (get_text("dict")) ===
TAM      NEGRITO  ITÁLICO      CHARS  EXEMPLO
9.7      -        -              940  traz com ele. Onde isso aconteceu, contribuímos para
14.0     -        -               62  CÓDIGO-FONTE E OUTROS RECURSOS
9.3      -        -                4  xiii
8.0      -        -               85  * N. de E.: Você também pode baixar os códigos em
8.0      sim      -               33  www.bookman.com.br
6.6      -        -                7  REFÁCIO
```

Blocos da mesma página (o PyMuPDF já segmentava; a informação era descartada):

```
bloco 0 | maior fonte 9.3 | P REFÁCIO   xiii
bloco 1 | maior fonte 9.7 | traz com ele. Onde isso aconteceu, contribuímos para o declínio
bloco 2 | maior fonte 20.0 | CÓDIGO-FONTE E OUTROS RECURSOS
bloco 3 | maior fonte 9.7 | Grande parte do código mostrado neste livro foi extraído de arqu
```

Verificação **depois**, no mesmo livro (Prefácio, capítulo índice 2):

```
Prefácio: 15699 chars, 17 chunks
fronteiras de parágrafo no texto: 68

=== o trecho do defeito, agora ===
'sso aconteceu, contribuímos para o declínio do idioma inventando nossos próprios
termos.\n\nCÓDIGO-FONTE E OUTROS RECURSOS\n\nGrande parte do código mostrado neste livro foi '
```

Antes eram **0** fronteiras de parágrafo no mesmo capítulo.

Suíte: `313 passed`. `ruff check`: `All checks passed!`

## 5. Desvios do escopo original

Nenhum. A OS previa não alterar o contrato `Extractor`, e não foi alterado.

Vale registrar uma decisão tomada durante a execução e já prevista na seção 3 da OS: a fixture precisou ser refeita. A primeira versão inseria cada linha do parágrafo com uma chamada `insert_text` separada, e o PyMuPDF as tratava como **blocos distintos** — o que não reproduz um PDF real, onde as linhas de um parágrafo compartilham o bloco. Refeita com `\n` na mesma chamada, ela passou a reproduzir o caso real e a testar de fato a regra do `\n` simples dentro do bloco.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Três continuações registradas no backlog, todas deliberadamente fora desta OS:

**Citação, itálico e nota de rodapé.** A mesma medição mostrou nota de rodapé a 8,0pt e URL em negrito a 8,0pt, distinguíveis do corpo a 9,7pt. Tratá-las exige **classificar** blocos por estilo, não só separá-los — outra responsabilidade, OS própria.

**Pausa diferenciada para título.** Hoje o título recebe a mesma pausa de parágrafo (800 ms) que qualquer outro bloco. Dar a ele uma pausa maior exigiria sinalizar o *tipo* do bloco até o Speaker, ou seja, sintaxe nova no texto ou campo novo no `ExtractedPage` — aí sim mexendo no contrato. Esta OS entregou a separação; a diferenciação precisa de um contrato para carregá-la.

**Cabeçalho corrente.** O bloco `"P REFÁCIO   xiii"` (9,3pt) continua sendo narrado. O `clean_text` remove linhas repetidas em duas ou mais páginas, mas essa carrega o número da página e varia a cada uma, escapando da regra. O tamanho de fonte seria um sinal mais forte — e cai na mesma OS de classificação por estilo.

## 7. Link do PR

https://github.com/dinei84/listening/pull/43
