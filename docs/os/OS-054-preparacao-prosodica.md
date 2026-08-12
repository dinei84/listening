# OS-054 — Preparação prosódica com guarda-corpo próprio

## 1. Objetivo

Um segundo passe de LLM, separado do normalizador de notação, que ajusta **só a pontuação** do texto — e um guarda-corpo que verifique isso de forma determinística, em vez de medir tamanho.

## 2. Correção de premissa registrada antes do escopo

Em 11/08/2026 foi afirmado, com base em 42 frases de duas amostras pequenas, que **prosa técnica tem ~0% de frases com `!` ou `?`**. Essa conclusão foi usada para argumentar que o roteamento híbrido (item 54 do backlog) "quase nunca dispararia".

**A medição em escala desmente isso.** Nos capítulos 1 a 4 do "Programador Pragmático" — 2.327 frases reais:

| | Frases | % |
|---|---|---|
| com `?` apenas | 190 | 8,2% |
| com `!` apenas | 20 | 0,9% |
| **total expressivas** | **211** | **9,1%** |

Uma frase em cada onze. As amostras anteriores eram pequenas demais para sustentar a conclusão, e o item 54 do backlog deve ser relido com este número.

## 3. O problema de respiro é menor do que se supunha

Medido nas mesmas 2.327 frases, pelo maior trecho sem vírgula, ponto e vírgula ou dois-pontos:

| Maior trecho sem pausa | Frases | % |
|---|---|---|
| até 120 chars | 2.012 | 86,5% |
| 120–200 chars | 294 | 12,6% |
| 200–300 chars | 20 | 0,9% |
| acima de 300 | 1 | 0,04% |

**86,5% das frases já respiram bem.** O caso severo é 0,9%. Isso precisa estar claro antes de a OS ser executada: o ganho desta OS é concentrado nos ~13% de faixa média, não é uma correção ampla.

O pior caso encontrado (362 caracteres sem pausa) revelou outra coisa: é uma **lista** sendo lida como frase corrida (`"gerou: As instruções SQL... Arquivos de dados simples..."`). Isso é problema de estrutura, não de pontuação — pertence à linha da OS-049/050, não a esta.

## 4. Escopo

Alterados:

- `plugins/normalizers/prosody_normalizer.py` — novo, com prompt e guarda-corpo próprios.
- `plugins/registry.py` — registro do normalizador novo.
- `core/config.py` e `config.yaml` — bloco de configuração próprio.
- `core/pipeline.py` — encadear os dois normalizadores.
- Testes correspondentes.

Fora de escopo:

- **Alterar o `SYSTEM_PROMPT` da OS-038.** Ele trata de notação e continua como está; o motivo de haver dois passes é justamente terem guarda-corpos incompatíveis (seção 6).
- **Criar entonação.** O Kokoro-82M não tem controle de emoção nem de ênfase (decisão #23). Esta OS reorganiza pontuação; o teto é o modelo.
- **Reescrever, resumir ou corrigir o texto do autor.** É o que o guarda-corpo existe para impedir.

## 5. Contratos envolvidos

Nenhum contrato muda. `TextNormalizer` (`normalize(text) -> str`, `cost_per_char`) já basta, e o encadeamento é feito por um **`ChainNormalizer`, que é ele mesmo um `TextNormalizer`** — compõe uma lista e soma os `cost_per_char`.

Como a trava de custo da OS-042 já multiplica caracteres por `normalizer.cost_per_char`, a soma da cadeia entra na estimativa **automaticamente**, sem tocar em `estimate_cost`.

**Ordem obrigatória: notação primeiro, prosódia depois.** A notação expande números por extenso, ou seja, muda palavras; a prosódia deve preservá-las. Rodar prosódia sobre o texto já normalizado é o único jeito de o guarda-corpo da seção 6 fazer sentido.

## 6. O guarda-corpo, que é o coração da OS

O da OS-038 mede **divergência de tamanho** (janela `[0.85, 2.0]`). Para preparação prosódica isso é a métrica errada: inserir vírgulas quase não muda o tamanho, então **qualquer reescrita de palavras passaria batido** desde que o comprimento se mantivesse.

O guarda-corpo desta OS verifica a única coisa que importa: **a sequência de palavras precisa ser idêntica.**

```
aceitar  ⟺  tokens(original) == tokens(saída)
```

onde `tokens` remove toda pontuação, colapsa espaços e compara sem diferenciar maiúsculas — porque dividir uma frase legitimamente troca `", e"` por `". E"`.

Consequências, e são desejadas:

- **Pode**: inserir vírgula, trocar vírgula por ponto (dividindo frase longa), remover pontuação supérflua.
- **Não pode**: acrescentar conectivo, trocar palavra, resumir, reordenar. Qualquer um desses **rejeita** e devolve o original.

Isso é determinístico e verificável em teste, sem chamar a LLM — diferente do guarda-corpo de tamanho, que aceita por probabilidade.

## 7. Custo

O normalizador da OS-038 custa ~US$ 0,16–0,87 por livro. Um segundo passe sobre o mesmo texto **aproximadamente dobra** isso. A cadeia soma os custos e a trava da OS-042 os enxerga, mas o dono deve saber que ligar esta OS é dobrar o custo do nível médio para melhorar ~13% das frases.

## 8. Critérios de aceite

- [ ] Saída que só muda pontuação é aceita
- [ ] Saída que troca uma palavra é rejeitada, devolvendo o original
- [ ] Saída que acrescenta palavra é rejeitada
- [ ] Saída que remove palavra é rejeitada
- [ ] Divisão de frase (`", e"` → `". E"`) é aceita, apesar da maiúscula
- [ ] Falha de rede devolve o original, sem derrubar o livro (como a OS-038)
- [ ] `ChainNormalizer` aplica os normalizadores na ordem configurada
- [ ] `cost_per_char` da cadeia é a soma dos elos
- [ ] A estimativa da OS-042 reflete a cadeia sem alteração em `estimate_cost`
- [ ] Prosódia desligada (padrão) não faz nenhuma chamada de rede
- [ ] Nenhum teste existente quebra (355 hoje)

## 9. Testes exigidos (mínimo)

- `test_prosody_accepts_punctuation_only_change`
- `test_prosody_rejects_changed_word`
- `test_prosody_rejects_added_word`
- `test_prosody_rejects_removed_word`
- `test_prosody_accepts_sentence_split_with_capitalization`
- `test_prosody_returns_original_on_network_failure`
- `test_chain_applies_normalizers_in_order`
- `test_chain_cost_is_the_sum_of_links`
- `test_estimate_cost_includes_chain_cost`
- `test_prosody_disabled_by_default_makes_no_network_call`

## 10. Relatório

Ver `docs/report/OS-054-report.md`.
