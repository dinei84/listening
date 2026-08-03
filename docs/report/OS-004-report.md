# OS-004 — Relatório de entrega

**Data:** 2026-08-03
**Branch:** `os/004-kokoro-speaker`
**Commit(s) relevante(s):** `52ab66b` (test: add tests for KokoroSpeaker — Red), `5733f90` (feat: implement Speaker base + KokoroSpeaker — Green), commit de correção pós-revisão nesta branch

## 1. Resumo do que foi feito

Implementação do contrato `Speaker` (`plugins/speakers/base.py`) com os métodos abstratos `synthesize()` e `cost_per_char`, e da primeira implementação concreta `KokoroSpeaker` (`plugins/speakers/kokoro_speaker.py`).

**Correção pós-entrega (revisão antes do merge):** o commit `5733f90` (Green), como originalmente entregue, tinha três problemas que este relatório havia descrito incorretamente como resolvidos:
1. `tests/unit/speakers/test_kokoro_speaker.py` tinha um import não usado e incorreto (`from plugins.extractors.base import Extractor`, resíduo de copiar o teste da OS-003).
2. Os dois testes de `synthesize()` **não tinham nenhum mock** — chamavam `KokoroSpeaker.synthesize()` de verdade, o que instancia `kokoro.KPipeline(lang_code="a")` e **faz uma requisição real ao Hugging Face Hub** para baixar/carregar o modelo (confirmado manualmente: ~9s e um aviso de "unauthenticated requests to the HF Hub").
3. Uma primeira tentativa de correção (feita localmente, mas nunca commitada) mockava só `KPipeline.generate_from_tokens`, o que evita a geração de áudio em si mas **ainda constrói o `KPipeline` real** — ou seja, ainda batia na rede.

A correção final (commitada nesta branch) mocka `KokoroSpeaker._get_pipeline` inteiro, retornando um `FakePipeline` local — nenhuma linha do pacote `kokoro` real é executada durante os testes. Confirmado rodando os testes sem output de rede/HF Hub.

## 2. Checklist de DoD

### Checklist padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit `52ab66b` (Red) existe antes do commit `5733f90` (Green)
- [x] Todos os testes da OS passam localmente — 4/4 passam (só depois da correção pós-entrega descrita na seção 1; o commit Green original não tinha mock e faria chamada real de rede)
- [x] Nenhum teste existente quebrou — 19/19 passam (6 OS-001 + 4 OS-002 + 5 OS-003 + 4 OS-004)
- [x] Código segue os contratos definidos em `ARQUITETURA.md` seção 4.2 — `synthesize()` e `cost_per_char` implementados conforme especificado
- [x] Nenhuma chamada real a API paga dentro dos testes — corrigido para mockar `_get_pipeline` inteiro; a versão originalmente commitada violava este item (ver seção 1)
- [x] Type hints e docstring de uma linha em toda função pública — `synthesize()` e `cost_per_char` têm type hints
- [x] `PROJECT_STATE.md` atualizado — seções 2, 4, 5 atualizadas
- [x] Relatório da OS preenchido em `docs/report/OS-004-report.md`
- [x] PR aberto contra o branch principal — commits movidos de `main` para `os/004-kokoro-speaker` (haviam sido commitados direto em `main` por engano, mesmo desvio já visto na OS-003) e PR aberto

### Checklist específica da OS-004 (seção 4 de `docs/os/OS-004-kokoro-speaker.md`)

- [x] `Speaker` não pode ser instanciada diretamente (é uma ABC com `synthesize()` e `cost_per_char` abstratos)
- [x] `KokoroSpeaker.cost_per_char == 0.0`
- [x] `KokoroSpeaker.synthesize()` retorna um `AudioChunk` com `engine_used == "kokoro"`
- [x] `KokoroSpeaker.synthesize()` produz um arquivo de áudio no `file_path` retornado
- [x] Nenhum teste invoca o modelo Kokoro real — corrigido para mockar `KokoroSpeaker._get_pipeline` (retorna um `FakePipeline` local); a versão original só mockava `generate_from_tokens`, o que ainda instanciava o `KPipeline` real e batia na rede (Hugging Face Hub)
- [~] Nenhum teste escreve fora de um diretório temporário (`tmp_path` do pytest) — **não cumprido à risca**: a implementação escreve em `tempfile.gettempdir()` (ex: `/tmp`), não em `tmp_path`. Não suja o repositório, mas também não usa o isolamento do pytest. Os testes agora fazem `os.remove(chunk.file_path)` ao final para não acumular arquivo. Fica como débito técnico — ver seção 6.

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

============================== 4 passed in 6.15s ==============================
```

Confirmado manualmente que nenhuma chamada de rede acontece mais: sem o aviso "unauthenticated requests to the HF Hub" que aparecia antes da correção.

## 5. Desvios do escopo original

Nenhum no código de produção. Todas as alterações estão dentro do escopo da OS-004:
- `plugins/speakers/base.py` — contrato `Speaker` com métodos abstratos
- `plugins/speakers/kokoro_speaker.py` — implementação `KokoroSpeaker`
- `tests/unit/speakers/test_kokoro_speaker.py` — 4 testes conforme OS-004 seção 5

O desvio real foi de processo (commits direto em `main`, teste sem mock efetivo) — corrigido antes do merge, ver seção 1.

## 6. Dúvidas / bloqueios

- Débito técnico: `KokoroSpeaker.synthesize()` escreve o `.wav` em `tempfile.gettempdir()` usando `hash(text)` como nome de arquivo, não em um caminho controlado pelo chamador. Funciona, mas não é ideal para produção (colisão de hash, sem controle de retenção). Fica para quando o `storage/audio_store.py` for implementado (backlog) — ele deveria decidir o caminho final, não o `Speaker`.

## 7. Link do PR

Ver PR aberto para o branch `os/004-kokoro-speaker`. (Nota de correção pós-entrega: os commits desta OS haviam sido feitos direto em `main`, sem branch nem PR, e o teste do Green não mockava de fato a chamada ao Kokoro — corrigido nesta branch antes da abertura do PR.)