# OS-061 — Um comando para subir a aplicação inteira

## 1. Objetivo

Eliminar a classe de falha "está travado?" que nasce de subir só metade da
aplicação, com um comando único que sobe a API e o worker juntos — e derruba os
dois quando um morre.

Item 57 do backlog, achado em 13/08/2026.

## 2. Escopo

### O problema, e por que a OS-051 não o fecha

A aplicação são **dois processos**, e faltar um é invisível de formas diferentes:

| O que falta | O que o usuário vê | Coberto? |
|---|---|---|
| worker | livro parado em `uploaded`, com a mesma tela de sempre | **sim**, pela OS-051 (heartbeat + aviso no player) |
| API | nada: não há player | **não** — não existe onde avisar |

O segundo caso é real e custou tempo do dono em 13/08/2026: o **worker estava
rodando, o `uvicorn` não**. O livro parou em `pending_confirmation`, que é o
comportamento **correto** da trava da OS-042, e a confirmação depende de um botão
que só existe no player, que só existe se a API estiver de pé.

Aviso não resolve esse lado — quando falta a API, não há superfície para avisar
em lugar nenhum. O que resolve é a assimetria não acontecer.

### Alterados

- `scripts/run_app.py` — **novo**. Sobe os dois, encerra os dois juntos.
- `RUNBOOK.md` — o comando único como caminho principal; os dois terminais viram
  a alternativa para quem quer os logs separados.
- Testes correspondentes.

### Decisão de comportamento: derrubar os dois

Se um dos processos morre, o outro é encerrado e o comando termina com o código
de saída de quem morreu. É a decisão de 13/08/2026 do dono — *"prefiro falha
rápida com aviso"* — aplicada aqui: meia aplicação de pé é exatamente o estado que
este item existe para impedir, e mantê-la viva reproduziria o problema por outro
caminho.

### Fora de escopo

- **Health check da API antes de declarar pronto.** Se o `uvicorn` não consegue
  subir (porta ocupada), ele sai, e o supervisor já trata isso como processo
  morto. Um check ativo acrescentaria espera e complexidade sem cobrir caso novo.
- **Rodar mais de um worker.** A decisão #11 é um worker por vez, e a OS-022
  depende disso.
- **Supervisão em produção** (systemd, Docker, reinício automático). Este é o
  caminho de desenvolvimento local, que é o que o item 57 descreve.
- **Alvo de Makefile.** O item cita "script **ou** alvo de Makefile"; um script
  Python roda igual em Linux, macOS e Windows e é testável, o Makefile não.

## 3. Contratos envolvidos

Nenhum contrato muda, e nenhum arquivo de produção existente é alterado — o
script é um invólucro que chama `uvicorn api.main:app` e `python -m worker.tasks`
exatamente como o `RUNBOOK.md` já mandava fazer à mão.

O supervisor recebe a função de criar processo por injeção, para os testes
exercitarem morte, encerramento e `Ctrl+C` **sem subir servidor de verdade**.

O comando usa `sys.executable`, e não `"python"`: assim
`venv/bin/python scripts/run_app.py` funciona sem ativar o venv, e é impossível
o script subir os processos num interpretador diferente do seu.

## 4. Critérios de aceite

- [ ] O comando sobe API e worker
- [ ] Os processos são lançados com o **mesmo** interpretador que roda o script
- [ ] Host e porta são configuráveis, com o padrão do `RUNBOOK.md` (127.0.0.1:8000)
- [ ] Quando um processo morre, o outro é encerrado
- [ ] O comando diz **qual** processo morreu e com que código de saída
- [ ] O código de saída do comando é o do processo que morreu
- [ ] `Ctrl+C` encerra os dois e sai com 0
- [ ] Processo que ignora o encerramento gentil é morto à força
- [ ] O comando imprime a URL do player depois de subir os dois
- [ ] `RUNBOOK.md` documenta o comando único como caminho principal
- [ ] Nenhum teste existente quebra (488 hoje)

## 5. Testes exigidos (mínimo)

- `test_build_processes_includes_api_and_worker`
- `test_build_processes_uses_the_running_interpreter`
- `test_build_processes_honours_host_and_port`
- `test_supervisor_starts_every_process`
- `test_supervisor_stops_the_others_when_one_exits`
- `test_supervisor_reports_which_process_died`
- `test_supervisor_exit_code_is_the_dead_process_exit_code`
- `test_supervisor_returns_zero_on_keyboard_interrupt`
- `test_supervisor_terminates_everything_on_keyboard_interrupt`
- `test_supervisor_kills_process_that_ignores_terminate`
- `test_supervisor_prints_player_url`

## 6. Relatório

Ver `docs/report/OS-061-report.md`.
