# OS-044 — Notação que o espeak lê errado

## 1. Objetivo

Corrigir, na camada determinística, os sinais de notação que o G2P do espeak pronuncia errado em português — abreviações, horas, datas e intervalos numéricos — para que o **nível simples** (sem LLM, sem rede, sem custo) já entregue uma narração correta.

## 2. Escopo

Alterados:

- `processing/sanitizer.py` — novas transformações de notação dentro de `sanitize_text`.
- `tests/unit/processing/test_sanitizer.py` — casos novos.

Fora de escopo (declarado explicitamente):

- **Sinais de expressividade** — reticências (`...`/`…`), travessão de diálogo (`—`), aspas curvas, parênteses, `?!` e CAIXA ALTA foram medidos no G2P e **já funcionam**; sobrevivem intactos para a prosódia do espeak. Nada a fazer.
- **Notação que já funciona** — `1º`→primeiro, `10ª`→décima, `½`→meio, `¾`→três quartos, `™`, `®`, `@`→arroba, `+`, `=`. Medido, correto hoje.
- `plugins/normalizers/llm_normalizer.py` — o `SYSTEM_PROMPT` **não** é alterado. O ajudante LLM já cobre todos esses casos; esta OS é sobre o nível que não paga. Manter a correção em um só lugar evita duas fontes de verdade divergindo.
- `plugins/speakers/kokoro_speaker.py` e `phonetic_map.yaml` — o mapa fonético é para termos que o G2P erra *foneticamente*; notação é transformação de texto e pertence ao sanitizer, como a OS-040 estabeleceu.
- O aviso `words count mismatch` do phonemizer — investigado e **benigno**: só aparece com dígitos crus, ou seja, é sintoma de texto não-normalizado, não defeito. Não suprimir.

## 3. Contratos envolvidos

Nenhum contrato de interface é criado ou alterado. Esta OS estende o comportamento interno de `sanitize_text`, estabelecido pela OS-040 (`ARQUITETURA.md`, seção de processamento de texto): símbolo/notação → palavra em português, antes do chunking.

A ordem dentro de `sanitize_text` importa e é parte do contrato desta OS: a expansão de abreviações roda **antes** da de intervalos, porque o intervalo depende do substantivo que o precede para se distinguir de subtração — `págs. 10-15` só é reconhecível como intervalo depois de virar `páginas 10-15`.

Só é expandido o que foi **medido como errado** no G2P. `Dr.`, `Dra.` e `etc.` já são pronunciados corretamente pelo espeak ("doutor", "doutora", "etcétera") e ficam intocados — expandi-los seria mudança sem defeito que a justifique.

## 4. Critérios de aceite

- [ ] `séc. XIX` narra "século dezenove" (hoje: "sék dezenove")
- [ ] `cap. IV` narra "capítulo quatro" (hoje: "káp quatro")
- [ ] `pág. 42` narra "página quarenta e dois"
- [ ] `15h30` narra "quinze e trinta" (hoje: "quinze agá trinta")
- [ ] `15h` narra "quinze horas"
- [ ] `12/03/2019` narra "doze de março de dois mil e dezenove" (hoje: "doze zero três dois mil e dezenove")
- [ ] `páginas 10-15` narra "dez a quinze" (hoje: "dez menos quinze")
- [ ] Subtração legítima (`o saldo caiu 10-15 reais`) **não** vira "a" — o hífen entre números só vira "a" quando o contexto indica intervalo
- [ ] `Dr.`/`Sr.`/`Prof.` expandem sem quebrar a detecção de fim de frase do `chunker.py`
- [ ] Nenhuma expansão dispara dentro de palavra ou em frase que apenas começa com a sigla
- [ ] Nenhum teste existente quebra (276 hoje)

## 5. Testes exigidos (mínimo)

- `test_sanitize_expands_reference_abbreviations`
- `test_sanitize_expands_title_abbreviations`
- `test_sanitize_does_not_expand_abbreviation_inside_word`
- `test_sanitize_reads_hour_marker_as_pause`
- `test_sanitize_reads_bare_hour_as_horas`
- `test_sanitize_expands_numeric_date_to_month_name`
- `test_sanitize_keeps_non_date_slash_untouched`
- `test_sanitize_reads_page_range_as_a`
- `test_sanitize_keeps_subtraction_hyphen_untouched`
- `test_sanitize_notation_runs_before_symbol_map`
- `test_chunker_still_splits_sentences_after_abbreviation_expansion`

## 6. Relatório

Ver `docs/report/OS-044-report.md`.
