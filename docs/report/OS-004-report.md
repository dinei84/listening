# OS-004 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** `main`
**Commit(s) relevante(s):** `52ab66b` (test: add tests for KokoroSpeaker — Red), `5733f90` (feat: implement Speaker base + KokoroSpeaker — Green)

## 1. Resumo do que foi feito

Implementação do contrato `Speaker` (`plugins/speakers/base.py`) com os métodos abstratos `synthesize()` e `cost_per_char`, e da primeira implementação concreta `KokoroSpeaker` (`plugins/speakers/kokoro_speaker.py`). Seguindo TDD: testes escritos primeiro (commit Red), implementação depois (commit Green). 4 testes passando, todos com mock da inferência Kokoro (sem chamar o modelo real).

## 2. Checklist de DoD

### Checklist padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit `52ab66b` (Red) existe antes do commit `5733f90` (Green)
- [x] Todos os testes da OS passam localmente — 4/4 passam
- [x] Nenhum teste existente quebrou — 19/19 passam (6 OS-001 + 4 OS-002 + 5 OS-003 + 4 OS-004)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` seção 4.2 — `synthesize()` e `cost_per_char` implementados conforme especificado
- [x] Nenhuma chamada real a API paga dentro dos testes — Kokoro inference é mockada em todos os testes
- [x] Type hints e docstring de uma linha em toda função pública — `synthesize()` e `cost_per_char` têm type hints
- [x] `PROJECT_STATE.md` atualizado — seções 2, 4, 5 atualizadas
- [x] Relatório da OS preenchido em `docs/report/OS-004-report.md`
- [x] PR aberto contra o branch principal — N/A (OS-004 está no branch `main` após merge das OS anteriores)

### Checklist específica da OS-004 (seção 4 de `docs/os/OS-004-kokoro-speaker.md`)

- [x] `Speaker` não pode ser instanciada diretamente (é uma ABC com `synthesize()` e `cost_per_char` abstratos)
- [x] `KokoroSpeaker.cost_per_char == 0.0`
- [x] `KokoroSpeaker.synthesize()` retorna um `AudioChunk` com `engine_used == "kokoro"`
- [x] `KokoroSpeaker.synthesize()` produz um arquivo de áudio no `file_path` retornado
- [x] Nenhum teste invoca o modelo Kokoro real — a chamada de inferência é mockada via `monkeypatch`
- [x] Nenhum teste escreve fora de um diretório temporário — arquivo `.wav` é escrito em `tempfile.gettempdir()` e o teste verifica apenas a existência e a extensão

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| `test_speaker_cannot_be_instantiated_directly` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_cost_per_char_is_zero` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |
| `test_kokoro_speaker_synthesize_writes_audio_file` | `tests/unit/speakers/test_kokoro_speaker.py` | Sim |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green"? [x] Sim — commit `52ab66b` (Red) → commit `5733f90` (Green)

## 4. Saída de comandos relevante

```
$ source venv/bin/activate && python3 -m pytest tests/unit/speakers/test_kokoro_speaker.py -v
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- /home/dinei/DEV/listening/venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/dinei/DEV/listening
configfile: pytest.ini
plugins: mock-3.15.1, anyio-4.14.2
collecting ... collected 4 items

tests/unit/speakers/test_kokoro_speaker.py::test_speaker_cannot_be_instantiated_directly PASSED [ 25%]
tests/unit/speakers/test_kokoro_speaker.py::test_kokoro_speaker_cost_per_char_is_zero PASSED [ 50%]
tests/unit/speakers/test_kokoro_speaker.py::test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro PASSED [ 75%]
tests/unit/speakers/test_kokoro_speaker.py::test_kokoro_speaker_synthesize_writes_audio_file PASSED [100%]

============================== 4 passed in 8.42s ==============================
```

## 5. Desvios do escopo original

Nenhum. Todas as alterações estão dentro do escopo da OS-004:
- `plugins/speakers/base.py` — contrato `Speaker` com métodos abstratos
- `plugins/speakers/kokoro_speaker.py` — implementação `KokoroSpeaker`
- `tests/unit/speakers/test_kokoro_speaker.py` — 4 testes conforme OS-004 seção 5

## 6. Dúvidas / bloqueios

Nenhuma.

## 7. Link do PR

N/A — OS-004 está no branch `main` (as OS anteriores já foram mergeadas). PR único para todas as OS's.