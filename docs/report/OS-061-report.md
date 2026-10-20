# OS-061 — Relatório de entrega

**Data:** 29/09/2026
**Branch:** `os/061-comando-unico`
**Commit(s) relevante(s):** `ae82b96` (OS), `55c40e1` (Red), `6b383be` (Green)

## 1. Resumo do que foi feito

`scripts/run_app.py` sobe a API e o worker juntos e os mantém vivendo e morrendo
juntos. `RUNBOOK.md` passou a tratar esse comando como caminho principal, com os
dois terminais como alternativa. Item 57 do backlog.

## 2. Checklist de DoD

### Padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit Red `55c40e1` precede o Green `6b383be`
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 488 → **502 passando**
- [x] Código segue os contratos de `ARQUITETURA.md` — nenhum contrato tocado; o script é um invólucro
- [x] Nenhuma chamada real a API paga nos testes — não há rede nos testes desta OS
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-061-report.md`
- [x] PR aberto com título `[OS-061] ...`

### Específico (seção 4 da OS)

- [x] O comando sobe API e worker
- [x] Os processos usam o **mesmo** interpretador que roda o script
- [x] Host e porta configuráveis, com o padrão do `RUNBOOK.md`
- [x] Quando um processo morre, o outro é encerrado
- [x] O comando diz qual processo morreu e com que código
- [x] O código de saída do comando é o do processo que morreu
- [x] `Ctrl+C` encerra os dois e sai com 0
- [x] Processo que ignora o encerramento gentil é morto à força
- [x] O comando imprime a URL do player
- [x] `RUNBOOK.md` documenta o comando único como caminho principal
- [x] Nenhum teste existente quebra

## 3. Testes escritos

14 novos, **todos com a criação de processo injetada** — nenhum servidor sobe na suíte.

| Teste | Passou? |
|---|---|
| comandos incluem API e worker / usam `sys.executable` / chamam uvicorn e `worker.tasks` | ✅ |
| host e porta configuráveis / padrões batem com o `RUNBOOK.md` | ✅ |
| supervisor sobe todos os processos | ✅ |
| morte de um encerra o outro | ✅ |
| relata qual morreu e com que código | ✅ |
| código de saída é o do processo morto | ✅ |
| imprime a URL do player | ✅ |
| `Ctrl+C` devolve 0 e encerra os dois | ✅ |
| processo teimoso é morto após a carência / processo educado não é morto | ✅ |

Todos em `tests/unit/test_run_app_os061.py`.

Commit "Red" antes do "Green"? **[x] Sim** — o Red falhava na coleta (`scripts/run_app.py` não existia).

## 4. Saída de comandos relevantes

### Suíte completa e lint

```
502 passed, 2 warnings in 14.45s
All checks passed!     (scripts/run_app.py, tests/unit/test_run_app_os061.py)
```

Os 5 erros restantes de `ruff check scripts/` são **pré-existentes**, em
`spike_ocr_confidence.py` e `validate_normalizer.py`, que esta OS não toca.

### Verificação com processos reais

Além dos testes com processo injetado, o comando foi executado de verdade.

**Os dois sobem, e a API responde:**

```
Subindo API...
Subindo worker...
Player em http://127.0.0.1:8000/  (Ctrl+C encerra os dois)

$ pgrep -af "uvicorn api.main|worker.tasks"
50095 /home/dinei/DEV/listening/venv/bin/python -m uvicorn api.main:app
50096 /home/dinei/DEV/listening/venv/bin/python -m worker.tasks

$ curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:8000/books
HTTP 200
```

**O cenário de 13/08/2026, impedido** — matando só o `uvicorn`, o worker cai junto:

```
$ kill 50095
API encerrou com código -15. Derrubando o resto.

$ pgrep -af "uvicorn api.main|worker.tasks"
(nada)
```

**`Ctrl+C` (SIGINT) encerra os dois com código 0:**

```
Encerrando os dois processos.
exit=0
$ pgrep -af "uvicorn api.main|worker.tasks"
(nada)
```

## 5. Desvios do escopo original

Nenhum desvio de escopo: os arquivos tocados são os declarados
(`scripts/run_app.py`, `RUNBOOK.md`, testes).

**Dois erros meus durante a execução, ambos nos testes:**

1. **Dois testes entraram em laço infinito** e travaram a suíte. O `FakeProcess`
   padrão nascia com `exit_code=None` — nunca morria — e o supervisor roda até o
   primeiro morto, com `sleep` injetado como no-op. Corrigido fazendo os falsos
   sem morte específica nascerem já encerrados, com a razão registrada na
   docstring do helper.
2. **Matei meu próprio shell** ao tentar encerrar o teste travado: o padrão do
   `pkill -f` casava também com a linha de comando que o continha. Sem efeito
   sobre o resultado — só custou uma rodada para recuperar o estado.

**`scripts/__init__.py` foi criado e depois removido.** Achei que seria
necessário para `from scripts import run_app`; verifiquei que o pacote de espaço
de nomes do Python 3 resolve sem ele, e tirei em vez de deixar um arquivo que
muda a semântica da pasta sem precisar.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Três observações:

1. **Isto não substitui o heartbeat da OS-051, e não deveria.** O comando único
   evita a assimetria quando alguém o usa; quem subir os processos à mão (para
   ver os logs separados, o que o `RUNBOOK.md` mantém documentado) continua
   podendo esquecer o worker — e é aí que o aviso do player age. As duas defesas
   cobrem caminhos diferentes.

2. **É desenvolvimento local, não supervisão de produção.** Não há reinício
   automático, log estruturado nem integração com systemd/Docker. Está declarado
   fora de escopo na OS, e o item 57 fala de desenvolvimento local.

3. **A saída dos dois processos vai misturada para o mesmo terminal.** É o custo
   de juntá-los, e é por isso que os dois terminais continuam documentados como
   alternativa legítima em vez de removidos.

## 7. Link do PR

Ver o PR aberto contra `main` com título `[OS-061] Um comando para subir a aplicação inteira`.
