# OS-036 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/036-corrige-deteccao-capitulos
**Commit(s) relevante(s):** 76d1809 (test: Red), ee65f02 (feat: Green)

## 1. Resumo do que foi feito

`detect_chapters()` deixou de fixar o nível 1 do TOC: agora escolhe **o nível mais raso cujo maior capítulo caiba em `MAX_CHAPTER_FRACTION` (25%) do livro**, prefere o **título descritivo** quando número e nome estão em níveis diferentes na mesma página, **subdivide** capítulos que ainda fiquem desproporcionais, e **cobre as páginas anteriores ao primeiro item do TOC** — que antes eram descartadas em silêncio. O campo "Abrir livro existente" passou a exibir o título do livro, guardando o `book_id` no `dataset` e continuando a aceitar um id digitado.

Medido no PDF real que originou a OS ("Arquitetura Limpa", 446 páginas): **4 → 35 capítulos**, maior capítulo de **415 páginas (93%) → 76 páginas (17%)**, cobertura a partir da **página 1** (antes começava na 18).

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `76d1809` "Red" antes de `ee65f02` "Green")
- [x] Todos os testes da OS passam localmente — 207 pass, 0 fail
- [x] Nenhum teste existente quebrou (200 anteriores + 7 novos = 207)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato tocado; `Chapter` já tinha `start_page`/`end_page` desde a OS-027
- [x] Nenhuma chamada real a API paga dentro dos testes
- [x] Type hints e docstring de uma linha em toda função nova
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-036-report.md`
- [x] PR aberto contra o branch principal

### DoD específico da OS (seção 4)

- [x] TOC com front matter no nível 1 e estrutura real mais abaixo produz os capítulos **reais** — `test_detect_chapters_picks_deeper_toc_level_when_level_1_is_only_front_matter`, confirmado no PDF real (seção 4)
- [x] Nenhum capítulo cobre fração desproporcional sem ser subdividido — `test_detect_chapters_subdivides_oversized_chapter`; no PDF real o maior caiu para 17%
- [x] Páginas anteriores ao primeiro item do TOC não são descartadas — `test_detect_chapters_covers_pages_before_first_toc_entry` e `test_extract_chapters_loses_no_page_text`; escolha documentada em (c)
- [x] TOC bem-comportado continua funcionando como na OS-027 — `test_detect_chapters_still_uses_level_1_when_it_covers_the_book` e os testes originais da OS-027 intactos
- [x] PDF sem TOC continua no fallback sintético — `test_detect_chapters_still_falls_back_to_synthetic_without_toc`
- [x] `AudioChunk.sequence` continua global e contínua — testes da OS-027 (`test_worker_process_job_keeps_sequence_global_across_chapters`) seguem verdes
- [x] Campo "Abrir livro existente" mostra o título e continua aceitando `book_id` digitado
- [x] Nenhum teste das OS-027/028/029 quebra

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_detect_chapters_picks_deeper_toc_level_when_level_1_is_only_front_matter` | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_subdivides_oversized_chapter` | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_covers_pages_before_first_toc_entry` | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_still_uses_level_1_when_it_covers_the_book` (regressão) | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_still_falls_back_to_synthetic_without_toc` (regressão) | `tests/unit/test_chapters.py` | Sim |
| `test_detect_chapters_prefers_descriptive_title_on_same_page` (extra) | `tests/unit/test_chapters.py` | Sim |
| `test_extract_chapters_loses_no_page_text` | `tests/unit/test_chapters.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `76d1809` (5 falhas) antes de `ee65f02`. As duas regressões da OS-027 já passavam no Red, como esperado.

**Uma asserção de teste foi ajustada durante o Green**, e vale registrar por transparência: `..._picks_deeper_toc_level...` exigia o título exato `"Capitulo Um"` na lista, mas a implementação (corretamente) subdividiu esse capítulo em `"Capitulo Um (parte 1)"` e `"(parte 2)"` — ele cobria 23 páginas contra um limite de 22. A asserção passou a checar substring, sem afrouxar o que o teste prova (a estrutura real do nível 2 tem de aparecer, e nenhum capítulo pode engolir o livro).

## 4. Saída de comandos relevantes

Rodada Red:
```
5 failed, 9 passed in 5.10s   (tests/unit/test_chapters.py)
```

Suíte completa (Green):
```
$ venv/bin/python -m pytest -q
207 passed, 1 warning in 9.27s

