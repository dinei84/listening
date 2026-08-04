# OS-016 — Liga a listagem de livros na UI do player

## 1. Objetivo

Consumir o `GET /books` (OS-015) no `player/`: mostrar os livros já enviados numa lista clicável, em vez de depender só do campo manual de `book_id`.

## 2. Escopo

**Dentro do escopo:**
- `player/index.html` + `player/app.js`: nova seção de lista de livros.
  - Ao carregar a página, buscar `GET /books` e renderizar cada item com pelo menos `title`, `status` e `created_at` (formatado de forma legível).
  - Clicar num item da lista abre aquele livro (reaproveita o fluxo já existente de `openBook()` — polling de status, playback, resume — sem duplicar lógica).
  - Lista vazia mostra uma mensagem amigável (ex: "Nenhum livro ainda"), não fica em branco sem explicação.
  - Um botão "Atualizar lista" que rebusca `GET /books` sem precisar recarregar a página inteira.
  - Depois de um upload bem-sucedido, a lista é atualizada automaticamente (o livro recém-criado aparece).
- O campo manual de `book_id` (`#manual-section`) **continua existindo** — não remover, é um fallback útil (ex: abrir um livro por id copiado de um `curl`). A lista é o caminho principal agora, o campo manual é secundário.

**Fora de escopo:**
- Atualização automática/periódica da lista inteira enquanto a página está aberta (ex: refletir em tempo real quando um livro que estava `processing` vira `ready`) — o usuário clica em "Atualizar lista" quando quiser. Uma vez que um livro é aberto, o polling de status dele já existe (OS-014) e continua funcionando normalmente.
- Exclusão de livros, edição de título, qualquer ação de escrita nova — só listagem e abertura.
- Paginação — mesma decisão da OS-015 (sem paginação por enquanto).
- Mudanças em `api/routes_books.py` ou qualquer contrato de backend — usa `GET /books` exatamente como já existe.

## 3. Contratos envolvidos

Nenhum. Consome só `GET /books`, já implementado e testado na OS-015.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Ao carregar a página, a lista de livros é buscada e renderizada (`title`, `status`, `created_at`)
- [ ] Lista vazia mostra mensagem amigável, não fica em branco
- [ ] Clicar num item da lista abre o livro (mesmo fluxo de `openBook()` já existente)
- [ ] Botão "Atualizar lista" rebusca e re-renderiza sem recarregar a página
- [ ] Depois de um upload bem-sucedido, a lista se atualiza automaticamente
- [ ] Campo manual de `book_id` continua funcionando, não foi removido
- [ ] Nenhuma dependência nova de frontend (framework/bundler/npm)
- [ ] Nenhuma chamada de rede além da própria API do projeto

### Nota sobre verificação (mesma regra da OS-014)

Esta OS é frontend — sem ciclo Red/Green de TDD da mesma forma que o backend. Verificação manual num navegador real é obrigatória antes de considerar concluída: subir a API + worker (`RUNBOOK.md`), enviar pelo menos dois PDFs, confirmar que ambos aparecem na lista, clicar num deles e confirmar que abre e toca normalmente, testar o botão de atualizar lista, e confirmar que o campo manual continua funcionando. Se o agente de execução não tiver acesso a navegador/automação no ambiente dele, seguir o mesmo protocolo já usado na OS-014: implementar, deixar o PR como draft, documentar precisamente o que falta verificar e por quê — não fechar a OS sem essa verificação.

## 5. Testes exigidos (mínimo)

Não há teste automatizado de backend novo nesta OS (nenhum contrato de API muda). A verificação é a checklist manual da seção acima, documentada no relatório.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-016-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
