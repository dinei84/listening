# OS-049 — Estrutura do documento na extração

## 1. Objetivo

Fazer a fronteira de bloco do PDF sobreviver até o Speaker, para que título de seção deixe de ser narrado como continuação da prosa e a pausa de parágrafo da OS-045 — hoje inerte — passe a existir.

## 2. Escopo

Alterados:

- `plugins/extractors/pymupdf_extractor.py` — `extract()` passa a usar `get_text("dict")` e a separar blocos.
- `tests/unit/extractors/test_pymupdf_extractor.py` e uma fixture nova.

Fora de escopo (declarado):

- **O contrato `Extractor` NÃO muda.** `extract()` continua devolvendo `list[ExtractedPage]` com `text: str`. Medido que o PyMuPDF já segmenta título em bloco próprio, então a estrutura cabe no texto simples como linha em branco — sem campo novo, sem quebrar `TesseractOCR` nem `EasyOCRExtractor`.
- **Citação, itálico e nota de rodapé.** Foram observados na mesma medição (rodapé a 8,0pt, URL em negrito) e exigem classificação por estilo, não só separação de bloco. É outra responsabilidade — OS própria, conforme `AGENTS.md` seção 3.
- **Pausa diferenciada para título.** Dar ao título uma pausa maior que a de parágrafo exigiria sinalizar o tipo do bloco até o Speaker, ou seja, sintaxe nova no texto. Esta OS entrega a separação; a diferenciação fica para quando houver contrato para carregá-la.
- `processing/cleaner.py` e `chunker.py` — não são tocados. A OS-045 já converte linha em branco em pausa de parágrafo, e a OS-035 já preserva linha em branco ao juntar linhas quebradas. Esta OS só passa a **alimentar** o que já existe.

## 3. Contratos envolvidos

Nenhum contrato de interface é alterado — o ponto central desta OS. `ARQUITETURA.md`, seção do `Extractor`: assinatura e tipo de retorno preservados.

A mudança é de **conteúdo** do `ExtractedPage.text`: onde antes vinha o resultado de `get_text()`, agora vêm os mesmos blocos com linha em branco entre eles.

Ordem interna que é contrato desta OS: **linhas dentro de um bloco continuam separadas por `\n` simples**, e só entre blocos entra a linha em branco. Sem isso, `_fix_hyphenation` (OS-035) quebraria: ela procura linha terminada em `-` para recolar palavra partida, e juntar as linhas do bloco com espaço apagaria essa fronteira, transformando "demons-\ntração" em "demons- tração".

## 4. Critérios de aceite

- [ ] Título de seção não é concatenado com o parágrafo seguinte
- [ ] Blocos distintos do PDF ficam separados por linha em branco no `ExtractedPage.text`
- [ ] Linhas dentro do mesmo bloco continuam separadas por `\n` simples (compatibilidade com a OS-035)
- [ ] Palavra hifenizada partida entre linhas continua sendo recolada pelo `clean_text`
- [ ] `chunk_text` passa a produzir a fronteira de parágrafo em PDF real (hoje: nenhuma)
- [ ] `confidence` e `source` do `ExtractedPage` inalterados
- [ ] Uma `ExtractedPage` por página do PDF, como antes
- [ ] `page_range` continua funcionando
- [ ] Nenhum teste existente quebra (307 hoje)

## 5. Testes exigidos (mínimo)

- `test_pymupdf_separates_blocks_with_blank_line`
- `test_pymupdf_keeps_single_newline_inside_block`
- `test_pymupdf_heading_is_not_glued_to_next_paragraph`
- `test_pymupdf_hyphenated_word_still_joined_by_cleaner`
- `test_pymupdf_extract_contract_unchanged`
- `test_chunker_produces_paragraph_from_extracted_pdf`

## 6. Relatório

Ver `docs/report/OS-049-report.md`.
