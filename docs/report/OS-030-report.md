# OS-030 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/030-playback-audio-parcial
**Commit(s) relevante(s):** 484dc7b (feat, player), 5ed01b7 (sync de docs de governança, sem código)

## 1. Resumo do que foi feito

`player/app.js` parou de esperar `status === "ready"` para buscar áudio: o ciclo de polling agora lê o status **e** a lista de chunks a cada 2s, começa a tocar assim que existe pelo menos um chunk, e anexa os chunks novos sem interromper nem reiniciar a reprodução. Chegar ao fim do que já foi sintetizado mostra "Aguardando próximo trecho..." e retoma sozinho quando o próximo chunk fica pronto. Nenhuma linha de backend mudou.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [ ] **Não se aplica — testes escritos antes da implementação (commit "Red").** Esta OS é 100% UI em JS puro e o projeto não tem suíte de testes JS (decisão #12: player sem build step/toolchain). A seção 5 da própria OS estabelece que "a verificação principal é manual, registrada no relatório" e que nenhum teste de backend novo é esperado. Não houve commit Red porque não havia teste automatizado a escrever sem introduzir uma segunda toolchain que a OS não autoriza. A verificação equivalente foi feita em navegador real e está na seção 4 deste relatório, com resultado de cada critério.
- [x] Todos os testes da OS passam localmente — a suíte existente (backend) segue verde: **123 passed**
- [x] Nenhum teste existente quebrou
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato tocado; o player consome `GET /books/{id}/status` e `GET /books/{id}/audio` como já existiam
- [x] Nenhuma chamada real a API paga — nada de cloud envolvido; a verificação manual usou Kokoro local (engine local, sem custo variável, permitido por `TDD.md` seção 3)
- [ ] **Não se aplica — type hints e docstring de uma linha em toda função pública.** Regra de Python (`AGENTS.md` seção 5); o arquivo alterado é JavaScript. As funções novas (`statusMessage`, `mergeChunks`, `startPlayback`, `pollBook`, `resetPlaybackState`) receberam comentário explicativo onde o motivo não era óbvio, seguindo o estilo já existente no arquivo.
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4, 5 e 6)
- [x] Relatório criado em `docs/report/OS-030-report.md`
- [x] PR aberto contra o branch principal, título `[OS-030] Tocar áudio parcial enquanto o livro ainda sintetiza`

### DoD específico da OS (`docs/os/OS-030-playback-audio-parcial.md` seção 4)

- [x] Abrir um livro em `synthesizing` que já tenha ≥1 chunk persistido começa a tocar, sem esperar `ready` — verificado no navegador: tocou com `bookStatus: "synthesizing"`, `Sintetizando: 1 de 49 chunks`
- [x] Chunks sintetizados durante a reprodução são anexados sem interromper e sem voltar ao início — as 49 `sequence`s foram tocadas em ordem estritamente crescente (`[0, 1, 2, ..., 48]`), sem nenhuma repetição ou retorno
- [x] Chegar ao fim dos chunks disponíveis com a síntese em andamento mostra um estado de espera e retoma sozinho — `Aguardando próximo trecho...` observado com 1 chunk disponível, e 2s depois a reprodução seguiu sozinha para a `sequence` 1
- [x] Livro que chega a `ready` durante a reprodução continua funcionando até o último chunk — virou `ready` enquanto tocava a `sequence` 47 e seguiu até a 48, terminando em "Fim do áudio."
- [x] Abrir um livro sem nenhum chunk (`uploaded`) não quebra — página estável, `Status: uploaded`, nenhum erro de JS no console, começou a tocar sozinha quando o primeiro chunk apareceu
- [x] Barra de progresso da OS-024 continua funcionando durante a reprodução parcial — visível com `value=1 / max=49` enquanto o áudio já tocava, e escondida quando o livro ficou `ready`
- [x] **Verificação manual em navegador real** — feita, seção 4 abaixo (não deixada pendente como na OS-024)

## 3. Testes escritos

Nenhum teste automatizado novo — ver a justificativa no primeiro item da checklist padrão acima e a seção 5 da OS ("Esta OS é majoritariamente UI em JS puro, sem suíte de testes JS no projeto (decisão #12) — a verificação principal é manual"). A suíte de backend existente continua rodando e verde:

```
$ venv/bin/python -m pytest -q
123 passed, 1 warning in 8.37s
```

