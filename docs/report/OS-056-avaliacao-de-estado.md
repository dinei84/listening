# OS-056 — Avaliação de estado: roteamento por expressividade

**Data:** 2026-08-14
**Tipo:** avaliação de estado (leitura de código + docs + histórico), não é relatório de OS
**Autor:** análise assistida, a pedido do dono do projeto

---

## 1. Resumo executivo

**A sua ideia já existe, já foi medida e já está implementada.** O que você descreveu — contar pontuações expressivas no pré-processamento e mandar só os trechos densos para a IA paga, devolvendo o áudio ao fluxo de chunks — é exatamente o par **OS-055 (`OpenAISpeaker`) + OS-056 (roteamento por expressividade)**, aberto em 13/08/2026 e implementado no branch `os/055-openai-speaker` (11 commits à frente da `main`, 399 testes passando).

O trabalho está a **um PR + uma validação real de áudio** de distância de ser concluído — não a um projeto de distância. A sensação de "rodar em círculos" não vem de falta de direção técnica; vem de três coisas concretas, detalhadas nas seções 5 e 6:

1. O branch com a feature **não tem PR aberto, não tem relatório e o `PROJECT_STATE.md` ainda diz que a última OS é a 054** — o trabalho existe mas não "aterrissou" no processo.
2. O teste real de ontem à noite bateu no muro de **crédito esgotado na OpenAI** (429 `insufficient_quota`, commits de 21:13 e 21:26) — um problema que não é de código, e que o código não resolve.
3. **Nenhum áudio real da OpenAI foi produzido neste ambiente até agora** — o único livro de teste no banco (`teste-expressividade2.pdf`, 2 chunks) foi narrado 100% pelo Kokoro.

---

## 2. O que a aplicação faz hoje

Pipeline completo e testado: upload de PDF → extração (PyMuPDF → Tesseract → EasyOCR) → limpeza/sanitização → detecção de capítulos → chunking por sentença (~1000 chars) → síntese incremental com persistência por chunk → player web com playback parcial, retomada, preempção de fila e trava de custo. Sobre esse esqueleto, três camadas de "naturalidade" já existem:

| Camada | Onde | Custo |
|---|---|---|
| **Ritmo determinístico** (OS-045): pausas calibradas por pontuação (vírgula 250 ms … parágrafo 1100 ms), velocidade 0,90 (~140 WPM), aparas de silêncio | `KokoroSpeaker` | zero |
| **Notação e prosódia via LLM** (OS-038 + OS-054): números/abreviações por extenso e ajuste só de pontuação, com guarda-corpos | `plugins/normalizers/` | ~US$ 0,16–0,87/livro (cada passe) |
| **Motor pago por demanda** (OS-055/056): chunk denso em `!`/`?` vai inteiro para a OpenAI | `core/pipeline.py` | ~US$ 0,79/livro medido |

## 3. Sua ideia, mapeada para o que já existe

| Elemento da sua ideia | Onde está | Estado |
|---|---|---|
| "Prever no pré-processamento as pontuações" | `_expressive_sentence_count()` em `core/pipeline.py` — contagem determinística de frases com `!`/`?` por chunk. **Decisão correta já registrada (backlog item 54): não precisa de "preditor" de IA** — o texto inteiro está em memória antes da síntese, então é regra, não lookahead. IA de verdade só entra onde ela agrega: a voz | Implementado |
| "Trecho com N pontuações perto uma da outra dispara o motor da IA" | Limiar configurável `routing.min_expressive_sentences` (padrão **3**, não 5 — ver a medição abaixo) | Implementado |
| "Devolver ao chunk para ele entregar o áudio em fluxo contínuo" | O chunk roteado vira um `AudioChunk` comum, persistido e servido pelo mesmo fluxo incremental da OS-021/030; `engine_used` registra o motor real de cada chunk | Implementado |
| "Não processar o livro inteiro pela IA por causa do custo" | Medido em 230 chunks reais do "Programador Pragmático": livro inteiro na OpenAI = **US$ 8,58**; com limiar 3 = **US$ 0,79 (9,2% do livro)** | Medido |
| Troca de motor audível | Desenho por **chunk inteiro** (não frase a frase): 32 trocas/livro em vez de 374, e a troca cai em fronteira que já tem pausa | Decidido, **não validado por escuta** |

