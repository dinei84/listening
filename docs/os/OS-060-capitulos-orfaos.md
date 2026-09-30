# OS-060 — `delete_book` deixa capítulos órfãos

## 1. Objetivo

Fazer `DELETE /books/{id}` cumprir o que a docstring dele promete — remover
"todo o seu rastro" — e limpar o lixo que a falha já acumulou.

Item 58 do backlog, achado em 13/08/2026.

## 2. Escopo

### O problema, medido

`storage/db.py::delete_book` executa **só** `DELETE FROM books`. A rota limpa
`audio_chunks`, `reading_progress`, `jobs` e o PDF — mas **não** `chapters`.

A tabela `chapters` entrou na OS-027 e o caminho de delete nunca foi atualizado.
Não há foreign key nem `ON DELETE CASCADE` no schema (`PRAGMA foreign_keys` é 0),
então nada segura isso por baixo.

Medido no banco local em 29/09/2026: **94 de 95 linhas em `chapters` são órfãs**,
para **1 livro existente**. Em 13/08/2026 eram 89 de 90 — cresceu com o uso, como
o item previa.

Sem impacto funcional conhecido (ninguém lê capítulo por `book_id` inexistente),
mas polui qualquer diagnóstico feito no banco — foi o que atrapalhou a leitura do
estado durante a investigação que originou o item.

### Alterados

- `storage/db.py` — `delete_book` remove também os capítulos; varredura de órfãos
  já acumulados no `init_db`.
- Testes correspondentes.

### Fora de escopo

- **Ligar `PRAGMA foreign_keys` e declarar as FKs.** Resolveria a classe inteira,
  mas muda o comportamento de **toda** escrita do projeto e exigiria revisar cada
  caminho de insert e delete. É OS própria, com risco próprio.
- **Órfãos em outras tabelas.** `audio_chunks`, `reading_progress` e `jobs` já são
  limpos pela rota; a varredura desta OS cobre só `chapters`, que é a falha
  conhecida. Ampliar sem medir seria inventar problema.

## 3. Contratos envolvidos

Nenhum contrato muda. `delete_book` mantém assinatura e semântica ("nenhum efeito
se o book_id não existir").

A varredura no `init_db` **apaga linhas**, e por isso é restrita ao que é
provavelmente seguro: só linhas de `chapters` cujo `book_id` não existe em
`books` — por definição inalcançáveis, já que todo consumidor busca capítulo por
`book_id`. A quantidade removida é registrada em log, não em silêncio.

## 4. Critérios de aceite

- [ ] `delete_book` remove os capítulos do livro apagado
- [ ] `delete_book` não toca nos capítulos de outros livros
- [ ] `delete_book` de um `book_id` inexistente continua sem efeito
- [ ] `DELETE /books/{id}` pela rota não deixa capítulo para trás
- [ ] `init_db` remove capítulos órfãos já existentes
- [ ] A varredura **não** remove capítulos de livros que existem
- [ ] A varredura é idempotente e registra em log quantas linhas removeu
- [ ] `init_db` em banco sem a tabela `chapters` não quebra
- [ ] Nenhum teste existente quebra (478 hoje)

## 5. Testes exigidos (mínimo)

- `test_delete_book_removes_its_chapters`
- `test_delete_book_keeps_other_books_chapters`
- `test_delete_unknown_book_is_noop`
- `test_delete_route_leaves_no_orphan_chapters`
- `test_init_db_sweeps_orphan_chapters`
- `test_init_db_sweep_keeps_chapters_of_existing_books`
- `test_init_db_sweep_is_idempotent`

## 6. Relatório

Ver `docs/report/OS-060-report.md`.
