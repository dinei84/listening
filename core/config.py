import os
from dataclasses import dataclass

import yaml

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


def load_config(path: str = _DEFAULT_CONFIG_PATH) -> Config:
    """Carrega config.yaml e retorna os nomes de extractor, speaker e queue configurados."""
    with open(path) as f:
        data = yaml.safe_load(f)
    retry = data.get("retry", {})
    return Config(
        extractor=data["extractor"],
        speaker=data["speaker"],
        queue=data["queue"],
        max_cost_per_book=data.get("max_cost_per_book"),
        fallback_speaker=data.get("fallback_speaker", "kokoro"),
        retry_max_attempts=retry.get("max_attempts", 3),
        retry_base_delay_seconds=retry.get("base_delay_seconds", 1.0),
        retry_max_delay_seconds=retry.get("max_delay_seconds", 30.0),
    )
