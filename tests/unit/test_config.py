import os

from core.config import load_config


def test_config_loads_extractor_and_speaker_from_yaml():
    config = load_config()
    assert config.extractor == "pymupdf"
    assert config.speaker == "kokoro"


def test_config_loads_queue_from_yaml():
    config = load_config()
    assert config.queue == "sqlite"


# --- OS-055: chaves vindas de .env -------------------------------------------


def test_load_env_file_reads_keys_from_dotenv(tmp_path, monkeypatch):
    """O dono pediu para pôr a chave num .env; python-dotenv já estava no
    requirements.txt desde sempre, declarado e nunca usado."""
    from core.config import load_env_file

    arquivo = tmp_path / ".env"
    arquivo.write_text("OPENAI_API_KEY=chave-do-arquivo\n")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_env_file(str(arquivo))

    assert os.environ["OPENAI_API_KEY"] == "chave-do-arquivo"


def test_load_env_file_does_not_override_existing_variable(tmp_path, monkeypatch):
    """Variável já exportada no shell vence o arquivo — senão um .env esquecido
    sobrescreveria silenciosamente a chave que a pessoa acabou de exportar."""
    from core.config import load_env_file

    arquivo = tmp_path / ".env"
    arquivo.write_text("OPENAI_API_KEY=do-arquivo\n")
    monkeypatch.setenv("OPENAI_API_KEY", "do-shell")

    load_env_file(str(arquivo))

    assert os.environ["OPENAI_API_KEY"] == "do-shell"


def test_load_env_file_is_silent_when_file_is_absent(tmp_path):
    """Sem .env o app continua funcionando pelo ambiente, sem erro."""
    from core.config import load_env_file

    load_env_file(str(tmp_path / "nao-existe.env"))
