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


def load_config(path: str = _DEFAULT_CONFIG_PATH) -> Config:
    """Carrega config.yaml e retorna os nomes de extractor, speaker e queue configurados."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(
        extractor=data["extractor"],
        speaker=data["speaker"],
        queue=data["queue"],
        max_cost_per_book=data.get("max_cost_per_book"),
        fallback_speaker=data.get("fallback_speaker", "kokoro"),
    )
