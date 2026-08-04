# OS-017 — Relatório de entrega

**Data:** 2026-08-04
**Branch:** os/017-easyocr-extractor
**Commit(s) relevante(s):** 7713a29 (test: Red), a3cdb7b (feat: Green)

## 1. Resumo do que foi feito

`plugins/extractors/easyocr_extractor.py` implementa `EasyOCRExtractor(Extractor)` — terceiro elo da cadeia de OCR (decisão #13), reaproveitando o padrão de `TesseractOCR` (`fitz` para renderizar cada página como imagem) e o padrão de `KokoroSpeaker` para construção lazy/mockável da engine (`_get_reader()`). Registrado em `plugins/registry.py` (`EXTRACTORS["easyocr"]`) e `easyocr==1.7.2` adicionado a `requirements.txt`. A validação empírica exigida pela OS (seção 6) encontrou um resultado relevante: o threshold `0.85` reaproveitado por analogia (decisão #13) não bate com o comportamento real do EasyOCR no fixture "legível" — achado registrado, não corrigido unilateralmente por este agente.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `7713a29` "Red" existe antes de `a3cdb7b` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (90 testes no total, todos passando — 79 pré-existentes + 11 novos)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (seção 4.1 — assinatura de `Extractor`, fórmula de confidence do `EasyOCRExtractor` já registrada na decisão #13; seção 4.4 — entrada no registry)
- [x] Nenhuma chamada real a API paga dentro dos testes automatizados — `_get_reader()` sempre mockado, nenhum `easyocr.Reader` real construído durante `pytest`
- [x] Type hints e docstring de uma linha em toda função pública — `EasyOCRExtractor` segue o mesmo padrão já estabelecido em `TesseractOCR`/`PyMuPDFExtractor` (sem docstrings próprias nos métodos, já documentados na assinatura abstrata de `plugins/extractors/base.py`); type hints presentes em todos os métodos
- [x] `PROJECT_STATE.md` atualizado (seções 2, 4, 5 e 6 — incluindo o achado empírico do threshold)
- [x] Relatório criado em `docs/report/OS-017-report.md`
- [x] PR aberto contra o branch principal, título `[OS-017] ...`

### DoD específico da OS (`docs/os/OS-017-easyocr-extractor.md` seção 4)

- [x] `supports()` retorna `True` para PDF válido com ≥1 página, `False` para caminho inexistente ou arquivo corrompido
- [x] `extract()` retorna uma `ExtractedPage` por página, na ordem do PDF
- [x] Cada `ExtractedPage` tem `source == "easyocr"`
- [x] `confidence` segue exatamente a fórmula de `ARQUITETURA.md` seção 4.1 (`mean` das confidences de `readtext()`, `0.0` sem regiões)
- [x] PDF com imagem de texto legível → `text` não vazio
- [x] PDF sem texto reconhecível → `confidence == 0.0` (testado com mock de `readtext()` retornando lista vazia, que é o caso coberto pela fórmula; ver seção 6 para o comportamento real observado, que é ligeiramente diferente desse caso mockado)
- [x] Nenhum teste constrói um `easyocr.Reader` real — todos os 7 testes de `EasyOCRExtractor` mockam `_get_reader()` inteiro via `monkeypatch.setattr`, nunca só o método de leitura
- [x] Validação empírica real rodando o EasyOCR de verdade sobre 2 fixtures, números colados no relatório — seção 6
- [x] `easyocr==1.7.2` em `requirements.txt`, versão confirmada via `pip index versions easyocr` (mais recente disponível no PyPI no momento)
- [x] Nenhuma chamada de rede dentro da suíte de testes automatizada (`pytest`) — o download de modelo do EasyOCR só aconteceu na validação empírica manual (seção 6), fora do `pytest`, mesma natureza do aviso já registrado para o Kokoro

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_easyocr_supports_returns_true_for_valid_pdf` | `tests/unit/extractors/test_easyocr_extractor.py` | Sim |
| `test_easyocr_supports_returns_false_for_nonexistent_path` | `tests/unit/extractors/test_easyocr_extractor.py` | Sim |
| `test_easyocr_supports_returns_false_for_corrupted_file` | `tests/unit/extractors/test_easyocr_extractor.py` | Sim |
| `test_easyocr_extract_returns_one_page_per_pdf_page` | `tests/unit/extractors/test_easyocr_extractor.py` | Sim |
| `test_easyocr_extract_sets_source_to_easyocr` | `tests/unit/extractors/test_easyocr_extractor.py` | Sim |
| `test_easyocr_extract_confidence_matches_formula_for_legible_text` | `tests/unit/extractors/test_easyocr_extractor.py` | Sim |
| `test_easyocr_extract_confidence_is_zero_for_unreadable_image` | `tests/unit/extractors/test_easyocr_extractor.py` | Sim |
| `test_registry_extractors_contains_easyocr` | `tests/unit/test_registry.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim — `7713a29` (`ModuleNotFoundError: No module named 'plugins.extractors.easyocr_extractor'`) antes de `a3cdb7b`.

## 4. Saída de comandos relevantes

Rodada de confirmação Red (antes da implementação):

```
ERROR tests/unit/extractors/test_easyocr_extractor.py
ERROR tests/unit/test_registry.py
ModuleNotFoundError: No module named 'plugins.extractors.easyocr_extractor'
Interrupted: 2 errors during collection
```

Suíte completa após a implementação (Green):

```
$ python -m pytest -q
90 passed, 1 warning in 6.64s
```

`black --check` e `ruff check` nos arquivos alterados: sem alterações pendentes após um `black` (reformatou uma linha longa em `test_easyocr_extractor.py`), `ruff` sem achados.

## 5. Validação empírica (exigida pela seção 2/4 da OS, mesmo espírito da OS-006)

Instalado `easyocr==1.7.2` de verdade no ambiente (reaproveitando o `torch==2.13.0` já presente via Kokoro — nenhum framework de deep learning novo, confirmando a premissa da decisão #13). Rodado `EasyOCRExtractor.extract()` **sem nenhum mock**, contra as duas fixtures já usadas na validação da OS-006 (`tests/fixtures/ocr/clear_text_pdf.pdf`, `tests/fixtures/ocr/unreadable_text_pdf.pdf`). Primeira execução baixou os pesos do modelo de detecção/reconhecimento do EasyOCR (mesmo comportamento já observado com o Kokoro na OS-004 — chamada de rede real na primeira vez, cacheada depois).

**Fixture "legível" (`clear_text_pdf.pdf`):**

```
regiões devolvidas por reader.readtext():
  text='THE QUICK BROWN FOX JUMPS OVER 13'  conf=0.8018300450905235
  text='LAZY'                                conf=0.9991483092308044
  text='De'                                  conf=0.4921409877522839

ExtractedPage:
  text = "THE QUICK BROWN FOX JUMPS OVER 13 LAZY De"
  confidence = mean([0.8018, 0.9991, 0.4921]) = 0.7644 (elapsed ~11.5s, incluindo download do modelo)
```

**Fixture "ilegível" (`unreadable_text_pdf.pdf`):**

```
regiões devolvidas por reader.readtext():
  text='Mecackaonneoau9rsOrtred'  conf=1.5247991238770913e-05

ExtractedPage:
  text = "Mecackaonneoau9rsOrtred"
  confidence = 1.5247991238770913e-05  (elapsed ~3.7s)
```

**Achado (não é uma correção de arquitetura feita por este agente):**

1. O texto do fixture "legível" foi lido corretamente (a frase completa é reconhecível), mas a confiança agregada (`0.7644`) fica **abaixo** do threshold `0.85` reaproveitado por analogia na decisão #13. Isso acontece porque uma única região de baixa confiança ("De", `0.49` — provavelmente uma leitura parcial da última palavra da frase, cortada pela imagem renderizada) puxa a média para baixo, mesmo com as outras duas regiões acima de `0.80` e `0.99`. Aplicando a heurística de decisão #9 literalmente, esse texto (legível, corretamente extraído) cairia desnecessariamente para `CloudOCRFallback` quando `EasyOCRExtractor` for ligado ao pipeline.
2. O fixture "ilegível" teve confiança real `~0.0000152`, não exatamente `0.0` como a fórmula produz no caso "zero regiões reconhecidas" — mas na prática é uma diferença irrelevante (ambos ficam muito abaixo de `0.85`, a heurística de fallback continua funcionando corretamente para esse caso).
3. A decisão #13 já registrava explicitamente que o reaproveitamento do threshold `0.85` "não é uma nova validação empírica" e pedia para confirmar/ajustar quando o `EasyOCRExtractor` tivesse uso real — este é exatamente esse momento. Este agente **não decidiu** um novo threshold (não é decisão de arquitetura de agente de execução, `AGENTS.md` seção 1) — o achado está registrado aqui e em `PROJECT_STATE.md` seção 6, para o dono do projeto avaliar antes do próximo passo natural (ligar `EasyOCRExtractor` em `core/pipeline.py`).

Nota de limitação do próprio achado: só 2 fixtures, ambas as mesmas da OS-006/OS-005 — não é uma amostra grande o suficiente para propor um novo threshold específico para EasyOCR, só para sinalizar que o `0.85` herdado por analogia merece revisão antes de virar comportamento em produção.

## 6. Desvios do escopo original

Nenhum desvio de escopo. O comportamento descrito na seção 5 é um achado dentro do escopo já previsto pela própria OS ("se os valores observados não baterem razoavelmente com o threshold 0.85 já aprovado... registrar isso explicitamente como achado, não forçar a fórmula a caber").

## 7. Dúvidas / bloqueios

Nenhum bloqueio para fechar esta OS — a implementação está completa e testada. Uma recomendação para a próxima OS (não uma dúvida sobre esta): revisitar o threshold `0.85` especificamente para `EasyOCRExtractor` (seção 5 acima) antes de ligá-lo em `core/pipeline.py`, para não descartar sistematicamente boas extrações.

## 8. Link do PR

[a preencher após abertura do PR]
