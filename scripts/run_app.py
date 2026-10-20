"""Sobe a API e o worker juntos, e derruba os dois quando um morre (OS-061).

A aplicação são dois processos, e faltar um é invisível de formas diferentes: a
falta do worker é avisada no player pelo heartbeat da OS-051, mas a falta da API
**não tem como ser avisada** — sem API não há player onde mostrar aviso nenhum.
Em 13/08/2026 isso custou tempo do dono: worker de pé, `uvicorn` não, e o livro
parado em `pending_confirmation` esperando um botão que não existia.

Uso:

    venv/bin/python scripts/run_app.py
    venv/bin/python scripts/run_app.py --port 9000
"""

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# De quanto em quanto tempo o supervisor checa se algum processo morreu.
POLL_INTERVAL_SECONDS = 0.5

# Quanto esperar o encerramento gentil antes de matar à força. O worker pode
# estar no meio de um chunk, então a carência não pode ser curta demais.
TERMINATE_GRACE_SECONDS = 10.0


@dataclass(frozen=True)
class ProcessSpec:
    """Um processo a ser supervisionado: nome legível e a linha de comando."""

    name: str
    argv: list[str]


def build_processes(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    python_executable: str | None = None,
) -> list[ProcessSpec]:
    """Monta as linhas de comando da API e do worker, com o interpretador que roda este script."""
    # `sys.executable`, e não "python": assim `venv/bin/python scripts/run_app.py`
    # funciona sem ativar o venv, e é impossível subir os processos num
    # interpretador que não tenha as dependências instaladas.
    executavel = python_executable or sys.executable
    return [
        ProcessSpec(
            "API",
            [
                executavel,
                "-m",
                "uvicorn",
                "api.main:app",
                "--host",
                host,
                "--port",
                str(port),
            ],
        ),
        ProcessSpec("worker", [executavel, "-m", "worker.tasks"]),
    ]


class Supervisor:
    """Sobe um conjunto de processos e mantém a regra de que eles vivem e morrem juntos."""

    def __init__(
        self,
        specs: list[ProcessSpec],
        spawn=None,
        sleep=time.sleep,
        log=print,
        grace_seconds: float = TERMINATE_GRACE_SECONDS,
    ):
        self._specs = specs
        self._spawn = spawn or (lambda argv: subprocess.Popen(argv))
        self._sleep = sleep
        self._log = log
        self._grace = grace_seconds

    def run(self) -> int:
        """Sobe tudo, espera, e devolve o código de saída do processo que morreu (0 em Ctrl+C)."""
        processos: list[tuple[str, object]] = []
        for spec in self._specs:
            self._log(f"Subindo {spec.name}...")
            processos.append((spec.name, self._spawn(spec.argv)))

        self._anunciar()

        try:
            while True:
                morto = self._primeiro_morto(processos)
                if morto is not None:
                    nome, codigo = morto
                    # Falha rápida com aviso (decisão do dono, 13/08/2026): meia
                    # aplicação de pé é justamente o estado que esta OS existe
                    # para impedir, então o resto vai junto.
                    self._log(
                        f"\n{nome} encerrou com código {codigo}. Derrubando o resto."
                    )
                    self._encerrar(processos, exceto=nome)
                    return codigo
                self._sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            self._log("\nEncerrando os dois processos.")
            self._encerrar(processos)
            return 0

    def _anunciar(self) -> None:
        """Diz onde o player está, para ninguém precisar lembrar a porta."""
        api = next((s for s in self._specs if s.name == "API"), None)
        if api is None:
            return
        host = api.argv[api.argv.index("--host") + 1]
        port = api.argv[api.argv.index("--port") + 1]
        self._log(f"Player em http://{host}:{port}/  (Ctrl+C encerra os dois)")

    @staticmethod
    def _primeiro_morto(processos) -> tuple[str, int] | None:
        for nome, processo in processos:
            codigo = processo.poll()
            if codigo is not None:
                return nome, codigo
        return None

    def _encerrar(self, processos, exceto: str | None = None) -> None:
        """Encerra os processos com carência, e mata os que ignorarem o pedido."""
        alvos = [(n, p) for n, p in processos if n != exceto and p.poll() is None]
        for _, processo in alvos:
            processo.terminate()
        for nome, processo in alvos:
            try:
                processo.wait(timeout=self._grace)
            except Exception:  # noqa: BLE001 — TimeoutExpired do subprocess ou equivalente
                self._log(f"{nome} não encerrou em {self._grace:.0f}s; matando.")
                processo.kill()


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Sobe a API e o worker do audiobook player juntos."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    return Supervisor(build_processes(host=args.host, port=args.port)).run()


if __name__ == "__main__":
    raise SystemExit(main())
