# OS-060 — Relatório de entrega

**Data:** 29/09/2026
**Branch:** `os/060-capitulos-orfaos`
**Commit(s) relevante(s):** `5419f2e` (OS), `8e436fa` (Red), `38bfda0` (Green)

## 1. Resumo do que foi feito

`delete_book` passou a remover os capítulos do livro apagado, e o `init_db` varre
os capítulos órfãos que a falha já tinha acumulado. Item 58 do backlog.

## 2. Checklist de DoD

### Padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit Red precede o Green
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 478 → **488 passando**
- [x] Código segue os contratos de `ARQUITETURA.md` — nenhum contrato alterado
- [x] Nenhuma chamada real a API paga nos testes — esta OS só toca SQLite
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-060-report.md`
- [x] PR aberto com título `[OS-060] ...`

### Específico (seção 4 da OS)

- [x] `delete_book` remove os capítulos do livro apagado
- [x] `delete_book` não toca nos capítulos de outros livros
- [x] `delete_book` de um `book_id` inexistente continua sem efeito
- [x] `DELETE /books/{id}` pela rota não deixa capítulo para trás
- [x] `init_db` remove capítulos órfãos já existentes
- [x] A varredura **não** remove capítulos de livros que existem
- [x] A varredura é idempotente e registra em log quantas linhas removeu
- [x] `init_db` em banco sem a tabela `chapters` não quebra
- [x] Nenhum teste existente quebra

## 3. Testes escritos

10 novos.

| Teste | Arquivo | Passou? |
|---|---|---|
| `delete_book` remove os capítulos dele | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| `delete_book` preserva capítulos de outro livro | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| `delete_book` de id inexistente é no-op | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| varredura remove 94 órfãos e preserva o vivo | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| varredura preserva capítulos de livros existentes | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| varredura é idempotente | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| varredura registra quantas removeu / cala quando não há nada | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| `init_db` em banco novo não quebra | `tests/unit/test_orphan_chapters_os060.py` | ✅ |
| rota `DELETE` não deixa órfão | `tests/integration/test_delete_orphans_os060.py` | ✅ |

Commit "Red" antes do "Green"? **[x] Sim** — 6 falhas antes da correção.

## 4. Saída de comandos relevantes

### Suíte completa e lint

```
488 passed, 2 warnings in 14.48s
All checks passed!     (storage/ tests/)
```

### Varredura executada contra o banco real

Cópia de segurança do `books.db` feita antes, no scratchpad da sessão.

```
INFO storage.db: Removidos 94 capítulo(s) órfão(s) de livros já apagados (OS-060)
ANTES:  95 capitulos, 94 orfaos, 1 de livros existentes
DEPOIS: 1 capitulos, 1 de livros existentes, 1 livro(s) intacto(s)
```

Confirma os dois lados: o lixo saiu inteiro e o que pertence ao livro existente
ficou. Em 13/08/2026 o item registrava 89 de 90 órfãs — o crescimento previsto
aconteceu.

## 5. Desvios do escopo original

Nenhum. Os únicos arquivos de produção tocados são os declarados na seção 2 da
OS (`storage/db.py`), mais os testes.

Uma decisão tomada dentro do escopo: a varredura ficou no `init_db` em vez de um
script de migração avulso, para o banco de qualquer máquina se limpar sozinho ao
subir a API ou o worker, sem exigir que alguém lembre de rodar algo. Ela é
idempotente, custa um `DELETE` com subconsulta e, em banco limpo, não registra
nada em log.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Duas observações:

1. **A causa raiz continua de pé:** não existe foreign key nem `ON DELETE
   CASCADE` no schema, e `PRAGMA foreign_keys` é `0`. Esta OS corrige o sintoma
   conhecido em `chapters`; a próxima tabela que alguém criar pode repetir a
   história. Ligar as FKs resolveria a classe inteira, mas muda o comportamento de
   **toda** escrita do projeto e exige revisar cada caminho de insert e delete —
   está declarado fora de escopo na seção 2 e é candidato a OS própria, com risco
   próprio. **Registrado como item 64 do backlog.**

2. **A varredura apaga dados.** Restringi ao que é provadamente inalcançável —
   linha cujo `book_id` não existe em `books`, e todo consumidor busca capítulo
   por `book_id` — e fiz o log dizer quantas linhas saíram. Não é silenciosa de
   propósito: apagar em silêncio é o que transforma correção em surpresa.

## 7. Link do PR

Ver o PR aberto contra `main` com título `[OS-060] delete_book deixa capítulos órfãos`.
