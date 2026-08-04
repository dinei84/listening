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


def load_config(path: str = _DEFAULT_CONFIG_PATH) -> Config:
    """Carrega config.yaml e retorna os nomes de extractor, speaker e queue configurados."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(
        extractor=data["extractor"], speaker=data["speaker"], queue=data["queue"]
    )
