# OS-035 — Juntar linhas quebradas do PDF (pausas artificiais na narração)

## 1. Objetivo

Achado em uso real ("a narração sai picotada") e **confirmado por medição**: cada quebra de linha herdada do PDF vira uma **pausa audível no meio da frase**. O Kokoro divide o texto em `\n` antes de sintetizar (`split_pattern=r'\n+'` em `KPipeline.__call__`), e o `processing/cleaner.py` corrige hifenização mas **não junta linhas** que continuam a mesma frase. Esta OS elimina essas pausas.

## 2. Contexto técnico medido (não repetir a investigação)

Parágrafo comum extraído de um PDF real, passando pelo pipeline atual:

```
quebras de linha no texto limpo: 4
chunk 0: 5 segmentos de síntese HOJE  vs  1 se as linhas fossem unidas
   1º segmento hoje: 'A engenharia de seguranca trata de construir sistemas que'
```

Cinco chamadas de inferência onde deveria haver uma — quatro pausas artificiais, todas no meio de frases. Um PDF quebra linha a cada ~80 caracteres, então um chunk de 1000 caracteres carrega ~12 quebras: **~12 pausas espúrias por chunk**, o livro inteiro.

**Por que o `cleaner.py` atual não resolve:** ele tem `_fix_hyphenation()`, que junta linha terminada em `-` com a próxima quando esta começa em minúscula. Isso cobre só a hifenização de sílaba partida; uma linha que termina em palavra inteira no meio da frase (o caso comum) continua quebrada.

**Achado secundário, mesmo território:** `chunk_text()` divide em `(?<=[.!?])\s+`, então abreviações viram falsas fronteiras de sentença. Verificado: `"Segundo o Dr. Silva a arquitetura mudou..."` com fronteira próxima produz `['Segundo o Dr.', 'Silva a arquitetura mudou...']` — dois `AudioChunk` separados, com pausa no meio do nome.

## 3. Escopo

**Dentro do escopo:**

- **`processing/cleaner.py`**: juntar linhas consecutivas que pertencem à mesma frase. Heurística sugerida (ajustável na implementação, documentar a escolhida): unir a linha atual com a próxima quando a atual **não** termina em `.`, `!`, `?`, `:`, `;` — preservando um espaço na junção. Deve continuar preservando **fronteira de parágrafo**: linha vazia (ou dupla quebra) separa parágrafos e não pode ser unida, senão o texto vira um bloco só e o TTS perde a pausa legítima entre parágrafos.
- Manter `_fix_hyphenation()` funcionando como hoje — a junção nova roda **depois** dele (hífen resolvido primeiro, senão a palavra partida vira duas).
- **`processing/chunker.py`**: não tratar como fim de sentença um `.` que faz parte de abreviação. Lista pequena e local de abreviações comuns em PT/EN (`Dr.`, `Sr.`, `Sra.`, `Prof.`, `pág.`, `p.`, `ex.`, `etc.`, `fig.`, `cap.`, `vol.`, `Inc.`, `Ltd.`...), mais o caso de inicial de nome (`R.` em "Robert R. Martin") e número seguido de ponto. **Não** trazer spaCy/NLTK: modelo de ~50MB e segunda toolchain para um ganho marginal, contra a filosofia de baixa infraestrutura (decisões #12/#13).

**Fora do escopo:**
- Qualquer chamada a LLM/API paga — é a OS-038, opt-in e separada.
- Dicionário fonético — é a OS-037.
- Mudar `DEFAULT_MAX_CHARS` ou o contrato de `chunk_text()` ("nunca corta sentença ao meio" continua valendo).
- Detecção de capítulos — é a OS-036.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Linhas que continuam a mesma frase são unidas, com espaço, no texto que chega ao Speaker
- [ ] Fronteira de parágrafo (linha em branco) **não** é unida — a pausa legítima entre parágrafos se mantém
- [ ] Hifenização (`_fix_hyphenation`) continua funcionando; palavra partida não vira duas
- [ ] Um parágrafo que hoje vira N segmentos de síntese passa a virar 1 — medido com o G2P real do Kokoro, número antes/depois no relatório
- [ ] Abreviações comuns não criam falsa fronteira de sentença em `chunk_text()`
- [ ] Nenhum teste das OS-008/009/021/022/024/027/034 quebra
- [ ] Nenhuma chamada de rede ou API paga na suíte

## 5. Testes exigidos (mínimo)

- `test_clean_text_joins_lines_that_continue_a_sentence`
- `test_clean_text_preserves_paragraph_boundaries`
- `test_clean_text_join_runs_after_hyphenation_fix`
- `test_chunk_text_does_not_split_on_common_abbreviations`
- `test_chunk_text_does_not_split_on_name_initial`
- `test_chunk_text_still_never_splits_a_sentence` (regressão OS-008)

Local sugerido: `tests/unit/processing/test_cleaner.py`, `tests/unit/processing/test_chunker.py`.

## 6. Verificação empírica exigida (fora da suíte automatizada)

Mesma lição da decisão #14 e da OS-034 — os testes automatizados não ouvem o áudio. Registrar no relatório:

- um parágrafo real de PDF, antes e depois: quantos segmentos o `KPipeline` produz (usar `kokoro.KPipeline(..., model=False)`, que roda só o G2P e não baixa o modelo pesado);
- confirmação de que o texto unido não perdeu nem ganhou palavras (comparar contagem de palavras antes/depois).

## 7. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-035-report.md`.*
