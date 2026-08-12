# OS-050 — Relatório de entrega

**Data:** 11/08/2026
**Branch:** `os/050-classificacao-por-estilo`
**Commit(s) relevante(s):** `e1e8798` (Red), `780508b` (Green)

## 1. Resumo do que foi feito

O `PyMuPDFExtractor` passou a classificar blocos por estilo e posição, descartando o que não é texto do autor: cabeçalho corrente, número de página solto e nota de rodapé. Título e citação são preservados. Nenhum contrato foi alterado — a classificação age na extração, e o que sobra continua sendo `text: str`.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `e1e8798` com 3 falhas antes de `780508b`
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou (313 → 321)
- [x] Contratos de `ARQUITETURA.md` respeitados — `Extractor` inalterado, por decisão do dono
- [x] Nenhuma chamada a API paga nos testes — extração é local
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-050-report.md`
- [x] PR aberto — https://github.com/dinei84/listening/pull/46

Específico (seção 5 da OS):

- [x] Cabeçalho corrente não narrado — verificado no Capítulo 1 real
- [x] Número de página isolado não narrado — cai na mesma regra de bloco miúdo
- [x] Nota de rodapé não narrada — verificado no Capítulo 1 real
- [x] Título continua narrado — verificado
- [x] Citação continua narrada — verificado
- [x] Página cujo primeiro bloco é conteúdo real não perde o bloco — `test_pymupdf_keeps_first_block_when_it_is_real_content`
- [x] Corpo medido do documento, não fixo — `test_pymupdf_body_size_is_measured_per_document`
- [x] Contrato `Extractor` inalterado — `test_pymupdf_extract_contract_unchanged` segue passando
- [x] Nenhum teste existente quebra

## 3. Testes escritos

| Teste | Passou? |
|---|---|
| `test_pymupdf_drops_running_header` | Sim |
| `test_pymupdf_drops_footnote_block` | Sim |
| `test_pymupdf_keeps_heading_block` | Sim |
| `test_pymupdf_keeps_italic_quote_block` | Sim |
| `test_pymupdf_keeps_body_block` | Sim |
| `test_pymupdf_keeps_first_block_when_it_is_real_content` | Sim |
| `test_pymupdf_body_size_is_measured_per_document` | Sim |
| `test_pymupdf_style_classification_does_not_break_os049_blocks` | Sim |

Todos em `tests/unit/extractors/test_pymupdf_extractor.py`. Fixture nova: `tests/fixtures/styled_blocks_sample.pdf`, com cabeçalho corrente, título, corpo, citação em itálico, nota de rodapé, e — de propósito — uma segunda página cujo primeiro bloco é **conteúdo real no topo**, para cobrir o risco declarado na OS.

Commit "Red" antes do "Green"? [x] Sim.

## 4. Saída de comandos relevantes

Medição que definiu os limiares (70 páginas do miolo, corpo = 9,7pt por moda de caractere):

```
CLASSE              BLOCOS  EXEMPLO
corpo                  593  ...
ITALICO>=80%            58  A maior de todas as fraquezas é o medo de parecer fraco.
TITULO (>=1,35x)        56  Uma Filosofia Pragmática
italico parcial         55  J. B. Bossuet,  A Política Tirada da Sagrada Escritura , 1709
MIUDO (<=0,85x)         52  1  Ao fazer isso, console-se com a frase atribuída à contra-al
```

Posição do cabeçalho corrente (10 páginas consecutivas):

```
PAG   TOPO_y  ALTURA  CHARS  PRIMEIRO BLOCO
24    53.9    708.7   50     C APÍTULO  1    U MA  F ILOSOFIA  P RAGMÁTICA   25
25    53.9    708.7   31     26  O P ROGRAMADOR  P RAGMÁTICO
26    53.9    708.7   50     C APÍTULO  1    U MA  F ILOSOFIA  P RAGMÁTICA   27
```

Verificação **depois**, no Capítulo 1 do mesmo livro (43.450 chars):

```
  cabeçalho corrente           REMOVIDO
  nota de rodapé               REMOVIDO
  título (deve permanecer)     presente
  citação (deve permanecer)    presente
```

Suíte: `321 passed`. `ruff check`: limpo.

## 5. Desvios do escopo original

**Uma condição a mais na regra do cabeçalho corrente, encontrada em execução.** A OS previa duas condições — posição no topo e bloco curto. Elas não bastavam: o **teste de regressão da OS-049 falhou**, porque um TÍTULO de seção no topo de uma página é tão curto quanto um cabeçalho corrente, e estava sendo descartado.

O discriminador que faltava é tipográfico: **cabeçalho corrente nunca é maior que o corpo** (medido: 9,3pt contra 9,7pt), enquanto título é (20,0pt). A regra passou a exigir três condições.

Vale registrar como isso foi pego: não por revisão nem por medição nova, mas por um teste escrito numa OS anterior, sobre uma fixture que existia por outro motivo. É o argumento concreto a favor da fixture da OS-049 ter sido feita com título em bloco próprio.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Duas continuações, ambas já previstas na OS:

**Entrega diferenciada para título e citação.** Continua fora. Hoje o título recebe os mesmos 800 ms de qualquer bloco e a citação não tem registro próprio — eles apenas param de vir grudados. A decisão do dono foi condicionar isso a evidência de escuta: se ainda incomodar depois desta OS, aí se avalia estender o contrato para carregar o tipo do bloco.

**Limiares fixos em constantes.** `SMALL_BLOCK_RATIO`, `HEADING_RATIO`, `HEADER_BAND` e `HEADER_MAX_CHARS` foram calibrados sobre **um** livro. São relativos ao corpo de cada documento, o que os torna portáveis entre PDFs de diagramação diferente, mas não foram validados em outro livro. Um PDF com cabeçalho corrente longo (acima de 80 caracteres) ou com corpo em dois tamanhos alternados escaparia. Risco aceito e registrado; a correção, se aparecer, é calibrar as constantes, não mudar a estrutura.

## 7. Link do PR

https://github.com/dinei84/listening/pull/46
