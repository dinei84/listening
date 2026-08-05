# OS-029 — UI do Visualizador: seletor de capítulos + indicador de posição

> **Depende da OS-027 (detecção de capítulos) e da OS-028 (progresso no servidor).** Sem capítulos persistidos não há o que listar; sem progresso no servidor, o indicador de posição fica preso ao `localStorage` de hoje.

## 1. Objetivo

Liga na UI do player as duas capacidades de backend das OS-027/028: uma lista de capítulos navegável (pular pra frente/voltar sem precisar ouvir tudo em sequência) e um indicador visual de "onde estou no livro" — mesmo padrão já usado no projeto pra ligar backend → UI (OS-013→014, OS-015→016, OS-021→023/024).

## 2. Escopo

**Dentro do escopo:**
- `player/index.html`: seção/painel novo com a lista de capítulos do livro aberto (consumindo `GET /books/{id}/chapters`, OS-027), cada um clicável.
- `player/app.js`: clicar num capítulo pula pro primeiro `AudioChunk` daquele intervalo (usa `chapter_id`/`sequence` inicial do capítulo — a lista de `chunks` já carregada tem `chapter_id` por chunk desde a OS-027, filtrar pelo primeiro da sequência do capítulo escolhido).
- Indicador de posição: mostrar o capítulo atual (nome) + posição relativa (ex: "Capítulo 3 de 12" e/ou "chunk 45 de 340", reaproveitando `chunks_total`/contagem já existente da OS-024) — atualizado durante a reprodução, junto com o `<progress>` já existente.
- Resume: troca a lógica atual de `pendingResume`/`resumeBanner` (baseada só em `localStorage`) para usar `GET /books/{id}/progress` (OS-028) como fonte da posição oferecida no banner de retomar.
- Verificação manual em navegador real desta OS antes de fechar (mesmo padrão das OS-014/016/023) — **não pular esta etapa**, diferente do que ficou pendente na OS-024.

**Fora do escopo:**
- Reordenar/editar capítulos.
- Sincronizar progresso entre abas abertas ao mesmo tempo no mesmo livro.
- Qualquer mudança no backend além do que as OS-027/028 já entregaram — esta OS só consome o que já existe.

## 3. Contratos envolvidos

Nenhum contrato novo — esta OS só consome `GET /books/{id}/chapters` (OS-027) e `GET/PUT /books/{id}/progress` (OS-028), ambos já definidos nas OS's anteriores.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Lista de capítulos aparece no player, com o nome de cada um
- [ ] Clicar num capítulo pula a reprodução pro início dele
- [ ] Indicador de posição mostra capítulo atual, atualizado durante a reprodução
- [ ] Banner de retomar usa o progresso do servidor (OS-028), não só `localStorage`
- [ ] Verificação manual em navegador real concluída e registrada no relatório (seção própria, mesmo padrão das OS-014/016/023) — golden path (abrir livro, navegar entre capítulos, retomar de onde parou) e pelo menos um caso de borda (livro com fallback sintético de capítulo, sem TOC real)

## 5. Testes exigidos (mínimo)

Esta OS é majoritariamente UI (JS puro, sem suíte de testes automatizada — decisão #12, mesmo caso das OS-014/016/023/024). Verificação principal é manual em navegador. Cobertura automatizada onde fizer sentido:

- Nenhum teste novo de backend esperado (esta OS não muda `api/`, `core/`, `storage/`, `worker/`) — se algum ajuste de backend for necessário durante a implementação, documentar no relatório por que não estava previsto.

Local sugerido: verificação manual documentada em `docs/report/OS-029-report.md` seção própria (mesmo formato das seções 6.1 das OS-014/016).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-029-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