A única divergência da sua descrição: o limiar padrão é **3** e não 5. A medição mostrou que o limiar 3 cobre os mesmos 9% do livro que o roteamento frase-a-frase cobriria, com 12× menos trocas de voz; o 5 cai para 4,3% de cobertura e perde trecho expressivo real por ~US$ 0,40 de economia. É configurável.

## 4. Estado real do trabalho neste momento

- **Branch:** `os/055-openai-speaker`, 11 commits à frente de `origin/main`, **sem PR aberto**.
- **Testes:** 399 passando (inclui `test_routing.py` e `test_openai_speaker.py`).
- **Config atual (`config.yaml`):** `speaker: kokoro` + `routing.enabled: true` + limiar 3. Desenho coerente: Kokoro é a base, OpenAI só nos chunks densos.
- **Ambiente:** `OPENAI_API_KEY` e `LLM_API_KEY` definidas no `.env`; `PROSODY_API_KEY` ausente (prosódia desligada, o padrão); `OPENAI_INSTRUCTIONS` **não configurada**.
- **Última atividade:** dois commits de correção na noite de 13/08, frutos de teste real: (a) 429 por falta de crédito agora é falha **permanente** (antes retentava/degradava calado); (b) falha permanente do motor pago **para o livro** com mensagem clara (antes degradava calado para o Kokoro — foi o que fez você ouvir "igual ao Kokoro" achando que era a IA).
- **Banco local:** 1 livro de teste, `ready`, custo confirmado US$ 0,0177, **2 chunks ambos `kokoro`** — ou seja, o fluxo roteado com áudio real da OpenAI ainda não aconteceu de ponta a ponta.

## 5. O que está faltando

### 5.1 Bug real encontrado nesta análise: a voz do livro "vaza" para a OpenAI

A OS-053 deixou o usuário escolher a voz do Kokoro por livro (`pf_dora`, `pm_alex`, `pm_santa`). O worker repassa `book.voice` para `synthesize_text()`, que repassa ao **Speaker escolhido para cada chunk**. Se o livro tem `voice = "pm_alex"` e um chunk é roteado para a OpenAI, o `OpenAISpeaker` envia `voice="pm_alex"` à API (`voice or self._voice`) → a OpenAI devolve **HTTP 400** → `PermanentSpeakerError` → **o livro inteiro falha** (pela regra de falha rápida que você mesmo decidiu em 13/08).

Os testes não pegam isso porque o `FakeSpeaker` aceita qualquer voz — e o teste `test_openai_voice_argument_overrides_configured_voice` até celebra o repasse direto como feature. **Correção provável:** o `OpenAISpeaker` precisa tratar voz desconhecida do seu catálogo como "usar a voz configurada" (ou o pipeline precisa mapear voz por motor). Precisa de teste cruzando OS-053 × OS-056.

### 5.2 Fechamento de processo (DoD das OS-055/056)

- [ ] PR aberto (nem rascunho existe)
- [ ] `docs/report/OS-055-report.md` e `OS-056-report.md`
- [ ] `PROJECT_STATE.md` atualizado (ainda diz "última OS concluída: OS-054")
- [ ] **Amostra de áudio real** de parágrafo com troca de motor — critério de aceite explícito da OS-056, bloqueado por crédito (ver 5.3)

### 5.3 Créditos na OpenAI

O 429 de ontem foi `insufficient_quota` — **a chave existe mas não tem saldo**. Sem isso resolvido, a OS-056 não fecha (falta a amostra real) e o nível premium inteiro continua teórico, como está desde a OS-041 (06/08). É o único bloqueio que não se resolve com código.

### 5.4 `OPENAI_INSTRUCTIONS` não configurada — a alavanca gratuita, parada

