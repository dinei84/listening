# OS-040 — Sanitização de markup, símbolos e blocos não-narráveis

## 1. Objetivo

Achado em uso real ("ele tenta ler caracteres não-alfanuméricos, sinais auxiliares, operadores matemáticos — fica estranho") e **confirmado por medição**. Esta OS remove o ruído de forma **local e determinística**, antes de qualquer IA — porque o nível simples do produto (decisão #23) não pode soar quebrado.

## 2. Contexto técnico medido (não repetir a investigação)

Saída real do G2P do Kokoro em português:

```
'**negrito**'   ->  'ˌæsteɾˈiskʊˌæsteɾˈiskʊ nˌeɡrˈitw ˌæsteɾˈiskʊˌæsteɾˈiskʊ'
                    (lê "asterisco asterisco negrito asterisco asterisco")

'a ≠ 0'         ->  'a nˌɒt ˈiːkwəl tʊ zˈɛɾw'
                    (lê "not equal to" — EM INGLÊS, no meio do texto em português)

'def calcular(x): return x * 2'
                ->  'dˈef kˌWkulˈar(ʃˈis): xetˈuɾən ʃˈiz ˌæsteɾˈiskʊ dˈoɪz'

'| Nome | Valor |\n|---|---|'  ->  'nˈomy valˈor'   (sopa de caracteres)

'https://exemplo.com.br/docs?id=42&ref=abc'
                ->  'aɡˌatˌetˈepˌeˈɛsy:ˌezˈAmplʊ.koŋ.bˌeˈɛxe dˈoks?ˈid iɡwˈæl ...'
```

O caso do `≠` é o mais grave: o espeak recorre ao **nome do símbolo em inglês** dentro de um texto em português.

## 3. Escopo

**Dentro do escopo:**

Um estágio novo de sanitização, aplicado ao texto **antes** de virar chunk. Onde exatamente é decisão de implementação (`processing/` é o lugar natural, junto de `cleaner.py`/`chunker.py`); documentar a escolha e a ordem em relação à limpeza que já existe.

- **Markup**: remover marcadores que não se lê — `**negrito**`, `*itálico*`, `` `código` ``, `## títulos`, `> citação`, marcadores de lista (`- `, `* `, `1. ` no início da linha). O **conteúdo** fica; só o marcador sai.
- **Símbolos**: mapa local de símbolo → palavra em português (`≠` → "diferente de", `±` → "mais ou menos", `→` → "leva a", `≈` → "aproximadamente", `%`, `°`, `§`...). Sem isso o espeak inventa nomes em inglês.
- **Tabelas**: linhas de separador (`|---|---|`) somem; linhas de tabela viram texto legível ou são anunciadas — decisão de implementação, documentar.
- **URLs e e-mails**: substituir por algo curto e legível (ex: "link", "endereço de e-mail") em vez de soletrar. Preservar o texto ao redor.
- **Blocos de código**: detectar (cerca ``` ou indentação consistente + densidade de símbolos) e **não narrar caractere a caractere**. Decisão de implementação a documentar: anunciar ("trecho de código omitido") ou pular em silêncio. Recomendação: anunciar — sumir com conteúdo sem avisar é pior.

**Fora do escopo:**
- Classificar tipo de trecho semanticamente ("isto é um poema?") ou ajustar ritmo/prosódia — isso é genuinamente IA, fica para o nível médio (OS-038 reposicionada).
- Ler fórmulas matemáticas por extenso de forma inteligente (`ax² + bx + c` → "a xis ao quadrado mais..."). O mapa de símbolos cobre o básico; a leitura correta de expressão é IA.
- Qualquer chamada a API paga.
- Mudar `chunk_text()`/`clean_text()` de contrato — o estágio novo é adicional.

**Cuidado obrigatório com falso positivo:** a sanitização **não pode comer texto normal**. Um asterisco solto no meio de uma frase comum, um hífen de lista que na verdade é travessão de diálogo, uma linha indentada que é citação e não código — todos precisam sobreviver. Preferir errar para o lado de **preservar** o texto. Cobrir isso com testes explícitos.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `**negrito**` é narrado como "negrito", sem "asterisco"
- [ ] `≠`, `±`, `→`, `≈` são narrados em português, não pelo nome em inglês
- [ ] Separador de tabela (`|---|`) não é narrado
- [ ] URL não é soletrada caractere a caractere
- [ ] Bloco de código não é narrado símbolo a símbolo; o comportamento escolhido (anunciar/pular) está documentado
- [ ] **Texto comum não é alterado** — prosa normal passa intacta, incluindo travessão de diálogo e asterisco/hífen isolados
- [ ] Verificação com o G2P real, antes e depois, para cada categoria acima, no relatório
- [ ] Nenhum teste das OS-008/009/035 quebra
- [ ] Nenhuma chamada de rede ou API paga na suíte

## 5. Testes exigidos (mínimo)

- `test_sanitize_removes_markdown_emphasis_markers`
- `test_sanitize_maps_math_symbols_to_portuguese`
- `test_sanitize_drops_table_separator_rows`
- `test_sanitize_shortens_urls_and_emails`
- `test_sanitize_handles_code_block_without_reading_symbols`
- `test_sanitize_leaves_plain_prose_untouched` (falso positivo)
- `test_sanitize_preserves_dialogue_dash` (falso positivo)
- `test_chunk_and_clean_contracts_unchanged` (regressão OS-008/035)

Local sugerido: `tests/unit/processing/`.

## 6. Verificação empírica exigida

Para cada categoria (markup, símbolo, tabela, URL, código), colar no relatório a saída do G2P real (`kokoro.KPipeline(lang_code='p', model=False)`) antes e depois — mesmo método das OS-034/035/037. Incluir pelo menos um trecho de prosa comum mostrando que **nada mudou**.

## 7. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-040-report.md`.*
