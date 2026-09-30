"""OS-061 — um comando sobe a API e o worker juntos (item 57 do backlog).

A aplicação são dois processos, e faltar um é invisível de formas diferentes: a
falta do worker é avisada pelo heartbeat da OS-051, mas a falta da API **não tem
como ser avisada**, porque sem API não há player. Em 13/08/2026 isso custou tempo
do dono — worker de pé, `uvicorn` não, livro parado em `pending_confirmation`
esperando um botão que não existia.

Todos os testes injetam a criação de processo: nenhum servidor sobe aqui.
"""

import sys

import pytest

from scripts import run_app


class FakeProcess:
    """Processo de mentira: controla quando "morre" e registra como foi encerrado."""

    def __init__(self, argv, exit_code=None, ignora_terminate=False):
        self.argv = argv
        self._exit_code = exit_code
        self.ignora_terminate = ignora_terminate
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._exit_code

    def morrer(self, code):
        self._exit_code = code

    def terminate(self):
        self.terminated = True
        if not self.ignora_terminate:
            self._exit_code = self._exit_code if self._exit_code is not None else -15

    def kill(self):
        self.killed = True
        self._exit_code = -9

    def wait(self, timeout=None):
        if self._exit_code is None:
            raise TimeoutError("não encerrou no prazo")
        return self._exit_code


def _supervisor(processos=None, **kwargs):
    """Monta um supervisor com spawn falso e sem dormir de verdade."""
    criados = []

    def spawn(argv):
        indice = len(criados)
        if processos is not None and indice < len(processos):
            processo = processos[indice]
            processo.argv = argv
        else:
            processo = FakeProcess(argv)
        criados.append(processo)
        return processo

    linhas = []
    sup = run_app.Supervisor(
        run_app.build_processes(),
        spawn=spawn,
        sleep=lambda _: None,
        log=linhas.append,
        **kwargs,
    )
    return sup, criados, linhas


# --------------------------------------------------------------------------
# Os comandos
# --------------------------------------------------------------------------


def test_build_processes_includes_api_and_worker():
    nomes = [spec.name for spec in run_app.build_processes()]
    assert "API" in nomes
    assert "worker" in nomes


def test_build_processes_uses_the_running_interpreter():
    """`sys.executable`, e não "python": assim `venv/bin/python scripts/run_app.py`
    funciona sem ativar o venv, e é impossível subir os processos noutro
    interpretador que não tenha as dependências."""
    for spec in run_app.build_processes():
        assert spec.argv[0] == sys.executable


def test_build_processes_runs_uvicorn_and_the_worker_module():
    comandos = {spec.name: spec.argv for spec in run_app.build_processes()}
    assert "uvicorn" in comandos["API"]
    assert "api.main:app" in comandos["API"]
    assert "worker.tasks" in comandos["worker"]


def test_build_processes_honours_host_and_port():
    api = next(s for s in run_app.build_processes(host="0.0.0.0", port=9001) if s.name == "API")
    assert "0.0.0.0" in api.argv
    assert "9001" in api.argv


def test_build_processes_defaults_match_the_runbook():
    api = next(s for s in run_app.build_processes() if s.name == "API")
    assert "127.0.0.1" in api.argv
    assert "8000" in api.argv


# --------------------------------------------------------------------------
# Supervisão
# --------------------------------------------------------------------------


def test_supervisor_starts_every_process():
    sup, criados, _ = _supervisor()
    # Os dois morrem de imediato para o laço não girar para sempre.
    sup.run()
    assert len(criados) == 2


def test_supervisor_stops_the_others_when_one_exits():
    """Meia aplicação de pé é exatamente o estado que este item existe para
    impedir: manter o worker vivo sem API reproduziria o problema de 13/08."""
    api = FakeProcess(None)
    worker = FakeProcess(None)
    sup, criados, _ = _supervisor([api, worker])

    api.morrer(1)
    sup.run()

    assert worker.terminated is True


def test_supervisor_reports_which_process_died():
    api = FakeProcess(None)
    worker = FakeProcess(None)
    sup, _, linhas = _supervisor([api, worker])

    worker.morrer(3)
    sup.run()

    texto = "\n".join(linhas)
    assert "worker" in texto
    assert "3" in texto


def test_supervisor_exit_code_is_the_dead_process_exit_code():
    """Porta ocupada faz o uvicorn sair diferente de zero; o comando precisa
    propagar isso, senão um script que o chame acha que deu certo."""
    api = FakeProcess(None)
    worker = FakeProcess(None)
    sup, _, _ = _supervisor([api, worker])

    api.morrer(2)
    assert sup.run() == 2


def test_supervisor_prints_player_url():
    sup, _, linhas = _supervisor()
    sup.run()
    assert any("8000" in linha for linha in linhas)


# --------------------------------------------------------------------------
# Encerramento
# --------------------------------------------------------------------------


def test_supervisor_returns_zero_on_keyboard_interrupt():
    api = FakeProcess(None)
    worker = FakeProcess(None)

    def sleep_que_interrompe(_):
        raise KeyboardInterrupt

    sup, _, _ = _supervisor([api, worker])
    sup._sleep = sleep_que_interrompe
    assert sup.run() == 0


def test_supervisor_terminates_everything_on_keyboard_interrupt():
    api = FakeProcess(None)
    worker = FakeProcess(None)

    sup, _, _ = _supervisor([api, worker])
    sup._sleep = lambda _: (_ for _ in ()).throw(KeyboardInterrupt)
    sup.run()

    assert api.terminated is True
    assert worker.terminated is True


def test_supervisor_kills_process_that_ignores_terminate():
    """Worker no meio de um chunk pode demorar a sair; depois da carência, mata."""
    api = FakeProcess(None)
    teimoso = FakeProcess(None, ignora_terminate=True)

    sup, _, _ = _supervisor([api, teimoso])
    api.morrer(0)
    sup.run()

    assert teimoso.terminated is True
    assert teimoso.killed is True


def test_supervisor_does_not_kill_a_process_that_exited_politely():
    api = FakeProcess(None)
    worker = FakeProcess(None)

    sup, _, _ = _supervisor([api, worker])
    api.morrer(0)
    sup.run()

    assert worker.terminated is True
    assert worker.killed is False