Confirmar: commit "Red" antes do commit "Green"? [ ] Sim [x] Não — não havia teste automatizado a escrever sem introduzir uma toolchain de testes JS, que está fora do escopo desta OS e contraria a decisão #12. Substituído por verificação em navegador real com resultado registrado por critério (seção 4).

## 4. Verificação manual em navegador real (obrigatória pelo DoD)

**Ambiente isolado, sem tocar nos dados reais do dono do projeto:** a API (`uvicorn`, porta 8011) e o worker (`python -m worker.tasks`) foram executados com `cwd` num diretório temporário de scratchpad e `PYTHONPATH` apontando para o repositório — como `books.db`, `uploads/` e `storage/audio/` são caminhos relativos ao `cwd`, o `books.db` real do projeto (com o "Security Engineering") não foi lido nem alterado em nenhum momento.

**Fixture:** PDF de 14 páginas gerado no scratchpad com ~44 mil caracteres de texto único por linha (linhas repetidas seriam removidas pelo cleaner da OS-008 como header/footer), resultando em **49 chunks** — grande o bastante para a síntese durar minutos e a reprodução alcançá-la.

**Browser:** Google Chrome real (`channel: "chrome"`, headless), dirigido por Playwright instalado **num venv separado no scratchpad** — nenhuma dependência nova foi adicionada ao `requirements-dev.txt` do projeto. Síntese real do Kokoro na GPU, worker real, API real.

**Roteiro executado:** (A) abrir o livro com o worker parado e nenhum chunk; (B) subir o worker e observar o início da reprodução; (C) pular para o fim de cada trecho, correndo na frente da síntese até bater no fim da fila; (D) seguir até `ready` e até o último chunk. Console e `pageerror` capturados o tempo todo — nenhum erro de JS (o único 404 registrado é `/favicon.ico`, que o projeto não serve, comportamento pré-existente).

Saída bruta dos momentos-chave (estado lido direto do DOM e das variáveis do player):

```
[13:26:45] FASE A (sem worker, 0 chunks): {'status': 'Status: uploaded', 'progressHidden': True, 'chunkCount': 0,
           'currentSequence': None, 'waiting': False, 'bookStatus': 'uploaded', 'src': None, 'paused': True}
[13:26:45] worker iniciado
[13:26:54] FASE B (primeiro áudio tocando): {'status': 'Sintetizando: 1 de 49 chunks — tocando o que já está pronto',
           'progressHidden': False, 'progressValue': 1, 'progressMax': 49, 'chunkCount': 1, 'currentIndex': 0,
           'currentSequence': 0, 'waiting': False, 'bookStatus': 'synthesizing',
           'src': '/books/dea94d69-.../audio/0', 'paused': False, 'currentTime': 0.034079, 'duration': 66.275}
[13:26:54] FASE C (fim da fila durante síntese): {'status': 'Aguardando próximo trecho...', 'progressHidden': False,
           'chunkCount': 1, 'currentSequence': 0, 'waiting': True, 'bookStatus': 'synthesizing',
           'paused': True, 'currentTime': 66.275, 'duration': 66.275}
[13:26:56] FASE C (retomou sozinho): {'status': 'Sintetizando: 2 de 49 chunks — tocando o que já está pronto',
           'chunkCount': 2, 'currentIndex': 1, 'currentSequence': 1, 'waiting': False,
           'src': '/books/dea94d69-.../audio/1', 'paused': False, 'currentTime': 0.13987}
[13:27:58] FASE D (livro ficou ready durante a reprodução): {'status': 'Pronto.', 'progressHidden': True,
           'chunkCount': 49, 'currentIndex': 47, 'currentSequence': 47, 'bookStatus': 'ready', 'paused': False}
[13:27:59] FASE D (fim do livro): {'status': 'Fim do áudio.', 'chunkCount': 49, 'currentSequence': 48,
           'bookStatus': 'ready', 'paused': True, 'currentTime': 35.2, 'duration': 35.2}
[13:27:59] sequences tocadas (final): [0, 1, 2, 3, ..., 46, 47, 48]
[13:27:59] RESULTADOS: {
  "A_nao_quebra_sem_chunks": true,
  "B_toca_antes_de_ready": true,
  "B_barra_visivel_durante_playback_parcial": true,
  "C_estado_de_espera": true,
  "C_retoma_sozinho": true,
  "C_nunca_volta_ao_inicio": true,
  "D_continua_ate_o_fim": true,
  "D_barra_escondida_no_ready": true,
  "D_ordem_final_sem_reinicio": true
}
```