$ venv/bin/ruff check core/ storage/ worker/ api/ processing/ tests/
All checks passed!
$ venv/bin/black --check core/ storage/ worker/ api/ processing/ tests/
49 files would be left unchanged.
$ node --check player/app.js
(sem erros)
```

### Verificação com o PDF real (exigida pela seção 6 da OS)

Mesmo arquivo que originou a OS — "Arquitetura Limpa", 446 páginas, 263 entradas de TOC em 8 níveis:

```
capitulos detectados: 35
primeira pagina coberta: 1   ultima: 446
maior capitulo: 76 paginas (17% do livro)

  ordem= 0  pag   1- 46  'O Objetivo?'
  ordem= 1  pag  47- 56  'Um Conto de Dois Valores'
  ordem= 2  pag  57- 60  'Panorama do Paradigma'
  ordem= 3  pag  61- 69  'Programação Estruturada'
  ordem= 4  pag  70- 86  'Programação Orientada a Objetos'
  ordem= 5  pag  87-100  'Programação Funcional'
  ordem= 6  pag 101-107  'SRP: O Princípio da Responsabilidade Única'
  ordem= 7  pag 108-114  'OCP: O Princípio Aberto/Fechado'
  ordem= 8  pag 115-120  'LSP: O Princípio de Substituição de Liskov'
  ordem= 9  pag 121-124  'ISP: O Princípio da Segregação de Interface'
  ordem=10  pag 125-132  'DIP: O Princípio da Inversão de Dependência'
  ordem=11  pag 133-141  'Componentes'
  ... (+23 capitulos)
```

Comparado com o estado anterior (registrado na seção 2 da OS):

| | Antes (OS-027) | Agora (OS-036) |
|---|---|---|
| Capítulos | 4 | **35** |
| Maior capítulo | 415 pág (93%) | **76 pág (17%)** |
| Primeira página coberta | 18 (1–17 perdidas) | **1** |
| Títulos | Prefácio, Apresentação, Agradecimentos, Sobre o Autor | os capítulos reais do livro |

Note que `'SRP: O Princípio da Responsabilidade Única'` aparece em vez de `'6'` — é o efeito da preferência por título descritivo (decisão (b) abaixo).

## 5. Decisões de implementação documentadas

**(a) Escolha do nível: o mais raso que couber no limite.** `_toc_milestones()` avalia cada nível do TOC, calcula qual seria o maior capítulo dele como fração do livro, e fica com **o mais raso cuja fração seja ≤ `MAX_CHAPTER_FRACTION` (0.25)**. Se nenhum nível couber, fica com o mais equilibrado (menor "maior capítulo") e a subdivisão de (d) resolve o resto. Medição que motivou o valor, no PDF real: nível 1 → 93%, nível 3 → 33%, nível 6 → 17%. Preferir o mais raso mantém os títulos mais próximos de "capítulo" e evita descer para seções minúsculas.

**(b) Melhor título por página, olhando todos os níveis.** Livros costumam pôr o número num nível e o nome em outro, **na mesma página** (`[4, '1', 36]` e `[5, 'O que são Design e Arquitetura?', 36]`). `_is_descriptive()` rejeita títulos que são só número ou algarismo romano, e o mapa `melhor_titulo` prefere o descritivo. Sem isso metade dos capítulos do PDF real se chamaria "3", "7", "12".

**(c) Páginas órfãs: estender o primeiro capítulo até a página 1.** A OS deixava duas saídas aceitáveis; escolhida a de **estender** em vez de criar um capítulo "Início" — evita poluir a lista de navegação com uma entrada artificial de capa/ficha catalográfica, e garante que o texto entra na síntese. No PDF real isso recuperou as páginas 1–17, que têm texto (medido: 358, 1159, 853 e 125 caracteres nas páginas 1, 6, 11 e 17) e antes nunca eram sintetizadas.

**(d) Subdivisão mantém o título com sufixo `(parte N)`.** Um capítulo acima do limite vira blocos de no máximo `max(SYNTHETIC_CHAPTER_PAGES, 25% do livro)` páginas. Preservar o título original mantém a navegação legível ("Corpo (parte 1)", "(parte 2)").

**(e) Campo "Abrir livro existente": título visível, id no `dataset`.** Clicar num livro grava `bookIdInput.value = book.title` e `dataset.bookId`/`dataset.bookTitle`. No submit, se o texto ainda for exatamente o título guardado, usa o id; se o usuário digitou ou alterou, trata o conteúdo como `book_id`. O campo não perdeu a função de entrada manual.

## 6. Desvios do escopo original

Nenhum. Arquivos tocados: `core/pipeline.py`, `player/app.js` e os testes — exatamente o previsto na seção 3 da OS.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Três observações para o dono do projeto:

1. **Livros já processados mantêm a estrutura antiga.** O "Arquitetura Limpa" que está no banco continua com os 4 capítulos ruins e sem as páginas 1–17 até ser reenviado. Não há reprocessamento automático (mesmo padrão das OS-019/027/034/035).
2. **`MAX_CHAPTER_FRACTION = 0.25` é um padrão razoável, não um número validado empiricamente.** Foi escolhido a partir da distribuição medida num único livro. Se algum PDF real produzir uma estrutura estranha, é o primeiro botão a girar.
3. **TOC malformado ainda limita a qualidade dos títulos.** O PDF do "Arquitetura Limpa" alterna títulos reais e números soltos entre níveis; a heurística de (b) recupera a maioria, mas um TOC suficientemente bagunçado pode gerar títulos pobres em alguns capítulos. A navegação (o problema relatado) fica correta de qualquer forma.

## 8. Link do PR

https://github.com/dinei84/listening/pull/32