A `gpt-4o-mini-tts` aceita instrução de estilo em linguagem natural ("entonação sobe nas perguntas, ênfase real nas exclamações") e **ela não é faturada** no input — é o controle de expressividade que o Kokoro não tem, de graça. O `.env.example` já tem até o texto sugerido. Hoje o roteamento manda o chunk denso para a OpenAI **sem nenhuma instrução** — ou seja, estamos pagando pelo motor expressivo sem ligar a expressividade.

### 5.5 Decisão pendente: normalização LLM em chunk que vai para a OpenAI

Hoje a ordem dentro de `synthesize_text()` é **normalizar → decidir rota**. Consequências:

- Com `normalize_text` ligado no livro, **os 9% de chunks roteados pagam LLM de notação (+ prosódia, se ligada) à toa** — a OpenAI lê número e abreviação nativamente, e a prosódia dela vem do modelo, não do texto preparado. Custo pequeno (9% de US$ 0,16–0,87), mas é custo sem benefício.
- A **estimativa de custo diverge da realidade**: `estimate_cost()` conta as frases expressivas sobre o texto **não normalizado**, mas a decisão real de rota usa o texto **normalizado**. Se a LLM de prosódia mudar pontuação, a fração roteada muda depois da estimativa aprovada pelo usuário. Na prática o prompt da OS-054 não deveria criar/remover `!`/`?`, então o desvio tende a ser pequeno — mas é uma inconsistência estrutural, não garantida.

### 5.6 Fricção operacional: todo livro vai parar em "confirmação de custo"

Com o roteamento ligado, **toda** estimativa é > 0 (alguns centavos), então **todo livro** para em `pending_confirmation` esperando um clique. A trava da OS-042 não tem limiar mínimo de auto-aprovação. Para um fluxo cujo custo típico é US$ 0,79, isso é atrito diário para proteger contra um risco de centavos. Falta um "auto-aprovar abaixo de US$ X" (decisão sua, não de agente).

### 5.7 Validação de escuta (a única medição que importa no fim)

Duas descontinuidades ainda não ouvidas em escala:

1. **Timbre:** `pf_dora` (Kokoro) × `nova` (OpenAI), 32 trocas por livro. A hipótese do desenho é que a troca em fronteira de chunk (já com pausa) é pouco perceptível — **hipótese, não medição**.
2. **Ritmo:** os chunks Kokoro saem a ~140 WPM com pausas calibradas da OS-045; os chunks OpenAI saem **no ritmo próprio do modelo**, sem nenhuma dessas pausas aplicadas (a segmentação de pausa vive dentro do `KokoroSpeaker`). Mesmo que o timbre fosse idêntico, a **velocidade de narração muda** a cada troca de motor. Ninguém mediu ou ouviu isso ainda.

### 5.8 Backlog operacional conhecido (não bloqueia, mas cresce)

- `delete_book` deixa **capítulos órfãos** no banco (89 de 90 linhas medidas em 13/08 — item 58 do backlog).
- `piper_speaker.py` continua com **0 bytes** (o `cloud_speaker.py` vazio foi apagado na OS-055; o piper ficou).
- Livros processados antes da OS-019/020/036 continuam com áudio errado e **precisam de reenvio manual**.
- **Camada de produto (multitenancy):** declarada por você como o próximo passo, nada implementado — sem usuário, conta, plano ou isolamento de arquivos. Enquanto ela não existe, os três níveis do produto vivem em `config.yaml` global.

## 6. Os trade-offs, um a um

### 6.1 O teto do Kokoro é o modelo, não o texto (o trade-off central)

Decisão #23, registrada e reconfirmada pela OS-054: **melhorar texto não faz o Kokoro atuar.** O Kokoro-82M não tem controle de emoção nem de ênfase; a pausa de 750 ms na exclamação (OS-045) é um "paliativo por tempo" — a exclamação sai com a mesma melodia de uma afirmação. Todo o polimento dos últimos dias (OS-044, 045, 049, 050, 054) melhora respiro e pronúncia do nível gratuito, mas a expressividade de `!`/`?` **só vem de trocar o motor**. É por isso que o roteamento é a feature certa — e também por isso ela não pode mais ficar esperando: sem ela, todo o resto foi preparação de palco.

