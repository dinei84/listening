# OS-040 — Relatório de entrega

**Data:** 2026-08-05
**Branch:** os/040-sanitizacao-de-simbolos
**Commit(s) relevante(s):** b8ad81c (test: Red), cd21f57 (feat: Green), 0c3232d (docs)

## 1. Resumo do que foi feito

Novo estágio de sanitização local e determinística em `processing/sanitizer.py::sanitize_text()`, aplicado no `core/pipeline.py` **antes do chunking** (em `synthesize_text()` e `count_text_chunks()`, para o total de chunks bater com o que a síntese produz). Remove, preservando o conteúdo: marcadores de markup (`**negrito**`, `*itálico*`, `` `código` ``, `# título`, `> citação`, itens de lista `- * + N.` no início de linha); símbolos mapeados para português (`≠`→"diferente de", `±`, `≈`, `→`, `%`, `°`, `§`, moedas, `&`...); linhas de separador de tabela (somem) e linhas de dados (células unidas por vírgula); URLs→"link" e e-mails→"endereço de e-mail" (pontuação de fim de frase preservada); e blocos de código cercados (```/~~~) → anúncio "trecho de código omitido". **Anti-falso-positivo por design** (exigência da OS): prosa comum, travessão de diálogo (`—`), asterisco/hífen soltos e citação indentada passam intactos — a detecção de bloco de código é apenas a cercada, deliberadamente, para não comer prosa indentada.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `b8ad81c` "Red" antes de `cd21f57` "Green")
- [x] Todos os testes da OS passam localmente — 235 pass, 0 fail
- [x] Nenhum teste existente quebrou (224 anteriores + 11 novos = 235; `chunk_text`/`clean_text` intocados e regressão coberta)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` — nenhum contrato mudou; `chunk_text()`/`clean_text()` não foram alterados (a OS proíbe), o estágio novo é adicional e fica em `processing/` (o lugar natural, junto de `cleaner.py`/`chunker.py`)
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — tudo local/determinístico; a verificação empírica usou só o G2P do Kokoro local (`model=False`, sem download de modelo)
- [x] Type hints e docstring de uma linha em toda função pública nova/alterada
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4 e 5)
- [x] Relatório criado em `docs/report/OS-040-report.md`
- [x] PR aberto contra o branch principal, título `[OS-040] ...`

### DoD específico da OS (`docs/os/OS-040-sanitizacao-de-simbolos.md` seção 4)

- [x] `**negrito**` é narrado como "negrito", sem "asterisco" — `test_sanitize_removes_markdown_emphasis_markers` + G2P real: `...ˌæsteɾˈiskʊˌæsteɾˈiskʊ nˌeɡrˈitw...` → `...nˌeɡrˈitw...` (seção 4)
- [x] `≠`, `±`, `→`, `≈` são narrados em português, não pelo nome em inglês — `test_sanitize_maps_math_symbols_to_portuguese` + G2P real: `≠` deixa de sair `nˌɒt ˈiːkwəl tʊ` e vira `ʤˌifeɾˈAŋʧy ʤy` ("diferente de") (seção 4)
- [x] Separador de tabela (`|---|`) não é narrado — `test_sanitize_drops_table_separator_rows` + G2P real: linha `|---|---|---|` some (seção 4)
- [x] URL não é soletrada caractere a caractere — `test_sanitize_shortens_urls_and_emails` + G2P real: `aɡˌatˌetˈepˌeˈɛsy:...` → `vˈeʒæ lˈiŋk.` ("Veja link.") (seção 4)
- [x] Bloco de código não é narrado símbolo a símbolo; o comportamento escolhido está documentado — **escolha: anunciar** ("trecho de código omitido", conforme a recomendação da OS — sumir sem avisar é pior); `test_sanitize_handles_code_block_without_reading_symbols` + G2P real (seção 4 e 5)
- [x] **Texto comum não é alterado** — prosa normal, travessão de diálogo e asterisco/hífen isolados intactos: `test_sanitize_leaves_plain_prose_untouched`, `test_sanitize_preserves_lone_asterisk_in_prose`, `test_sanitize_preserves_dialogue_dash` + G2P real com prosa/diálogo **idênticos antes e depois** (seção 4)
- [x] Verificação com o G2P real, antes e depois, para cada categoria acima — seção 4 do relatório
- [x] Nenhum teste das OS-008/009/035 quebra — `test_chunk_and_clean_contracts_unchanged` + toda a suíte antiga verde (235 pass)
- [x] Nenhuma chamada de rede ou API paga na suíte — nada de cloud; só processamento local

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_sanitize_removes_markdown_emphasis_markers` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_removes_headings_quotes_and_list_markers` (extra) | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_maps_math_symbols_to_portuguese` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_drops_table_separator_rows` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_shortens_urls_and_emails` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_handles_code_block_without_reading_symbols` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_leaves_plain_prose_untouched` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_preserves_lone_asterisk_in_prose` (extra) | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_sanitize_preserves_dialogue_dash` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_chunk_and_clean_contracts_unchanged` | `tests/unit/processing/test_sanitizer.py` | Sim |
| `test_pipeline_applies_sanitize_before_chunking` (extra, wiring) | `tests/unit/processing/test_sanitizer.py` | Sim |

