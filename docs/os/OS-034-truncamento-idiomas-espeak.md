# OS-034 — Corrige truncamento silencioso de áudio em idiomas não-ingleses

## 1. Objetivo

Achado em uso real (relato do dono do projeto: "o português às vezes engole pontuação") e confirmado por medição: **áudio em português está sendo cortado silenciosamente**, não é impressão nem problema de pontuação. Uma frase de 557 caracteres sem `.!?` internos gera 661 fonemas e o Kokoro descarta os 151 excedentes (22,8% da frase), emitindo apenas um `logger.warning` — o áudio termina no meio da palavra. Esta OS elimina esse truncamento.

## 2. Contexto técnico medido (não repetir a investigação)

**A causa é uma assimetria dentro do próprio Kokoro** (`KPipeline.__call__`, `kokoro/pipeline.py`):

- **Inglês (`lang_code` `a`/`b`)**: usa `en.G2P` (misaki) + `en_tokenize()`, que divide o texto respeitando o limite de 510 fonemas. Medido: frase de 496 caracteres → 2 pedaços de 504 e 19 fonemas, **nada perdido**.
- **Demais idiomas (`e`/`f`/`h`/`i`/`p` — via `EspeakG2P`)**: divide só em `[.!?]` com alvo de 400 caracteres. Se **uma única frase** já passa disso, ela é enviada inteira e, se o G2P passar de 510 fonemas, o código faz `logger.warning('Truncating...'); ps = ps[:510]` — **corta e segue**.

**Densidade fonêmica medida neste ambiente** (mesmo texto equivalente em cada idioma):

| Idioma | Fonemas por caractere |
|---|---|
| Inglês | 0,88 |
| Português (pt-br) | **1,19** |

Ou seja, ~510 fonemas ≈ **430 caracteres** de português. Frases acima disso são truncadas.

**Armadilha importante — baixar `DEFAULT_MAX_CHARS` NÃO resolve.** Verificado: `chunk_text()` nunca corta uma sentença ao meio (é o contrato dele desde a OS-008), então a frase de 557 caracteres continua num pedaço só mesmo com `max_chars=200`. A correção precisa saber dividir **uma sentença que sozinha estoura o orçamento**.

**O comentário atual em `processing/chunker.py` está desatualizado** e ajudou a esconder o problema: ele afirma que "o Kokoro agora lida com o limite de fonemas internamente" (herdado da OS-019). Isso é verdade **só para inglês**. Corrigir o comentário faz parte desta OS.