### 6.2 Cobertura × custo × trocas de voz (a tabela do limiar)

| Limiar | % do livro no pago | US$/livro | Trocas de voz |
|---|---|---|---|
| 1 | 37,1% | 3,19 | 86 |
| **3 (padrão)** | **9,2%** | **0,79** | **32** |
| 5 | 4,3% | 0,37 | 17 |
| Livro inteiro | 100% | 8,58 | 0 |

**Custo do trade-off, já declarado na OS-056:** uma pergunta isolada num chunk de prosa (abaixo do limiar) fica sem melhoria nenhuma — melhorá-la custaria uma troca de timbre que você já constatou ser pior que o defeito. É o trade-off certo, mas precisa estar na expectativa: o roteamento melhora **trechos densos** (diálogo, exclamação retórica em sequência), não toda pontuação expressiva do livro.

### 6.3 Custo medido uma única vez × cobrança por token

O `cost_per_char` da OpenAI (1,608e-05) vem de **uma medição** (US$ 0,015 / 933 chars, 11/08). Mas a `gpt-4o-mini-tts` cobra por **token de áudio**, não por caractere — texto com mais número, pontuação ou palavras raras tokeniza diferente. A estimativa da OS-042 pode desviar da fatura real em textos de perfil diferente do medido. Mitigação: recalibrar com 2–3 livros reais quando houver crédito, e guardar o custo real por livro para refinar a constante.

### 6.4 Resiliência × consistência de voz

Falha **transitória** do motor pago degrada **aquele chunk** para o Kokoro (o livro completa, mas a narração mistura motores além do planejado — potencialmente no trecho mais dramático). Falha **permanente** para o livro com aviso (decisão sua de 13/08). É o equilíbrio certo entre disponibilidade e "não enganar o usuário", mas note a assimetria: o caso que mais vai acontecer em produção (limite de taxa por minuto, instabilidade de rede) é justamente o que degrada — então a experiência "quase sempre OpenAI nos trechos densos" depende de a conta ter folga de rate limit.

### 6.5 Prosódia por LLM × prosódia por motor (sobreposição)

A OS-054 (passe de pontuação via LLM) e a OS-056 (motor expressivo) atacam **o mesmo sintoma** por caminhos diferentes: uma reorganiza a pontuação para o Kokoro respirar melhor; o outro troca o motor onde a pontuação já pede atuação. Ligados juntos, o nível médio **dobra de custo** (dois passes de LLM) para melhorar ~13% das frases — e nos 9% de chunks roteados o passe de prosódia é pago e descartado. Decisão de produto pendente: provavelmente são **alternativas**, não complementos — prosódia LLM é o "premium do pobre" (quem não paga TTS cloud), roteamento é o real. Vale documentar essa escolha em vez de deixar os dois ligados por acidente.

### 6.6 "Local = grátis" só vale no uso pessoal

Registrado no backlog (item 53) e continua valendo para o plano de "pessoas comuns": Kokoro/Chatterbox têm custo zero **na sua RTX 3060**. Alugada, a GPU custa ~US$ 2,30/livro (Chatterbox em nuvem) e **uma GPU processa um livro por vez** — 10 usuários simultâneos = fila de 76 h ou 10 GPUs. O roteamento híbrido é, na verdade, a resposta arquitetural mais elegante para isso: o volume fica no motor local e só 9% vai para a nuvem, que escala sozinha. Mas quando o produto virar SaaS, a conta honesta do "gratuito" precisa aparecer no preço do plano.

### 6.7 Escopo da expressividade: só `!` e `?`

Ironia, diálogo, caixa alta, reticências, citações longas — nada disso roteia. Escopo declarado e correto para a primeira versão, mas é o próximo degrau óbvio: o mesmo mecanismo (contagem → limiar → rota) aceita novos sinais sem redesenho. Junto com isso, `instructions` hoje é **uma só para todos os chunks roteados**; calibrar instrução por tipo de trecho (pergunta × exclamação × diálogo) ficou explicitamente fora da OS-056 e é a melhoria de maior alavanca depois da validação — e continua de graça.