**Caso de erro com áudio parcial** (bullet da seção 2 da OS, verificado à parte): o livro foi forçado para `status="error"` no banco do sandbox, mantendo só os 5 primeiros chunks. Ao abrir no player:

```
{'status': 'Erro no processamento — tocando os 5 trecho(s) já sintetizados.', 'chunkCount': 5,
 'src': '/books/dea94d69-.../audio/0', 'paused': False, 'polling': False, 'progressHidden': False}
```

O erro aparece, o polling para, e o que dá pra ouvir continua tocável — que é exatamente o pedido ("não descartar o que dá pra ouvir"). A barra de progresso fica visível nesse caso (mostrando 5 de 49), decisão consciente: comunica onde a síntese parou.

Capturas de tela dos quatro estados (A, B, C-aguardando, D-ready/fim) e o log completo ficaram no diretório de scratchpad da sessão, não versionados — o conteúdo relevante está transcrito acima.

## 5. Decisões de implementação documentadas

**(a) A posição de reprodução passou a ser ancorada na `sequence`, não no índice do array.** `currentIndex` sozinho é frágil quando a lista cresce: se a retomada da OS-022 preencher um buraco antes do trecho em reprodução, o mesmo índice passa a apontar para outro áudio. `playChunk()` guarda `currentSequence` e `mergeChunks()` reancora `currentIndex` por ela depois de cada merge.

**(b) "Fim do áudio" vs. "Aguardando próximo trecho" é decidido por `pollTimer !== null`.** O polling é parado exatamente quando o livro chega a `ready`/`error`, então "ainda estou pollando" é o mesmo que "a síntese pode produzir mais". Evita duplicar a máquina de estados do status em outra variável.

**(c) O timer de polling é armado antes do primeiro ciclo** (`openBook`), para que um livro já `ready` consiga pará-lo de dentro do próprio ciclo — se fosse armado depois, o `stopPolling()` do primeiro ciclo não teria nada para limpar e o polling ficaria rodando para sempre num livro já terminado.

**(d) Falha pontual em `GET /books/{id}/audio` não derruba a reprodução:** o `catch` do merge é silencioso de propósito e o ciclo seguinte tenta de novo. Falha no `GET /status`, essa sim, para o polling e mostra o erro (comportamento de antes, preservado).

**(e) `player/index.html` não mudou.** A OS permitia ajustes "se necessário"; os estados novos são só texto dentro do `#player-status` que já existia, e a barra da OS-024 já estava no lugar certo.

## 6. Desvios do escopo original

Nenhum desvio de escopo de código: as mudanças ficaram inteiramente em `player/app.js`, nenhum arquivo de backend foi tocado (a OS pedia para parar e reportar se backend parecesse necessário — não foi).

Dois pontos de processo, para registro:

1. O primeiro commit do branch (`5ed01b7`) é a **sincronização dos docs vindos do repositório de arquitetura** (`docs/os/OS-027` a `OS-031` e a atualização do `PROJECT_STATE.md` que priorizou esta OS), que estavam como modificação não commitada na `main` ao início da sessão. Commitados aqui, separados do código, conforme a decisão #6 — não são trabalho de execução desta OS.
2. Playwright foi usado só como ferramenta de verificação, instalado num venv de scratchpad. **Nada foi adicionado a `requirements.txt`/`requirements-dev.txt`** — adotar (ou não) uma suíte de testes de browser é decisão de arquitetura, não de execução.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Uma observação e uma sugestão para o dono do projeto:

1. **Retomada (`localStorage`) apontando para uma `sequence` ainda não sintetizada:** o comportamento antigo foi preservado (cai para o trecho 0). Na prática é inalcançável — os chunks são persistidos em ordem crescente e nunca removidos, então o usuário só pode ter salvo uma posição que já existe. Se algum dia deixar de ser verdade (ex: alguma forma de reprocessamento parcial), vira um caso a tratar.
2. **Backlog relacionado:** com o áudio parcial tocável, o item 35 do backlog (preempção/prioridade na fila) fica mais interessante — hoje, escolher outro livro não interrompe a síntese do atual, mas agora dá para ouvir os dois parcialmente conforme a fila avança.

## 8. Link do PR

https://github.com/dinei84/listening/pull/22
