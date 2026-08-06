# OS-038 — Relatório de entrega

**Data:** 2026-08-06
**Branch:** os/038-ajudante-llm
**Commit(s) relevante(s):** (test: Red), ff1c73e (feat: Green)

## 1. Resumo do que foi feito

Contrato de plugin `TextNormalizer` novo, com `NoOpNormalizer` (padrão — não toca a rede, não custa nada) e `LLMNormalizer` via **endpoint compatível com OpenAI** (`base_url`/`model` em `config.yaml`, chave sempre de variável de ambiente). A normalização é **opt-in por livro** (`Book.normalize_text`, campo no upload); sem opt-in o normalizador **nem é construído**. Guarda-corpo em três camadas contra alteração do texto do autor. `estimate_cost()` passou a somar o custo do normalizador, para o nível médio não escapar da trava de custo da OS-042.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit "Red" antes de `ff1c73e`)
- [x] Todos os testes da OS passam localmente — 275 pass, 0 fail
- [x] Nenhum teste existente quebrou (258 anteriores + 17 novos = 275)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — `TextNormalizer` documentado na seção 4.4 **antes** de implementar
- [x] Nenhuma chamada real a API paga dentro dos testes — `_call_api()` é o único ponto que toca a rede e está sempre mockado
- [x] Type hints e docstring de uma linha em toda função pública nova
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-038-report.md`
- [x] PR aberto contra o branch principal

### DoD específico da OS (seção 4)

- [x] Contrato `TextNormalizer` documentado em `ARQUITETURA.md` antes de implementar — seção 4.4 nova
- [x] Livro sem opt-in tem comportamento idêntico ao de hoje, sem nenhuma chamada de rede — `test_book_without_optin_never_calls_normalizer` usa um normalizador que **levanta exceção se chamado**; o teste prova que ele nunca é tocado
- [x] Livro com opt-in tem o texto normalizado antes da síntese — `test_optin_book_has_text_normalized_before_synthesis`
- [x] Saída que diverge demais é descartada em favor do original, com log — três testes (encolhe, explode, preâmbulo)
- [x] Falha de rede/API degrada para o texto original, sem marcar o livro como `error` — `test_llm_network_failure_falls_back_to_original_text`
- [x] Um mesmo chunk não é reenviado à LLM — `test_same_text_is_not_resent_to_the_llm`
- [x] Nenhuma chamada real a API paga na suíte
- [ ] **Custo real medido em um livro de verdade** — **pendente**: exige a chave do dono. O custo foi **estimado** a partir de um livro real do acervo (seção 4) e o script de validação está pronto (`scripts/validate_normalizer.py`); a medição real é o passo que o dono executa.

## 3. Testes escritos

17 testes em `tests/unit/test_normalizer.py`, agrupados por responsabilidade:

| Grupo | Testes |
|---|---|
| Contrato | `test_normalizer_cannot_be_instantiated_directly`, `test_noop_normalizer_returns_text_unchanged`, `test_noop_normalizer_costs_nothing` |
| Integração no pipeline | `test_book_without_optin_never_calls_normalizer`, `test_optin_book_has_text_normalized_before_synthesis` |
| Guarda-corpo | `test_llm_output_used_when_within_threshold`, `test_llm_output_discarded_when_text_shrinks_too_much`, `test_llm_output_discarded_when_text_explodes`, `test_llm_output_discarded_when_model_adds_preamble`, `test_llm_network_failure_falls_back_to_original_text`, `test_llm_empty_response_falls_back_to_original` |
| Cache | `test_same_text_is_not_resent_to_the_llm` |
| Custo / config | `test_llm_normalizer_declares_cost_per_char`, `test_llm_normalizer_reads_api_key_from_environment`, `test_missing_api_key_degrades_to_noop`, `test_cost_estimate_includes_normalizer_when_optin`, `test_cost_estimate_without_optin_ignores_normalizer_cost` |

Confirmar: commit "Red" antes do "Green"? [x] Sim — o Red falhou com `ModuleNotFoundError: No module named 'plugins.normalizers'`.

**Um teste meu estava errado e foi corrigido durante o Green**, registrado por transparência: `test_optin_book_has_text_normalized_before_synthesis` configurava `normalizer="noop"` mas esperava o comportamento do `llm`. O erro era do teste, não da implementação — a semântica correta (e que ficou) é: **o livro opta por normalizar; a config decide qual normalizador**. O teste foi ajustado para configurar `normalizer="llm"`, sem afrouxar o que ele prova.

## 4. Custo estimado

Medido sobre um livro real do acervo (O Programador Pragmático, 648.877 caracteres ≈ 216 mil tokens de entrada, saída de tamanho semelhante):

| Patamar de preço | Custo por livro |
|---|---|
| LLM barata (~US$ 0,15/1M entrada, 0,60/1M saída) | **~US$ 0,16** |
| LLM média (~US$ 1,00/1M entrada, 3,00/1M saída) | **~US$ 0,87** |

Para comparação, o **premium** (TTS cloud, OS-041) custa **US$ 8–107** no mesmo livro. A normalização é **duas ordens de grandeza mais barata** — é isso que torna o nível médio viável comercialmente.

Ressalva: os preços de LLM acima são estimativa por ordem de grandeza, **não** levantamento oficial como o que a OS-041 fez para TTS. Antes de virar preço de plano, merecem a mesma pesquisa com fonte e data.

## 5. Decisões de implementação documentadas

**(a) Endpoint compatível com OpenAI, não SDK de um provedor.** `_call_api()` faz `POST {base_url}/chat/completions` com `urllib` da stdlib — **nenhuma dependência nova**. DeepSeek, Groq, Together, OpenRouter e a própria OpenAI expõem esse mesmo formato, então trocar de provedor é mudar `config.yaml`, não código. Mantém a filosofia de baixa infraestrutura do projeto (decisões #12/#13).

**(b) Guarda-corpo em três camadas, e a janela é assimétrica.** Este é o ponto que torna a OS aceitável — o risco não é o modelo ser fraco, é ele alterar o texto do autor num audiobook, onde o ouvinte não tem como perceber:

1. **Tamanho, com janela assimétrica** — normalizar **expande** legitimamente ("R$ 50" → "cinquenta reais"), então crescer até 2× é aceitável, mas encolher abaixo de 85% é sinal de resumo. Uma janela simétrica ou deixaria passar resumo, ou barraria normalização legítima.
2. **Preâmbulo conversacional** — "Aqui está o texto formatado:", "Claro!", "Sure," etc. É o modo de falha mais comum de modelos pequenos, e **passaria direto pelo teste de tamanho** por acrescentar poucos caracteres.
3. **Fallback total** — rede fora, resposta vazia, chave ausente ou qualquer exceção devolvem o texto original. O contrato exige que `normalize()` **nunca levante**.

**(c) Sem opt-in, o normalizador nem é construído.** `_build_normalizer()` só é chamado quando `normalize=True`. O nível simples não paga nada — nem latência, nem construção de objeto, nem risco.

**(d) A normalização roda antes da divisão por limite do engine.** Ela muda o tamanho do texto (números por extenso crescem), então medir antes daria orçamento errado — mesma razão pela qual o mapa fonético da OS-037 roda antes da divisão por fonemas.

**(e) Cache por texto, não por `sequence`.** Chaveado pelo conteúdo, funciona mesmo se a numeração mudar. Vale notar que a retomada da OS-022 **já** evita a maior parte do reenvio (chunks persistidos entram em `skip_sequences` e nunca chegam ao normalizador); o cache cobre o caso restante — chunk normalizado cuja síntese falhou.

**(f) `estimate_cost()` ganhou o parâmetro `normalize`.** Sem isso, um livro do nível médio teria estimativa zero e escaparia da trava de custo da OS-042 — dois testes cobrem os dois lados.

## 6. Desvios do escopo original

Nenhum desvio de escopo. Dois acréscimos que a OS pedia e ficaram registrados aqui:

- **`scripts/validate_normalizer.py`** — a OS exige validação com o provedor real antes de confiar. O script roda casos difíceis (moeda, abreviação, número, sigla, prosa longa) e mostra antes/depois, mas **não** é executado por mim: exige a chave do dono. Nenhuma chamada paga foi feita nesta OS.
- **`RUNBOOK.md` seção 6.2** — como ligar o nível médio, o aviso da coluna nova (`normalize_text`) com o `ALTER TABLE`, e o que esperar do guarda-corpo.

## 7. Dúvidas / bloqueios

Nenhum bloqueio. Duas pendências para o dono do projeto:

1. **Validar o provedor com a chave real** antes de usar em livro inteiro:
   ```bash
   export LLM_API_KEY='sua-chave'
   venv/bin/python scripts/validate_normalizer.py \
       --base-url https://api.deepseek.com/v1 --model deepseek-chat
   ```
   Conferir as três coisas que a OS pede: `R$ 50` → "cinquenta reais" (não "dólares"), nada de conteúdo sumiu, e nenhuma saída com preâmbulo. **Se o guarda-corpo descartar muita coisa, o modelo não serve para este uso** — e isso é informação valiosa, não falha da implementação.
2. **`ALTER TABLE` na coluna `normalize_text`** antes do primeiro upload pós-merge (comando no `RUNBOOK.md`), ou apagar o `books.db`.

## 8. Link do PR

https://github.com/dinei84/listening/pull/39