## 7. Por que a sensação de "rodar em círculos"

Lendo o histórico, o loop não é técnico — é este ciclo:

```
implementa (com mocks, testes verdes)
  → vai testar de verdade
    → bate num muro não-código (credencial, cota, dois processos, venv)
      → volta para o código para melhorar o tratamento do muro
        → testes verdes de novo
          → mas o áudio real nunca saiu
```

As evidências: o premium está bloqueado em credencial desde 06/08 (OS-041); quando a chave apareceu, bateu em cota esgotada (ontem, 21:26); os dois últimos commits são **semântica de erro**, não avanço de feature; e o branch pronto está sem PR, sem relatório e com o `PROJECT_STATE.md` atrasado — ou seja, o processo que garante a qualidade também está segurando o trabalho refém. Some-se a isso ~10 OSs em ~10 dias polindo o motor gratuito enquanto o salto real (trocar o motor nos trechos que importam) esperava o muro de credencial: muita atividade visível, pouca mudança audível.

A saída do círculo é pequena e concreta, não é replanejar o produto:

## 8. Recomendações priorizadas

1. **Corrigir o bug voz × roteamento (5.1)** — antes de qualquer teste real com livro que tenha voz escolhida. Uma OS pequena: catálogo de vozes da OpenAI + fallback para a voz configurada + teste cruzado.
2. **Resolver o crédito da OpenAI** (ou decidir explicitamente congelar o premium e focar 100% no gratuito por um ciclo — as duas saídas são legítimas; ficar no meio é o que alimenta o círculo).
3. **Configurar `OPENAI_INSTRUCTIONS`** no `.env` (texto já sugerido no `.env.example`) — custo zero, é a expressividade que o roteamento existe para entregar.
4. **Fechar o ciclo OS-055/056:** PR + dois relatórios + `PROJECT_STATE.md` + a amostra de áudio real com troca de motor (critério de aceite pendente). Ouvir você mesmo as 32 trocas é a validação que destrava tudo.
5. **Decidir a política do nível médio × roteamento** (6.5): recomendo documentar que são alternativas — prosódia LLM para quem não paga TTS, roteamento para quem paga — e não rodar LLM de prosódia em chunk destinado à OpenAI.
6. **Auto-aprovação de custo abaixo de um limiar** (ex.: < US$ 1) para não travar todo livro em `pending_confirmation` — decisão sua, implementação pequena na trava da OS-042.
7. **Faxina rápida:** capítulos órfãos no `delete_book` (uma linha + um teste) e apagar `piper_speaker.py` (0 bytes).
8. **Só então** abrir a OS da camada de produto (multitenancy), que é o próximo passo declarado — com a vantagem de que, aí sim, o roteamento já será uma feature real e ouvida, não uma promessa.

---

### Apêndice — evidências desta análise

- Branch `os/055-openai-speaker`: `git log main..HEAD` → 11 commits (055 Red/Green, 056 Red/Green, 2 fix de 13/08 à noite); `gh pr list` → nenhum PR aberto.
- Suíte: `pytest` → **399 passed** em 14,6 s.
- Banco local: 1 livro (`teste-expressividade2.pdf`, `ready`, custo confirmado US$ 0,0177); `audio_chunks` → 2 chunks, ambos `engine_used = kokoro`.
- `.env`: `OPENAI_API_KEY` e `LLM_API_KEY` definidas; `PROSODY_API_KEY`, `OPENAI_INSTRUCTIONS`, `OPENAI_TTS_VOICE` ausentes.
- Números do limiar: `docs/os/OS-056-roteamento-por-expressividade.md` seção 5 (medição em 230 chunks reais).
- Teto do Kokoro: `docs/PROJECT_STATE.md` decisão #23 e `docs/os/OS-054-preparacao-prosodica.md` seção 4.
