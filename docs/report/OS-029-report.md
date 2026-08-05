# OS-029 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/029-ui-visualizador (empilhada sobre `os/028-progresso-leitura`)
**Commit(s) relevante(s):** 2650026 (test: Red), a seguir o commit de Green

## 1. Resumo do que foi feito

O player ganhou a lista de capítulos navegável (consumindo `GET /books/{id}/chapters` da OS-027) e o indicador de posição ("Capítulo 2 de 3 — Desenvolvimento · trecho 4 de 6"). Clicar num capítulo pula para o primeiro trecho dele; o capítulo em reprodução é marcado com "← tocando"; capítulos ainda não sintetizados aparecem desabilitados com "(ainda sintetizando)". O banner de retomar passou a usar o progresso do servidor (OS-028) em vez do `localStorage`. Livro sem capítulos (processado antes da OS-027) esconde a seção e mantém tudo funcionando.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `2650026` "Red" antes do Green)
- [x] Todos os testes da OS passam localmente — 200 pass, 0 fail
- [x] Nenhum teste existente quebrou (196 anteriores + 4 novos = 200)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato de plugin tocado
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados
- [ ] **Não se aplica — type hints e docstring em toda função pública.** Regra de Python (`AGENTS.md` seção 5); as funções novas (`fetchChapters`, `chapterOfSequence`, `firstChunkIndexOfChapter`, `renderChapters`, `renderPositionIndicator`) são JavaScript. Todas receberam comentário explicativo onde o motivo não era óbvio, seguindo o estilo do arquivo.
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-029-report.md`
- [x] PR aberto contra o branch principal, título `[OS-029] UI do Visualizador`

### DoD específico da OS (seção 4)

- [x] Lista de capítulos aparece no player, com o nome de cada um — verificado em navegador: `["Introducao ← tocando", "Desenvolvimento", "Conclusao"]`
- [x] Clicar num capítulo pula a reprodução pro início dele — pulou para "Conclusao" (`/audio/4`) e voltou para "Desenvolvimento" (`/audio/2`), tocando nos dois casos
- [x] Indicador de posição mostra capítulo atual, atualizado durante a reprodução — `"Capítulo 3 de 3 — Conclusao · trecho 5 de 6"` mudou para `"Capítulo 2 de 3 — Desenvolvimento · trecho 3 de 6"` ao trocar de capítulo
- [x] Banner de retomar usa o progresso do servidor (OS-028), não só `localStorage` — provado com `localStorage` **esvaziado** antes do reload (ver seção 4)
- [x] Verificação manual em navegador real concluída e registrada — seção 4, com golden path e o caso de borda de livro sem capítulos

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_player_has_chapter_list_section` | `tests/integration/test_player.py` | Sim |
| `test_player_has_position_indicator` | `tests/integration/test_player.py` | Sim |
| `test_player_js_consumes_chapters_and_progress_endpoints` | `tests/integration/test_player.py` | Sim |
| `test_get_books_audio_returns_chapter_id_per_chunk` (ver desvio, seção 5) | `tests/integration/test_api_books.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `2650026` (3 falhas: `id="chapters-list"`, `id="position-indicator"` e `/chapters` ausentes) antes do Green.

## 4. Verificação manual em navegador real (obrigatória pelo DoD)

**Ambiente isolado:** API (`uvicorn`, porta 8029) e worker rodando com `cwd` num diretório de scratchpad e `PYTHONPATH` apontando para o repositório — o `books.db` real do dono do projeto **não** foi lido nem alterado. Síntese real do Kokoro (idioma forçado `pt`), worker real, Chrome real.

**Fixture:** PDF de 9 páginas com TOC de 3 capítulos (`Introducao` p.1, `Desenvolvimento` p.4, `Conclusao` p.7), texto denso o bastante para gerar 2 chunks por capítulo.

### Backend (confirma que a OS-027 chega íntegra na UI)

```
status:    {"status":"ready","chunks_done":6,"chunks_total":6}
capítulos: Introducao (1-3), Desenvolvimento (4-6), Conclusao (7-9)
chunks:    6  |  a7d53773 -> 2 | 4f591a31 -> 2 | bb1df89b -> 2
sequences: [0, 1, 2, 3, 4, 5]      <- global e contínua entre capítulos
```

### Golden path na UI

```
Ao abrir pela lista:
{ "titulo": "Livro: livro.pdf", "status": "Pronto.",
  "secaoCapitulosVisivel": true,
  "capitulos": ["Introducao ← tocando", "Desenvolvimento", "Conclusao"],
  "indicador": "Capítulo 1 de 3 — Introducao · trecho 1 de 6",
  "tocando": true, "src": ".../audio/0" }

Ao clicar em "Conclusao":
{ "indicador": "Capítulo 3 de 3 — Conclusao · trecho 5 de 6",
  "capitulos": ["Introducao", "Desenvolvimento", "Conclusao ← tocando"],
  "src": "/audio/4", "tocando": true }