Confirmar: commit "Red" existe antes do commit "Green"? [x] Sim — `b8ad81c` (`ModuleNotFoundError: No module named 'processing.sanitizer'`) antes de `cd21f57`.

## 4. Verificação empírica com o G2P real (seção 6 da OS)

Mesmo método das OS-034/035/037: `kokoro.KPipeline(lang_code='p', model=False)` (só G2P, sem modelo/download). Saída antes/depois por categoria:

```
=== markup ===
ANTES : o ˌæsteɾˈiskʊˌæsteɾˈiskʊ nˌeɡrˈitw ˌæsteɾˈiskʊˌæsteɾˈiskw i ˌæsteɾˈiskw ˌitalˈikw ˌæsteɾˈiskw i o kˌoʤˈiɡʊ.
DEPOIS: ʊ nˌeɡrˈitw i ˌitalˈikw i ʊ kˌoʤˈiɡʊ.                    (negrito / italico / codigo, sem "asterisco")

=== simbolo ===
ANTES : ʃˈis nˌɒt ˈiːkwəl tʊ zˈɛɾw i ˈipsiloŋ plˈʌs ɔː mˈInəs ˈũŋ; ... ɐpɹˈɒksɪmətli ...
DEPOIS: ʃˈiz ʤˌifeɾˈAŋʧy ʤy zˈɛɾw i ˈipsiloŋ mˈIz ow mˈenʊs ˈũŋ; ... ˌaprosˌimadæmˈAŋʧy ...
        (≠ agora "diferente de", ± "mais ou menos", ≈ "aproximadamente" — em português)

=== tabela ===
ANTES : nˈomy valˈor a ˈũŋ
DEPOIS: nˈomy, valˈoɾ ˈa, ˈũŋ                                       (separador sumiu; células legíveis)

=== url ===
ANTES : vˈeʒæ aɡˌatˌetˈepˌeˈɛsy:ˌezˈAmplʊ.koŋ.bˌeˈɛxe dˈoks?ˈid iɡwˈæl kwˌaɾˈAŋtæidˈoɪs ˈe xˈef ...
DEPOIS: vˈeʒæ lˈiŋk.                                                  ("Veja link.")

=== codigo ===
ANTES : ˌezˈAmplʊ: pˈIθɐ̃ŋ dˈef kˌWkulˈar(ʃˈis): xetˈuɾən ʃˈiz ˌæsteɾˈiskʊ dˈoɪs fˈiŋ.
DEPOIS: ˌezˈAmplʊ: trˈeʃʊ ʤy kˈɔʤiɡw ˌomiʧˈidʊ fˈiŋ.                   ("trecho de código omitido")

=== prosa (falso positivo) ===
ANTES : a ˌAŋʒeɲaɾˈiæ ʤy sˌeɡuɾˈɐ̃ŋkæ xekˈɛr mˌetˈodʊs foɾəmˈIz i vˌeɾifˌikakˈW xˌiɡoɾˈɔzæ. ...
DEPOIS: IDÊNTICO                                                     (prosa comum intacta)

=== dialogo (falso positivo) ===
ANTES : — vˈɔsy kˈɛɾ ˈir? — sˈiŋ, klˈaɾʊ.
DEPOIS: IDÊNTICO                                                     (travessão de diálogo intacto)
```