**Custo:** pela OS-031 (decisão #19/#20), tamanho de chunk **não afeta o throughput** — o custo é proporcional ao áudio gerado, não ao número de chamadas. Dividir mais é gratuito em performance.

## 3. Escopo

**Dentro do escopo:**

- Garantir que **nenhum texto enviado ao Kokoro ultrapasse o limite de 510 fonemas**, em qualquer idioma. Onde implementar é decisão do agente, mas a recomendação é `plugins/speakers/kokoro_speaker.py::synthesize()`, porque:
  - é onde o conhecimento do engine (limite de fonemas, idioma efetivo) já mora;
  - `synthesize()` **já concatena** vários pedaços de áudio num só (`torch.cat(audio_parts)`), então dividir mais **não** muda a granularidade de `AudioChunk`;
  - mantém `processing/chunker.py` agnóstico de engine, como sempre foi.
- A divisão de uma sentença grande demais deve preferir fronteiras naturais, em ordem de preferência: `;` / `:` / `,` → depois espaço entre palavras. **Nunca cortar no meio de uma palavra.**
- O orçamento deve ser **medido, não adivinhado**: o pipeline do Kokoro expõe `g2p()`, e contar fonemas custa ~1,3% do tempo de um chunk (medido na OS-031). Preferir medir o resultado real do G2P a estimar por caracteres — a densidade varia por idioma (1,19 em pt, provavelmente diferente em fr/hi/it).
- Corrigir o comentário desatualizado de `processing/chunker.py` (ver seção 2).
- Registrar no `PROJECT_STATE.md` (seção 6, riscos) a **limitação de qualidade inerente do espeak-ng**, que esta OS **não** resolve — ver seção 5.

**Fora do escopo:**
- Melhorar a *qualidade/sotaque* da voz em português — é limitação do espeak-ng, não tem conserto por parâmetro (seção 5).
- Trocar de engine TTS ou adicionar um `Speaker` novo para português.
- Mudar `DEFAULT_MAX_CHARS` ou o contrato de `chunk_text()` (que continua "nunca corta sentença ao meio" — a divisão fina desta OS acontece depois, no Speaker, sem virar `AudioChunk` separado).
- Mudar a numeração/granularidade de `AudioChunk` — **um pedaço de `chunk_text()` continua virando exatamente um `AudioChunk`**, com `sequence` global e contínua. Quebrar isso invalidaria a retomada (OS-022), a barra de progresso (OS-024) e a preempção (OS-032).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Nenhum texto enviado ao Kokoro excede 510 fonemas, em qualquer idioma
- [ ] Uma frase longa em português (sem `.!?` internos) que hoje é truncada passa a ser sintetizada **por inteiro** — verificado comparando a contagem de fonemas efetivamente sintetizados com a do texto original, sem perda
- [ ] Nenhuma palavra é cortada ao meio pela divisão
- [ ] Um pedaço de `chunk_text()` continua produzindo **exatamente um** `AudioChunk` (`sequence` inalterada) — regressão das OS-021/022/024/032
- [ ] Comportamento em inglês inalterado (o caminho `en_tokenize` já resolvia; não introduzir divisão redundante que mude o áudio existente)
- [ ] Comentário desatualizado de `processing/chunker.py` corrigido
- [ ] `PROJECT_STATE.md` registra a limitação de qualidade do espeak-ng como risco conhecido em aberto
- [ ] Nenhuma chamada de rede ou API paga na suíte de testes

## 5. Limitação conhecida que esta OS NÃO resolve (registrar, não tentar consertar)

O Kokoro usa `pt-br` corretamente (`LANG_CODES['p'] == 'pt-br'`), mas fonemiza português com **espeak-ng** (motor baseado em regras), enquanto o inglês usa um G2P com léxico (`misaki[en]`). O resultado é aproximado: "segurança" é fonemizado como `sˌeɡuɾˈɐ̃ŋsæ`, terminando em `æ` — vogal que **não existe em português**. É isso que o dono do projeto percebeu como "mistura com português de Portugal".

Não há parâmetro que corrija: é o limite do suporte a português do modelo. O caminho real seria um `Speaker` alternativo só para esse idioma — possível pela arquitetura de plugins (decisão #1), mas fora do escopo aqui e provavelmente envolvendo TTS pago (o que exigiria decisão do dono, ver `ARQUITETURA.md` seção 6, regras de custo). **Registrar como risco em aberto, sem prometer solução barata.**

## 6. Testes exigidos (mínimo)

- `test_kokoro_speaker_splits_oversized_sentence_before_synthesis` — frase longa em português não chega ao engine acima de 510 fonemas
- `test_kokoro_speaker_never_splits_mid_word`
- `test_kokoro_speaker_returns_single_audio_chunk_for_oversized_text` (regressão: continua **um** `AudioChunk`)
- `test_kokoro_speaker_short_text_unchanged` (regressão: texto curto não passa por divisão nenhuma)
- `test_chunk_text_contract_unchanged` (regressão da OS-008: `chunk_text` continua sem cortar sentença)

`_build_pipeline()` continua sendo o único ponto que toca o engine e **deve seguir mockado** em todos os testes automatizados (padrão desde a OS-004). Para verificar a contagem de fonemas sem carregar o modelo, lembrar que `kokoro.KPipeline(lang_code=..., model=False)` constrói só o G2P — mas isso é ferramenta de *investigação manual*, não deve entrar na suíte automatizada se implicar download de modelo.

Local sugerido: `tests/unit/speakers/test_kokoro_speaker.py`, `tests/unit/test_chunker.py`.

## 7. Verificação empírica exigida (fora da suíte automatizada)

Como o achado veio de audição real e os testes automatizados **nunca detectaram** isso (mesma lição institucional da decisão #14: os testes só verificam propriedades estruturais do áudio, nunca o conteúdo), registrar no relatório uma verificação manual com o Kokoro real:

- sintetizar a frase longa em português de antes e de depois da correção;
- comparar as durações (a versão corrigida deve ser mensuravelmente maior);
- confirmar por audição que a frase termina completa, não no meio da palavra.

## 8. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-034-report.md` (template em `docs/report/REPORT_TEMPLATE.md`).*
