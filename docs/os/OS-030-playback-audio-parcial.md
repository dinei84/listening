# OS-030 — Tocar áudio parcial enquanto o livro ainda sintetiza

> **Esta OS é o "ligar na UI" que a OS-021 explicitamente deixou pra depois** (`docs/os/OS-021-entrega-incremental-audio.md` seção 2, "Fora de escopo"): *"mudar o `player/` pra realmente tocar os chunks parciais antes do livro ficar `ready` (...). Ligar isso na UI é uma OS seguinte"*. A capacidade de backend existe desde a OS-021 e nunca foi consumida.

## 1. Objetivo

Medido em uso real (livro "Security Engineering", 1212 páginas, 2026-08-05): **2265 `AudioChunk`s já persistidos e tocáveis — 40 horas de áudio — enquanto o usuário olhava uma barra de progresso sem conseguir ouvir nada.** `pollUntilReady()` (`player/app.js`) só chama `fetchAudioChunks()` quando `status === "ready"`, então todo o áudio parcial que a OS-021 passou a persistir incrementalmente fica inacessível até o livro inteiro terminar. Esta OS faz o player começar a tocar assim que o primeiro chunk existe, e continuar buscando os novos conforme são sintetizados.

**Contexto de performance (medido, para calibrar expectativa):** a síntese em si não é o gargalo — 1,34 s/chunk na GPU (RTX 3060, CUDA ativo), ~14 s de áudio gerado por segundo de processamento. O livro inteiro leva ~74 min para 40h de áudio. O problema é puramente de entrega, não de velocidade. Otimizar a síntese é assunto separado (OS-031).

## 2. Escopo

**Dentro do escopo:**
- `player/app.js`:
  - `openBook()` / `pollUntilReady()`: parar de exigir `status === "ready"` para buscar áudio. Passar a buscar os chunks disponíveis assim que houver **pelo menos um** (`GET /books/{id}/audio` já devolve chunks parciais desde a OS-021 — não checa status, confirmado por teste naquela OS).
  - Enquanto o livro estiver `synthesizing`, continuar o polling e **anexar** os chunks novos à lista `chunks` já carregada, sem interromper a reprodução em andamento nem re-tocar do início. Preservar `currentIndex`.
  - Tratamento do fim da lista durante síntese ativa: hoje `audioPlayer.addEventListener("ended")` mostra "Fim do áudio." quando acaba a lista. Com síntese em andamento, isso é "alcancei o que já foi sintetizado", não o fim do livro — mostrar um estado diferente (ex: "aguardando próximo trecho...") e retomar a reprodução automaticamente quando o próximo chunk aparecer no polling.
  - Manter a barra de progresso da OS-024 visível durante a reprodução parcial (o usuário está ouvindo E vendo o quanto falta sintetizar).
  - Continuar tratando `status === "error"` como hoje (interrompe, mostra o erro) — mas se já houver chunks tocáveis, não descartar o que dá pra ouvir.
- `player/index.html`: ajustes de texto/estado se necessário para o novo estado "tocando parcial".

**Fora do escopo:**
- Qualquer mudança de backend — `GET /books/{id}/audio` e `GET /books/{id}/status` já entregam tudo que esta OS precisa (OS-021 e OS-024). Se durante a implementação parecer necessário mudar backend, **parar e reportar** em vez de expandir o PR.
- Preempção/priorização de fila (pausar livro A ao selecionar o livro B) — capacidade nova, OS separada a definir.
- Otimizar a velocidade de síntese — OS-031 (spike).
- Seletor de capítulos / indicador de posição — OS-027 a 029.

## 3. Contratos envolvidos

Nenhum contrato muda. Esta OS só consome endpoints que já existem (`GET /books/{id}/audio` da OS-013/021, `GET /books/{id}/status` com `chunks_done`/`chunks_total` da OS-024).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Abrir um livro em `synthesizing` que já tenha ≥1 chunk persistido começa a tocar, sem esperar `ready`
- [ ] Chunks sintetizados durante a reprodução são anexados à lista sem interromper o que está tocando e sem voltar ao início
- [ ] Chegar ao fim dos chunks disponíveis com a síntese ainda em andamento mostra um estado de espera (não "Fim do áudio.") e retoma sozinho quando o próximo chunk fica pronto
- [ ] Livro que chega a `ready` durante a reprodução continua funcionando normalmente até o último chunk
- [ ] Abrir um livro sem nenhum chunk ainda (`uploaded`/início de `synthesizing`) não quebra — espera o primeiro chunk aparecer
- [ ] Barra de progresso da OS-024 continua funcionando durante a reprodução parcial
- [ ] **Verificação manual em navegador real, obrigatória** (mesmo padrão das OS-014/016/023; a OS-024 deixou isso pendente, não repetir): tocar um livro parcialmente sintetizado, confirmar que a reprodução não reinicia quando novos chunks chegam, e que o estado de espera no fim da fila se resolve sozinho

## 5. Testes exigidos (mínimo)

Esta OS é majoritariamente UI em JS puro, sem suíte de testes JS no projeto (decisão #12) — a verificação principal é manual, registrada no relatório. Nenhum teste de backend novo é esperado (o backend não muda).

Se algum ajuste de backend se provar inevitável, documentar no relatório por que não estava previsto e cobrir com teste automatizado normalmente.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-030-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