Todos os critérios da OS batem com a saída real do G2P: markup sem "asterisco", `≠`/`±`/`≈` em português, tabela legível, URL → "link", código anunciado, e prosa/diálogo **idênticos antes e depois** (nada de falso positivo).

## 5. Decisões de implementação documentadas

1. **Ordem do estágio** (documentada no código): código → URL/e-mail → markup → tabela → símbolos. Blocos de código primeiro (contêm tudo — URLs, símbolos, markup — e viram um anúncio, então nada interno vaza); URL/e-mail antes dos símbolos (senão `&`/`:` de uma URL viraria "e"/"dois pontos"); markup antes das tabelas (célula com `**negrito**` é limpa antes de virar célula); símbolos por último.
2. **Onde aplicar:** dentro de `pipeline.synthesize_text()` **e** `pipeline.count_text_chunks()`, ambos antes do `chunk_text()`. Assim o total de chunks (barra de progresso OS-024 e checagem de consistência OS-022) é calculado sobre o MESMO texto que a síntese usa — se a sanitização removesse uma linha (ex: separador de tabela), sem isso o total não bateria. `chunk_text()`/`clean_text()` ficaram intocados (a OS proíbe mudar o contrato).
3. **Bloco de código: anunciar**, como a OS recomenda ("sumir com conteúdo sem avisar é pior") — "trecho de código omitido". **Detecção apenas cercada** (```/~~~): a indentação consistente foi deixada de fora de propósito, porque "linha indentada" é exatamente o que citação/prosa indentada de um PDF parece — a OS manda preferir preservar. Limitação registrada: código inline de uma linha (ex: `def calcular(x): return x * 2` sozinho, sem cerca) não é detectado, para não arriscar falso positivo; isso é decisão documentada, não esquecimento.
4. **Tabela:** linha de separador (`|:---:|`, `|---|---|`) some por completo; linha de dados vira células unidas por vírgula ("| Nome | Valor |" → "Nome, Valor"). Bare `---` (sem pipes) é preservado — poderia ser separador de diálogo/seção, e o `|` é o sinal confiável de tabela.
5. **Travessão de diálogo (`—`, U+2014) preservado** — não está no mapa de símbolos nem nos marcadores de lista (que removem só `- * + N.` no início de linha). Convenção de PT: diálogo usa travessão; lista usa hífen.
6. **Falso positivo de lista vs. diálogo:** um `- ` no início de linha é tratado como marcador de lista e removido (o conteúdo — as palavras faladas — sobrevive; o marcador não é narrado). A OS lista `- ` como marcador a remover; o travessão `—` (a forma canônica de diálogo em PT) é sempre preservado. Trade-off documentado.
7. **URL engolindo pontuação:** o match da URL incluía a pontuação final de frase ("https://x.com." → "link."); a implementação devolve a pontuação ("Veja link."), preservando o termo de sentença.

## 6. Desvios do escopo original

Nenhum. Mudanças em `processing/sanitizer.py` (novo), `core/pipeline.py` (duas linhas de aplicação) e o arquivo de teste; `chunk_text()`/`clean_text()` intocados; nenhuma dependência nova.

## 7. Dúvidas / bloqueios

Nenhum. Duas observações, sem decisão de arquitetura deste agente: (1) o mapa de símbolos cobre o conjunto matemático/comum (a OS pede `≠ ± → ≈` no mínimo) — ampliar (ex: `<`/`>`) foi deliberadamente evitado para não transformar tags HTML em "menor b maior"; (2) código inline não cercado segue lido símbolo a símbolo (limitação documentada na seção 5, item 3) — se o uso real pedir, vira uma OS própria com heurística mais fina.

## 8. Link do PR

A preencher após abertura do PR.
