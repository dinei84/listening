import os
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

_DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)


@dataclass
class Config:
    extractor: str
    speaker: str
    queue: str
    # Teto de segurança por livro (OS-042): estimativa acima disso não roda o Speaker
    # pago mesmo com confirmação — degrada para a voz local (fallback_speaker).
    max_cost_per_book: float | None = None
    fallback_speaker: str = "kokoro"
    # Retry de falha transitória (OS-043): quantas tentativas no total, o delay inicial
    # do backoff exponencial (dobra a cada tentativa) e o teto do delay.
    retry_max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0
    # Normalizador de texto (OS-038). "noop" (padrão) não toca a rede; "llm" usa um
    # endpoint compatível com OpenAI — a chave vem de variável de ambiente, nunca
    # do arquivo versionado.
    normalizer: str = "noop"
    normalizer_base_url: str = "https://api.openai.com/v1"
    normalizer_model: str = ""
    normalizer_api_key_env: str = "LLM_API_KEY"
    normalizer_cost_per_char: float = 0.0
    normalizer_divergence_ratio: float | None = None
    # Preparação prosódica (OS-054): segundo passe de LLM que só ajusta pontuação.
    # Desligado por padrão ("noop") — só faz rede se o dono ligar e fornecer a chave.
    prosody_normalizer: str = "noop"
    prosody_base_url: str = "https://api.openai.com/v1"
    prosody_model: str = ""
    prosody_api_key_env: str = "PROSODY_API_KEY"
    prosody_cost_per_char: float = 0.0
    prosody_divergence_ratio: float | None = None

    # Roteamento por expressividade (OS-056). Desligado por padrão: sem ele o
    # comportamento é exatamente o de antes, um motor para o livro inteiro.
    routing_enabled: bool = False
    routing_premium_speaker: str = "openai"
    routing_min_expressive: int = 3


DEFAULT_ENV_PATH = ".env"


def load_env_file(path: str = DEFAULT_ENV_PATH) -> None:
    """Carrega variáveis de ambiente de um arquivo .env, sem sobrescrever o que já está no ambiente; arquivo ausente é silencioso."""
    # `override=False` de propósito: variável exportada no shell vence o arquivo.
    # O contrário faria um .env esquecido sobrescrever calado a chave que a pessoa
    # acabou de exportar — o tipo de surpresa que já custou caro nesta sessão.
    load_dotenv(path, override=False)


# Carregado na importação porque tanto o worker quanto a API importam este módulo
# antes de qualquer leitura de chave. python-dotenv está no requirements.txt desde
# o começo do projeto, declarado e nunca usado até a OS-055.
load_env_file()


def load_config(path: str = _DEFAULT_CONFIG_PATH) -> Config:
    """Carrega config.yaml e retorna os nomes de extractor, speaker e queue configurados."""
    with open(path) as f:
        data = yaml.safe_load(f)
    retry = data.get("retry", {})
    norm = data.get("normalizer", {})
    prosody = data.get("prosody", {})
    routing = data.get("routing", {})
    return Config(
        extractor=data["extractor"],
        speaker=data["speaker"],
        queue=data["queue"],
        max_cost_per_book=data.get("max_cost_per_book"),
        fallback_speaker=data.get("fallback_speaker", "kokoro"),
        retry_max_attempts=retry.get("max_attempts", 3),
        retry_base_delay_seconds=retry.get("base_delay_seconds", 1.0),
        retry_max_delay_seconds=retry.get("max_delay_seconds", 30.0),
        normalizer=norm.get("name", "noop"),
        normalizer_base_url=norm.get("base_url", "https://api.openai.com/v1"),
        normalizer_model=norm.get("model", ""),
        normalizer_api_key_env=norm.get("api_key_env", "LLM_API_KEY"),
        normalizer_cost_per_char=norm.get("cost_per_char", 0.0),
        normalizer_divergence_ratio=norm.get("divergence_ratio"),
        prosody_normalizer=prosody.get("name", "noop"),
        prosody_base_url=prosody.get("base_url", "https://api.openai.com/v1"),
        prosody_model=prosody.get("model", ""),
        prosody_api_key_env=prosody.get("api_key_env", "PROSODY_API_KEY"),
        prosody_cost_per_char=prosody.get("cost_per_char", 0.0),
        prosody_divergence_ratio=prosody.get("divergence_ratio"),
        routing_enabled=routing.get("enabled", False),
        routing_premium_speaker=routing.get("premium_speaker", "openai"),
        routing_min_expressive=routing.get("min_expressive_sentences", 3),
    )
