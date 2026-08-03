# OS-007 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** os/007-core-pipeline
**Commit(s) relevante(s):** 5042c78 (test: Red), 032c7ac (feat: Green)

## 1. Resumo do que foi feito

Implementado `plugins/registry.py` (`EXTRACTORS`/`SPEAKERS`), `core/config.py` (`load_config()`) e `core/pipeline.py` (`extract_with_fallback()` e `synthesize_text()`), ligando `PyMuPDFExtractor` → `TesseractOCR` e `KokoroSpeaker` numa orquestração síncrona em memória, sem importar nenhuma classe concreta de plugin fora do registry.

## 2. Checklist de DoD

### DoD padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação (commit `5042c78` "Red" existe antes de `032c7ac` "Green")
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou (33 testes no total, todos passando)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` (interfaces, nomes, estrutura de pastas)
- [x] Nenhuma chamada real a API paga dentro dos testes — tudo com dublês fake
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado (status dos componentes + seção 2)
- [x] Relatório criado em `docs/report/OS-007-report.md`
- [x] PR aberto contra o branch principal, com título `[OS-007] core/pipeline.py`

### DoD específico da OS (seção 4 de `docs/os/OS-007-core-pipeline.md`)

- [x] `plugins/registry.py` expõe `EXTRACTORS` com `"pymupdf"` e `"tesseract"`, e `SPEAKERS` com `"kokoro"`
- [x] `core/config.py` lê `config.yaml` e retorna os nomes de extractor/speaker configurados
- [x] A função de extração do pipeline usa o extractor primário configurado (`pymupdf` via `config.yaml`) quando `supports()` é `True`
- [x] A função de extração cai para `tesseract` quando `supports()` do primário é `False`
- [x] `ExtractedPage.confidence` do resultado final continua acessível para quem chama, mesmo quando baixo — não é descartado
- [x] A função de síntese chama o Speaker configurado e retorna `AudioChunk`(s) válidos, com `chapter_id` preenchido pelo chamador
- [x] Nenhum módulo, incluindo `core/pipeline.py`, importa uma classe concreta de plugin fora de `plugins/registry.py`
- [x] Testes usam extractors/speaker fake (dublês que implementam `Extractor`/`Speaker`) para isolar a orquestração — nenhum teste desta OS roda Tesseract/Kokoro de verdade
- [x] Nenhuma chamada de rede ou API paga

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_registry_extractors_contains_pymupdf_and_tesseract` | `tests/unit/test_registry.py` | Sim |
| `test_registry_speakers_contains_kokoro` | `tests/unit/test_registry.py` | Sim |
| `test_config_loads_extractor_and_speaker_from_yaml` | `tests/unit/test_config.py` | Sim |
| `test_pipeline_uses_primary_extractor_when_supports_true` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_pipeline_falls_back_to_tesseract_when_primary_supports_false` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_pipeline_exposes_confidence_even_when_low` | `tests/integration/test_pipeline_end_to_end.py` | Sim |
| `test_pipeline_synthesizes_extracted_text_with_configured_speaker` | `tests/integration/test_pipeline_end_to_end.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [x] Sim [ ] Não

## 4. Saída de comandos relevantes

Testes falhando antes da implementação (commit Red, `5042c78`):

```
tests/unit/test_registry.py:3: in <module>
    from plugins.registry import EXTRACTORS, SPEAKERS
E   ImportError: cannot import name 'EXTRACTORS' from 'plugins.registry'

tests/unit/test_config.py:1: in <module>
    from core.config import load_config
E   ImportError: cannot import name 'load_config' from 'core.config'

tests/integration/test_pipeline_end_to_end.py — 4 failed
E   AttributeError: <module 'core.config' ...> has no attribute 'load_config'
```

Suíte completa após a implementação (commit Green, `032c7ac`):

```
$ python -m pytest -q
.................................                                        [100%]
33 passed in 5.75s
```

`black --check` e `ruff check` nos arquivos tocados por esta OS: sem alterações pendentes, todos os checks passaram (um arquivo de teste foi reformatado automaticamente por `black` antes do commit Green).

## 5. Desvios do escopo original

Nenhum. O escopo declarado na seção 2 da OS (`plugins/registry.py`, `core/config.py`, `core/pipeline.py` com as duas funções de orquestração) foi implementado sem tocar em `processing/`, `storage/`, `worker/` ou `api/`, e sem introduzir nenhum plugin fora dos dois extractors e um speaker já existentes.

Uma decisão de implementação não literal na OS, mas necessária para cumprir o requisito de testabilidade com dublês (seção 4, item "Testes usam extractors/speaker fake"): `core/pipeline.py` referencia `core.config`/`plugins.registry` como módulos (`config_module.load_config()`, `registry_module.EXTRACTORS`) em vez de importar os nomes diretamente (`from core.config import load_config`), para que os testes de integração possam usar `monkeypatch.setattr` nesses módulos e substituir `EXTRACTORS`/`SPEAKERS`/`load_config` por dublês sem tocar em `Tesseract`/`Kokoro`/`PyMuPDF` reais. Isso não altera nenhum contrato de interface, apenas o estilo de import dentro do próprio `pipeline.py`.

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

https://github.com/dinei84/listening/pull/5
