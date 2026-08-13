# OS-054 — Relatório de entrega

**Data:** 2026-08-13
**Branch:** os/054-preparacao-prosodica
**Commit(s) relevante(s):** c1a0d10 (test: Red), 7195e19 (feat: Green), f101f45 (style)

## 1. Resumo do que foi feito

Segundo passe de LLM, separado do normalizador de notação (OS-038), que **só ajusta a pontuação** do texto para respiro. O diferencial é o **guarda-corpo próprio**: em vez de medir divergência de tamanho (a métrica errada para pontuação, que quase não muda comprimento), ele exige que a **sequência de palavras seja idêntica** — determinístico e verificável sem chamar a LLM. Os dois passes são encadeados por um `ChainNormalizer` (ele mesmo um `TextNormalizer`) na ordem obrigatória **notação → prosódia**, e a trava de custo da OS-042 enxerga a cadeia automaticamente pela soma dos `cost_per_char`.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit "Red" c1a0d10 antes de `7195e19`)
- [x] Todos os testes da OS passam localmente — 10 novos, 365 no total, 0 fail
- [x] Nenhum teste existente quebrou (355 anteriores + 10 novos = 365)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — reusa o contrato `TextNormalizer` (seção 4.4) sem alterá-lo; `ChainNormalizer` é um `TextNormalizer` adicional
- [x] Nenhuma chamada real a API paga dentro dos testes — `_call_api()` é o único ponto que toca a rede e está sempre mockado
- [x] Type hints e docstring de uma linha em toda função pública nova
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-054-report.md`
- [x] PR aberto contra o branch principal

### DoD específico da OS (seção 8)

- [x] Saída que só muda pontuação é aceita — `test_prosody_accepts_punctuation_only_change`
- [x] Saída que troca uma palavra é rejeitada, devolvendo o original — `test_prosody_rejects_changed_word`
- [x] Saída que acrescenta palavra é rejeitada — `test_prosody_rejects_added_word`
- [x] Saída que remove palavra é rejeitada — `test_prosody_rejects_removed_word`
- [x] Divisão de frase (`, e` → `. E`) é aceita, apesar da maiúscula — `test_prosody_accepts_sentence_split_with_capitalization`
- [x] Falha de rede devolve o original, sem derrubar o livro — `test_prosody_returns_original_on_network_failure`
- [x] `ChainNormalizer` aplica os normalizadores na ordem configurada — `test_chain_applies_normalizers_in_order`
- [x] `cost_per_char` da cadeia é a soma dos elos — `test_chain_cost_is_the_sum_of_links`
- [x] A estimativa da OS-042 reflete a cadeia sem alteração em `estimate_cost` — `test_estimate_cost_includes_chain_cost`
- [x] Prosódia desligada (padrão) não faz nenhuma chamada de rede — `test_prosody_disabled_by_default_makes_no_network_call`

## 3. Testes escritos

10 testes em `tests/unit/test_prosody_normalizer.py`:

| Teste | Passou? |
|---|---|
| `test_prosody_accepts_punctuation_only_change` | [x] |
| `test_prosody_rejects_changed_word` | [x] |
| `test_prosody_rejects_added_word` | [x] |
| `test_prosody_rejects_removed_word` | [x] |
| `test_prosody_accepts_sentence_split_with_capitalization` | [x] |
| `test_prosody_returns_original_on_network_failure` | [x] |
| `test_chain_applies_normalizers_in_order` | [x] |
| `test_chain_cost_is_the_sum_of_links` | [x] |
| `test_estimate_cost_includes_chain_cost` | [x] |
| `test_prosody_disabled_by_default_makes_no_network_call` | [x] |

Confirmar: commit "Red" antes do "Green"? [x] Sim — o Red falhou com `ModuleNotFoundError: No module named 'plugins.normalizers.prosody_normalizer'`.

## 4. Saída de comandos relevantes

```
$ python -m pytest tests/unit/test_prosody_normalizer.py -q
..........                                                               [100%]
10 passed in 4.90s

$ python -m pytest -q
365 passed, 1 warning in 12.71s

$ ruff check core/ plugins/ tests/unit/test_prosody_normalizer.py
All checks passed!

$ black --check core/ plugins/ tests/unit/test_prosody_normalizer.py
All done! ✨ 🍰 ✨
```

## 5. Decisões de implementação documentadas

**(a) Guarda-corpo de identidade de palavras, não de tamanho.** O da OS-038 mede divergência de tamanho (`[0.85, 2.0]`); para prosódia isso é a métrica errada — inserir vírgulas quase não muda comprimento, então qualquer reescrita de palavras passaria batido. O guarda-corpo desta OS compara `tokens(original) == tokens(saída)`, onde `tokens` remove toda pontuação (`\w+`), colapsa espaços e compara sem diferenciar maiúsculas. Isso permite `", e"` → `". E"` (aceito) e barra troca/adição/remoção de palavra (rejeitado, devolve o original). É determinístico e testável sem LLM.

**(b) Dois passes separados com guarda-corpos incompatíveis.** A OS-038 trata de notação (números/abreviações por extenso) e mede tamanho; a prosódia mexe só em pontuação e mede palavras. Por isso são dois normalizadores distintos com prompts e guarda-corpos próprios, não um único passe.

**(c) Ordem obrigatória notação → prosódia (seção 5 da OS).** A notação expande palavras ("R$ 50" → "cinquenta reais"), e a prosódia roda *depois*, sobre o texto já expandido — só assim o guarda-corpo de palavras faz sentido (ele compara contra o texto que a notação produziu, não contra o original cru).

**(d) `ChainNormalizer` é ele mesmo um `TextNormalizer`.** Compõe a lista na ordem recebida e soma os `cost_per_char`. Como a trava da OS-042 já multiplica caracteres por `normalizer.cost_per_char`, a soma da cadeia entra na estimativa **automaticamente** — `estimate_cost` não precisou de nenhuma alteração além de `_build_normalizer` devolver a cadeia.

**(e) Prosódia desligada por padrão (`config.yaml` `prosody.name: noop`).** Sem opt-in por livro (`Book.normalize_text`) nada é construído; com opt-in, a prosódia só entra na cadeia se o dono ligar `prosody.name: prosody` e fornecer a chave. Sem chave o `ProsodyNormalizer` degrada para "sem normalização" (nem toca a rede), igual à OS-038.

**(f) Sem opt-in, nem a cadeia é construída.** `_build_normalizer` só é chamado quando `normalize=True`; o nível simples não paga nada.

## 6. Desvios do escopo original

Nenhum desvio de escopo. Arquivos alterados exatamente os listados na seção 4 da OS:
- `plugins/normalizers/prosody_normalizer.py` (novo)
- `plugins/normalizers/base.py` (novo `ChainNormalizer`)
- `plugins/registry.py` (registro do `prosody`)
- `core/config.py` + `config.yaml` (bloco `prosody`)
- `core/pipeline.py` (`_build_normalizer` agora monta a cadeia)
- Testes correspondentes

`SYSTEM_PROMPT` da OS-038 **não foi tocado**, conforme a restrição de fora de escopo.

## 7. Dúvidas / bloqueios

Nenhuma decisão de arquitetura nova foi tomada sozinha — tudo estava coberto pela OS. Pendência para o dono: **ligar a prosódia em `config.yaml` e validar com a chave real** antes de usar em livro inteiro, observando o dobro de custo do nível médio (~US$ 0,32–1,74 livro) para o ganho concentrado nos ~13% de frases da faixa média (seção 3 da OS).

## 8. Link do PR

https://github.com/dinei84/listening/pull/54
