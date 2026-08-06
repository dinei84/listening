# OS-044 — Relatório de entrega

**Data:** 06/08/2026
**Branch:** `os/044-notacao-para-narracao` (empilhado sobre `fix/observabilidade-normalizador`)
**Commit(s) relevante(s):** `cfe0ea1` (Red), `2f1b3d7` (Green)

## 1. Resumo do que foi feito

`sanitize_text` passou a expandir a notação que o G2P do espeak pronuncia errado em português: abreviações, horas, datas numéricas e intervalos. A correção é determinística e roda no nível simples — sem rede, sem custo, sem depender do opt-in do ajudante LLM. Só entrou o que foi **medido** como errado no G2P real.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes escritos antes da implementação — commit `cfe0ea1` com 9 testes falhando existe antes do `2f1b3d7`
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (276 antes → 290 depois)
- [x] Código segue os contratos de `ARQUITETURA.md` — nenhum contrato de interface tocado
- [x] Nenhuma chamada real a API paga nos testes — o sanitizer é puro, sem rede; a medição no G2P foi manual e local (Kokoro roda offline)
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-044-report.md`
- [x] PR aberto — https://github.com/dinei84/listening/pull/41

Específico (seção 4 da OS):

- [x] `séc. XIX` → "século dezenove" — verificado no G2P: `sˈɛkulʊ dˌezenˈɔvy`
- [x] `cap. IV` → "capítulo quatro" — `kˌapˈitulʊ kwˈatrʊ`
- [x] `pág. 42` → "página quarenta e dois" — `pˈaʒinæ kwˌaɾˈAŋtæidˈoɪs`
- [x] `15h30` → "quinze e trinta" — `kˈiŋzy i trˈiŋtæ`
- [x] `15h` → "quinze horas" — `kˈiŋzy ˈɔɾæs`
- [x] `12/03/2019` → "doze de março de dois mil e dezenove" — `dˈozy ʤy mˈaɾəsʊ ʤy dˈoɪz mˈiʊ i dˌezenˈɔvy`
- [x] `páginas 10-15` → "dez a quinze" — `dˈɛz a kˈiŋzy`
- [x] Subtração legítima intacta — `o saldo caiu 10-15 reais` segue `dˈɛz mˈenʊs kˈiŋzy`
- [x] `Sr.`/`Prof.` expandem sem quebrar o chunker — `test_chunker_still_splits_sentences_after_abbreviation_expansion`
- [x] Nenhuma expansão dentro de palavra — `test_sanitize_does_not_expand_abbreviation_inside_word`
- [x] Nenhum teste existente quebra

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_sanitize_expands_reference_abbreviations` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_expands_title_abbreviations` | idem | Sim |
| `test_sanitize_keeps_abbreviations_espeak_already_says_right` | idem | Sim |
| `test_sanitize_does_not_expand_abbreviation_inside_word` | idem | Sim |
| `test_sanitize_reads_hour_marker_as_pause` | idem | Sim |
| `test_sanitize_reads_bare_hour_as_horas` | idem | Sim |
| `test_sanitize_expands_numeric_date_to_month_name` | idem | Sim |
| `test_sanitize_keeps_non_date_slash_untouched` | idem | Sim |
| `test_sanitize_reads_page_range_as_a` | idem | Sim |
| `test_sanitize_expands_range_after_abbreviation_expansion` | idem | Sim |
| `test_sanitize_reads_en_dash_between_numbers_as_a` | idem | Sim |
| `test_sanitize_keeps_subtraction_hyphen_untouched` | idem | Sim |
| `test_sanitize_keeps_hyphenated_word_untouched` | idem | Sim |
| `test_chunker_still_splits_sentences_after_abbreviation_expansion` | idem | Sim |

Commit "Red" antes do "Green"? [x] Sim — `cfe0ea1` com 9 falhas, depois `2f1b3d7`.

## 4. Saída de comandos relevantes

Medição no G2P **antes** da correção (o que motivou cada item):

```
séc. XIX           -> sˈɛk. dˌezenˈɔvy
cap. IV            -> kˈap. kwˈatrʊ
pág. 42            -> pˈaɡ. kwˌaɾˈAŋtæidˈoɪs
pp. 33             -> pˌepˈe. trˈiŋtæitrˈes
Sr. Souza          -> ˌɛsyˈɛxe. sˈowzæ
Sra. Lima          -> zxˈa. lˈimæ
Prof. Melo         -> prˈɔf. mˈɛlʊ
cf. adiante        -> sˌeˈɛfy. ˌaʤiˈɐ̃ŋʧy
A reuniao e as 15h30.      -> a xˌeuniˈW i as kˈiŋzy aɡˈa trˈiŋtæ
Publicado em 12/03/2019.   -> pˌublikˈadw ˈAŋ dˈozy zˈɛɾʊ trˈez dˈoɪz mˈiʊ i dˌezenˈɔvy
Veja as paginas 10-15.     -> vˈeʒæ as pˈaʒinæs dˈɛz mˈenʊs kˈiŋzy