Ao voltar para "Desenvolvimento":
{ "indicador": "Capítulo 2 de 3 — Desenvolvimento · trecho 3 de 6", "src": "/audio/2" }
```

### Retomada vinda do servidor (não do `localStorage`)

```
1. progresso gravado pelo player durante a reprodução:
   {"sequence": 2, "position_seconds": 5.800851, "updated_at": "...21:33:43"}
2. localStorage.clear()  ->  { "localStorageLimpo": true }
3. reload + abrir o livro -> { "bannerRetomarVisivel": true }
4. clicar em "Retomar":
   { "src": "/audio/2", "currentTime": 23.5,
     "indicador": "Capítulo 2 de 3 — Desenvolvimento · trecho 3 de 6", "tocando": true }
```

Com o `localStorage` esvaziado, a posição só pode ter vindo do servidor — o critério da OS. O `currentTime` de 23,5s (em vez dos 5,8s do passo 1) não é discrepância: o chunk 2 tem **63,3s** e a página anterior continuou tocando e gravando enquanto o teste avançava; o valor do servidor foi de 5,8 → 23,5 → 40,6s ao longo da sessão. O que a OS exige — a posição vir do servidor — está provado.

### Caso de borda: livro sem capítulos (simula pré-OS-027)

Capítulos removidos do banco do sandbox para reproduzir um livro processado antes da OS-027:

```
{ "semCapitulos_secaoEscondida": true,
  "semCapitulos_indicador": "trecho 1 de 6",
  "semCapitulos_indicadorVisivel": true,
  "reproducaoContinuaFuncionando": true,
  "src": "/audio/0",
  "errosJS": [] }
```

A seção de capítulos some, o indicador degrada para só o trecho, a reprodução segue normal e **nenhum erro de JS** é lançado.

`GET /books/nao-existe/chapters` devolve **404**, como esperado.

## 5. Desvios do escopo original

**Um desvio de backend, previsto pela própria OS como possível.** A seção 5 da OS diz: "se algum ajuste de backend for necessário durante a implementação, documentar no relatório por que não estava previsto".

`GET /books/{id}/audio` **não devolvia `chapter_id`** — só `sequence`, `duration_seconds` e `url`. Sem esse campo o player não tem como mapear trecho → capítulo, e tanto a lista de capítulos quanto o indicador de posição ficam impossíveis: a OS-027 gravou o `chapter_id` em cada `AudioChunk`, mas ele parava no banco e nunca chegava à UI. Descoberto exatamente na verificação em navegador (`KeyError: 'chapter_id'`), não em revisão de código.

A mudança é **mínima e aditiva** — um campo novo na resposta, nenhum campo existente alterado ou removido, nenhum contrato de plugin tocado — e está coberta por `test_get_books_audio_returns_chapter_id_per_chunk`. A alternativa (o player buscar o mapeamento por outra via) exigiria contar chunks por capítulo no cliente, reintroduzindo exatamente o acoplamento frágil que a OS-027 evitou ao carimbar o `chapter_id` em cada chunk.

Nenhum outro desvio: `player/index.html` e `player/app.js` são o resto das mudanças.

## 6. Decisões de implementação documentadas

**(a) O mapeamento trecho → capítulo usa o `chapter_id` do chunk, não contagem.** `chapterOfSequence()` acha o chunk pela `sequence` e casa o `chapter_id` dele com a lista de capítulos. Contar "quantos chunks tem cada capítulo" no cliente quebraria durante a síntese incremental (OS-021/030), quando a lista ainda está crescendo.

**(b) Capítulo ainda não sintetizado fica desabilitado, não escondido.** `firstChunkIndexOfChapter()` devolve `null` quando a síntese não chegou lá; o botão vira `disabled` com o rótulo "(ainda sintetizando)". Assim o leitor vê a estrutura completa do livro desde o começo, mesmo ouvindo enquanto sintetiza, sem clicar em algo que não tem áudio.

**(c) Os capítulos são buscados em todo ciclo de polling enquanto a lista estiver vazia.** O worker só persiste os capítulos quando começa a processar o livro — buscar uma vez só, na abertura, deixaria a seção vazia para sempre num livro recém-enviado. Assim que a lista chega, a busca para.

**(d) O indicador degrada em vez de sumir quando não há capítulos.** Mostra só "trecho N de M" — informação útil que existe independente da OS-027, e evita que a UI pareça quebrada em livros antigos.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Uma observação para o dono do projeto: **livros processados antes da OS-027 não têm capítulos persistidos** e vão mostrar a seção escondida até serem reenviados (comportamento verificado na seção 4). Não há reprocessamento automático — mesmo padrão já registrado nas OS-019 e OS-034.

## 8. Link do PR

*A preencher após abrir o PR.*
