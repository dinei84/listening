# OS-008 — processing/cleaner.py + processing/chunker.py

## 1. Objetivo

Implementar a limpeza de texto extraído (remover headers/footers repetidos, corrigir hifenização de quebra de linha) e a divisão em unidades de síntese (chunks por parágrafo/sentença, nunca por corte fixo de caracteres — regra já definida em `ARQUITETURA.md` seção 6, item 5). Sem isso, o pipeline da OS-007 manda o texto extraído inteiro numa única chamada ao Speaker, o que não escala para um livro de verdade.

## 2. Escopo

**Dentro do escopo:**
- `processing/cleaner.py` — uma função que recebe o texto **por página** (lista de strings, uma por página — não um blob já concatenado) e devolve um texto único limpo:
  - Remove linhas que se repetem em várias páginas (headers/footers) — comparar linha a linha entre páginas, não achismo de posição fixa (topo/rodapé pode variar de PDF pra PDF).
  - Corrige hifenização de quebra de linha (ex: uma linha termina em `-` e a próxima começa em minúscula → junta as duas partes sem o hífen e sem quebra de linha).
  - Preserva a estrutura de parágrafos — cleaner não é chunker, não deve colapsar tudo numa linha só.
  - Texto de entrada vazio (lista vazia ou só strings vazias) não deve quebrar, deve devolver string vazia.
- `processing/chunker.py` — uma função que recebe um texto já limpo e devolve uma lista de pedaços (`chunks`) prontos para virar `AudioChunk`:
  - Divide por parágrafo/sentença, respeitando um tamanho máximo configurável (parâmetro com valor padrão razoável, documentado e justificado no relatório — não precisa ser um número "oficial", mas precisa ter uma razão).
  - **Nunca corta uma sentença no meio** — se uma única sentença for maior que o tamanho máximo, ela vira um chunk sozinha mesmo excedendo o limite (documentar essa troca explicitamente: preferimos um chunk grande a cortar uma frase ao meio).
  - Texto vazio devolve lista vazia.
- Preferir biblioteca padrão (`re`) para divisão de sentenças — evitar adicionar uma dependência pesada de NLP (spaCy, NLTK) só para isso; mantém a filosofia de baixo custo/dependência do projeto (`HANDOFF.md` seção 2).

**Fora do escopo:**
- Ligar `cleaner`/`chunker` em `core/pipeline.py` — isso muda o comportamento público do pipeline (que hoje manda o texto inteiro numa única síntese) e merece OS própria depois que estas duas funções existirem e estiverem testadas isoladamente.
- Detecção de capítulos (`processing/chapter_detector.py`) — ainda não existe.
- Suporte a idiomas além de português/inglês na detecção de sentença — só precisa lidar com pontuação comum (`.`, `!`, `?`), não com regras linguísticas sofisticadas.

## 3. Contratos envolvidos

Nenhum contrato de interface formal (`cleaner`/`chunker` não são plugins — são lógica de negócio fixa, não trocável, conforme a regra de "o que é plugin" em `ARQUITETURA.md` seção 1). A única regra vinculante é `ARQUITETURA.md` seção 6, item 5: "Chunking deve ser por parágrafo/sentença, nunca por corte fixo de caracteres."

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `cleaner` remove uma linha que se repete em pelo menos duas páginas de um texto de fixture conhecido (assert no resultado exato, conforme `TDD.md` seção 4)
- [ ] `cleaner` corrige pelo menos um caso de hifenização de quebra de linha
- [ ] `cleaner` preserva quebras de parágrafo que não são header/footer/hifenização
- [ ] `cleaner` com entrada vazia devolve string vazia, sem erro
- [ ] `chunker` nunca corta uma sentença no meio — testar com texto de tamanho conhecido e verificar os limites exatos dos chunks (conforme `TDD.md` seção 4)
- [ ] `chunker` respeita o tamanho máximo configurável quando possível (quando não há sentença isolada maior que o limite)
- [ ] `chunker` com uma única sentença maior que o limite devolve essa sentença inteira como um chunk (não corta, mesmo excedendo o tamanho máximo)
- [ ] `chunker` com entrada vazia devolve lista vazia, sem erro
- [ ] Nenhuma dependência nova pesada de NLP adicionada a `requirements.txt` sem justificar por que `re`/stdlib não bastou

## 5. Testes exigidos (mínimo)

- `test_clean_text_removes_repeated_header_across_pages`
- `test_clean_text_removes_repeated_footer_across_pages`
- `test_clean_text_fixes_hyphenation_across_line_break`
- `test_clean_text_preserves_paragraph_breaks`
- `test_clean_text_handles_empty_input`
- `test_chunk_text_never_splits_a_sentence`
- `test_chunk_text_respects_max_chars_when_possible`
- `test_chunk_text_keeps_oversized_single_sentence_as_one_chunk`
- `test_chunk_text_handles_empty_input`

Local sugerido: `tests/unit/processing/test_cleaner.py` e `tests/unit/processing/test_chunker.py` (diretório já existe).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-008-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