Já corretos, mantidos intocados:
Dr. Silva          -> dowtˈor. sˈiʊvæ
Dra. Ana           -> dˌowtˈoɾæ. ˈɐ̃næ
etc. e tal         -> ˌeʦˈɛteɾæ. i tˈW
```

Medição **depois** da correção:

```
Ver séc. XIX e cap. IV.        | Ver século XIX e capítulo IV.    | vˈer sˈɛkulʊ dˌezenˈɔvy i kˌapˈitulʊ kwˈatrʊ.
Na pág. 42.                    | Na página 42.                    | na pˈaʒinæ kwˌaɾˈAŋtæidˈoɪs.
O Sr. Souza e a Sra. Lima.     | O senhor Souza e a senhora Lima. | ʊ seɲˈor sˈowzæ i a sˌeɲˈɔɾæ lˈimæ.
O Prof. Melo, cf. adiante.     | O professor Melo, conforme adiante. | ʊ prˌofesˈor mˈɛlʊ, kˌoŋfˈɔɾəmj ˌaʤiˈɐ̃ŋʧy.
A reuniao e as 15h30.          | A reuniao e as 15 e 30.          | a xˌeuniˈW i as kˈiŋzy i trˈiŋtæ.
Comeca as 15h.                 | Comeca as 15 horas.              | kˌomˈɛkæ as kˈiŋzy ˈɔɾæs.
Publicado em 12/03/2019.       | Publicado em 12 de março de 2019. | pˌublikˈadw ˈAŋ dˈozy ʤy mˈaɾəsʊ ʤy dˈoɪz mˈiʊ i dˌezenˈɔvy.
Veja as paginas 10-15.         | Veja as paginas 10 a 15.         | vˈeʒæ as pˌaʒˈinæs dˈɛz a kˈiŋzy.
O periodo 1914–1918.           | O periodo 1914 a 1918.           | ʊ pˌeɾiˈɔdʊ mˈiʊ nˈɔvysˈAŋtʊzˌi katˈoɾəzy a mˈiʊ nˈɔvysˈAŋtʊzˌi dezˈoɪtʊ.
O Dr. Silva e a Dra. Ana.      | O Dr. Silva e a Dra. Ana.        | ʊ dowtˈor. sˈiʊvæ i a dˌowtˈoɾæ. ˈɐ̃næ.
O saldo caiu 10-15 reais.      | O saldo caiu 10-15 reais.        | ʊ sˈWdʊ kaˈiʊ dˈɛz mˈenʊs kˈiŋzy xeˈIs.
A relacao custo/beneficio.     | A relacao custo/beneficio.       | a xˌelakˈW kˈustʊ bˌenefisˈiʊ.
```

Suíte:

```
290 passed, 1 warning in 11.41s
```

`black`: 2 arquivos reformatados. `ruff check`: `All checks passed!`

## 5. Desvios do escopo original

Dois, ambos por medição:

1. **`Dr.`, `Dra.` e `etc.` foram excluídos da expansão.** A OS falava genericamente em "abreviações". Ao medir no G2P, esses três já são pronunciados corretamente pelo espeak ("doutor", "doutora", "etcétera"). Expandi-los seria mudança sem defeito que a justifique, então entraram como teste de não-regressão em vez de item de correção.

2. **A seção 3 da OS foi corrigida antes da implementação.** O texto original justificava a ordem dizendo que a expansão de notação precisava rodar antes do mapeamento de símbolos "para que a barra de data fosse consumida como data". Isso estava errado — `/` não está em `SYMBOL_TO_WORD`, então não há conflito. A restrição de ordem real é outra: abreviações **antes** de intervalos, porque `págs. 10-15` só é reconhecível como intervalo depois de virar `páginas 10-15`.

## 6. Dúvidas / bloqueios

**Ordem de merge — resolvida.** Este branch estava empilhado sobre `fix/observabilidade-normalizador`, que contém trabalho de responsabilidade diferente (ligar o normalizador LLM + configurar logging). Foram separados para não inchar o PR, conforme a seção 3 do `AGENTS.md`. O dono aprovou o merge dos dois: o PR do fix (https://github.com/dinei84/listening/pull/40) entrou primeiro, e este veio em seguida.

**Fora de escopo, registrado para backlog:** ordinais escritos sem o caractere correto (`1o`, `2a` em vez de `1º`, `2ª`) são lidos como "um o" e "dois a". Foi medido e confirmado, mas não estava entre os quatro itens aprovados para esta OS. Os ordinais com `º`/`ª` de verdade já funcionam ("primeiro", "décima").

**Limitação conhecida da âncora de intervalo:** a lista `RANGE_ANCHORS` é fechada. Um intervalo com substantivo fora da lista ("nos versos 10-15" está coberto, "nas estrofes 10-15" não) continua sendo lido como subtração. É o lado seguro do trade-off — o erro é não-corrigir, nunca alterar o sentido de uma subtração legítima. Ampliar a lista é barato e não exige mudança de código.

## 7. Link do PR

https://github.com/dinei84/listening/pull/41
