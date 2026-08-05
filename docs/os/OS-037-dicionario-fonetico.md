# OS-037 — Dicionário de substituição fonética local

## 1. Objetivo

O Kokoro fonemiza português com **espeak-ng** (motor por regras), não com um G2P de léxico como faz no inglês — daí a pronúncia aproximada que o dono do projeto descreveu como "mistura com português de Portugal" (risco registrado no `PROJECT_STATE.md` seção 6; medido: "segurança" vira `sˌeɡuɾˈɐ̃ŋsæ`, terminando em `æ`, vogal que não existe em português). Não há parâmetro que conserte isso de forma geral. Esta OS entrega o remédio pontual: um mapa local de substituição para os termos que erram sempre — nomes próprios, siglas e jargão técnico.

Proposta originada de uma sugestão externa (Etapa 4 do documento trazido pelo dono do projeto), avaliada e mantida por ser **local, determinística e sem custo de API** — ao contrário da Etapa 3, que virou a OS-038.

## 2. Escopo

**Dentro do escopo:**

- Arquivo de dados versionado com o mapa de substituições (`JSON` ou `YAML` — o projeto já usa `yaml` em `config.yaml`; decisão de implementação, documentar). Formato: chave = termo como aparece no texto, valor = grafia que faz o G2P acertar.
- Aplicação do mapa **antes** da fonemização, no `KokoroSpeaker`. Ponto natural: junto do tratamento que a OS-034 já faz em `synthesize()`, antes de medir/dividir por orçamento de fonemas.
- Substituição deve respeitar **fronteira de palavra** (não trocar dentro de outra palavra) e ser **case-insensitive na busca**, preservando o resto do texto intacto.
- Mapa inicial pequeno e honesto: só entradas verificadas de verdade (ex: siglas comuns em livros técnicos). **Não** inventar dezenas de entradas não testadas — cada uma deve ter sido conferida ouvindo ou comparando o G2P antes/depois.
- Documentar no `RUNBOOK.md` como adicionar uma entrada nova, já que isso é manutenção recorrente do dono do projeto, não de agente.

**Fora do escopo:**
- Corrigir o sotaque geral do português — é limitação do espeak-ng, não tem conserto por dicionário (só melhora termo a termo).
- Qualquer chamada a LLM/API paga — é a OS-038.
- Trocar de engine TTS ou adicionar `Speaker` novo para português. **Registrar no relatório** que esse continua sendo o único caminho para resolver o sotaque de forma ampla, e que é decisão do dono (envolve provavelmente TTS pago — `ARQUITETURA.md` seção 6).
- Junção de linhas — é a OS-035.

## 3. Contratos envolvidos

Nenhum contrato de `Extractor`/`Speaker`/`JobQueue` muda: a substituição acontece **dentro** do `KokoroSpeaker`, antes de falar com o engine. Um `Speaker` futuro pode ou não usar o mesmo mapa — se um dia houver um segundo, avaliar mover o mapa para fora do plugin (mesma observação já registrada na OS-025 sobre `LANG_CODE_BY_LANGUAGE`).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Termos do mapa são substituídos antes da fonemização, respeitando fronteira de palavra
- [ ] Texto sem nenhum termo do mapa passa inalterado (comportamento idêntico ao de hoje)
- [ ] Substituição não altera a contagem de `AudioChunk` nem a `sequence` — continua um pedaço de `chunk_text()` por `AudioChunk` (regressão OS-021/022/024/032/034)
- [ ] Mapa vazio ou arquivo ausente não derruba a síntese (degrada para "sem substituição")
- [ ] Cada entrada do mapa inicial tem evidência de melhora registrada no relatório (G2P antes/depois)
- [ ] `RUNBOOK.md` explica como adicionar entradas
- [ ] Nenhuma chamada de rede ou API paga na suíte

## 5. Testes exigidos (mínimo)

- `test_phonetic_map_replaces_known_term_before_synthesis`
- `test_phonetic_map_respects_word_boundaries`
- `test_phonetic_map_is_case_insensitive`
- `test_text_without_mapped_terms_is_unchanged`
- `test_missing_or_empty_map_does_not_break_synthesis`
- `test_phonetic_map_does_not_change_audio_chunk_count` (regressão)

`_build_pipeline()` continua mockado em todos os testes automatizados (padrão desde a OS-004).

## 6. Verificação empírica exigida

Para cada entrada do mapa inicial, colar no relatório a saída do G2P real (`kokoro.KPipeline(..., model=False).g2p(...)`) antes e depois da substituição, mostrando que a fonemização melhorou. Entrada sem essa evidência não entra no mapa.

## 7. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-037-report.md`.*
