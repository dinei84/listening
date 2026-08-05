# OS-036 — Corrige detecção de capítulos (nível do TOC, capítulo-monstro e páginas órfãs)

## 1. Objetivo

Achado em uso real com o "Arquitetura Limpa" (446 páginas) e confirmado no banco: a detecção de capítulos da OS-027 produziu uma estrutura inútil — três capítulos minúsculos e um absorvendo o livro inteiro. Esta OS corrige **três defeitos** da OS-027, sendo um deles perda silenciosa de conteúdo.

## 2. Contexto técnico medido (não repetir a investigação)

Estado real do livro no banco depois de processado pela OS-027:

```
CAPITULOS:
  ordem=0  paginas 18-23   'Prefácio'          ->   8 chunks
  ordem=1  paginas 24-28   'Apresentação'      ->   7 chunks
  ordem=2  paginas 29-31   'Agradecimentos'    ->   1 chunk
  ordem=3  paginas 32-446  'Sobre o Autor'     -> 320 chunks   <-- 415 páginas
```

O TOC desse PDF tem **263 entradas**, mas só **4 no nível 1** — e essas 4 são apenas a parte pré-textual. A estrutura real do livro está nos níveis 2 a 5:

```
[1, 'Prefácio', 18]      [1, 'Apresentação', 24]      [1, 'Agradecimentos', 29]
[1, 'Sobre o Autor', 32]
[2, 'I', 34]             <- partes reais
[3, 'Introdução', 34]
[4, '1', 36]             <- capítulos reais
[5, 'O que são Design e Arquitetura?', 36]
```

**Defeito 1 — "só nível 1" é heurística errada para TOC aninhado.** A OS-027 decidiu usar só o nível 1 ("ignorar sub-seções neste MVP"). Em livros cuja estrutura real está aninhada, isso devolve só o front matter.

**Defeito 2 — o último capítulo absorve todo o resto.** `detect_chapters()` define `end_page` do último como `total_pages`. Com o TOC cobrindo só o começo, "Sobre o Autor" (que tem 1–2 páginas de verdade) virou 415 páginas e 320 chunks. É isso que o dono do projeto viu na UI: chegou em "Capítulo 4 de 4" no trecho 18 de 559 e não havia mais granularidade nenhuma pelo resto do livro.

**Defeito 3 — páginas antes do primeiro item do TOC são descartadas, silenciosamente.** O primeiro capítulo começa na página 18; `extract_chapters()` só inclui páginas dentro de algum intervalo de capítulo, então **as páginas 1–17 nunca são sintetizadas**. Verificado que elas têm texto real (358, 1159, 853 e 125 caracteres nas páginas 1, 6, 11 e 17). Pode ser conteúdo dispensável (capa, ficha catalográfica) — mas hoje isso é acidente, não decisão.

## 3. Escopo

**Dentro do escopo:**

- **Escolha do nível do TOC (`core/pipeline.py::detect_chapters`)**: em vez de fixar nível 1, escolher o nível que dá a estrutura mais útil. Heurística sugerida (a implementação decide e documenta): percorrer os níveis do mais raso ao mais profundo e ficar com o primeiro que produza uma cobertura razoável do livro — por exemplo, aquele em que nenhum capítulo sozinho passe de uma fração grande do total de páginas, ou que produza pelo menos N capítulos. **Não** misturar níveis diferentes numa mesma lista.
- **Capítulo desproporcional**: se, mesmo após escolher o nível, algum capítulo cobrir uma fatia grande demais do livro (limiar a definir e documentar), subdividi-lo em blocos sintéticos, como o fallback sem TOC já faz — mantendo o título original com sufixo (ex: `"Sobre o Autor (parte 2)"`). Isso garante granularidade de navegação mesmo em TOC ruim.
- **Páginas órfãs antes do primeiro capítulo**: não descartar em silêncio. Decisão de implementação a documentar no relatório — as duas saídas aceitáveis são (a) criar um capítulo inicial cobrindo essas páginas (ex: `"Início"`), ou (b) estender o primeiro capítulo para começar na página 1. **Não** deixar como está.
- **Perfumaria pedida pelo dono do projeto:** o campo "Abrir livro existente" hoje recebe o `book_id` cru quando se clica num livro da lista (OS-033 seção 2.2). Passar a exibir o **título** ali, mantendo o `book_id` associado internamente (ex: `dataset`), e continuar aceitando um `book_id` digitado à mão — o campo não pode deixar de funcionar como entrada manual.

**Fora do escopo:**
- Hierarquia de capítulos na UI (partes → capítulos → seções aninhadas): esta OS continua entregando uma **lista plana**, só que do nível certo.
- Reprocessar automaticamente livros já processados — quem quiser a estrutura nova reenvia (mesmo padrão das OS-019/027/034).
- Junção de linhas e abreviações — é a OS-035.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Um PDF cujo TOC tenha só front matter no nível 1 e a estrutura real em nível mais profundo produz os capítulos **reais**, não os quatro do front matter
- [ ] Nenhum capítulo detectado cobre uma fração desproporcional do livro sem ser subdividido
- [ ] Páginas anteriores ao primeiro item do TOC **não** são descartadas — comportamento escolhido documentado no relatório
- [ ] PDF com TOC "bem-comportado" (todos os capítulos no nível 1) continua funcionando como na OS-027 — regressão
- [ ] PDF sem TOC continua caindo no fallback sintético — regressão
- [ ] `AudioChunk.sequence` continua global e contínua entre capítulos (restrição da OS-027, vale igual aqui)
- [ ] Clicar num livro da lista preenche o campo "Abrir livro existente" com o **título**; o campo continua aceitando um `book_id` digitado
- [ ] Nenhum teste das OS-027/028/029 quebra

## 5. Testes exigidos (mínimo)

- `test_detect_chapters_picks_deeper_toc_level_when_level_1_is_only_front_matter`
- `test_detect_chapters_subdivides_oversized_chapter`
- `test_detect_chapters_covers_pages_before_first_toc_entry`
- `test_detect_chapters_still_uses_level_1_when_it_covers_the_book` (regressão OS-027)
- `test_detect_chapters_still_falls_back_to_synthetic_without_toc` (regressão OS-027)
- `test_extract_chapters_loses_no_page_text`

Local sugerido: `tests/unit/test_chapters.py`. Os PDFs de teste são gerados com `fitz` + `doc.set_toc()`, como os da OS-027 — inclusive um caso com TOC aninhado imitando o "Arquitetura Limpa".

## 6. Verificação empírica exigida

Rodar `detect_chapters()` contra um PDF real com TOC aninhado (o "Arquitetura Limpa" ou equivalente) e colar no relatório a lista de capítulos resultante — mostrando que a estrutura real aparece e que nenhum capítulo engole o livro. Comparar com a saída atual (registrada na seção 2 desta OS).

## 7. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-036-report.md`.*
