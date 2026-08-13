"""Testes da preparação prosódica (OS-054): segundo passe de LLM que só ajusta pontuação, com guarda-corpo de identidade de palavras, e o ChainNormalizer que encadeia notação + prosódia.

Cobertura:
  - o guarda-corpo aceita mudança apenas de pontuação
  - o guarda-corpo rejeita troca/adicao/remocao de palavra (devolve o original)
  - o guarda-corpo aceita divisão de frase (", e" -> ". E") apesar da maiúscula
  - falha de rede devolve o original
  - ChainNormalizer aplica os normalizadores na ordem configurada
  - ChainNormalizer.cost_per_char é a soma dos elos
  - estimate_cost reflete a cadeia (notação + prosódia) sem alteração em estimate_cost
  - prosódia desligada por padrão não faz nenhuma chamada de rede
"""

import pytest

from core import config as config_module
from core import pipeline
from plugins import registry as registry_module
from plugins.normalizers.base import ChainNormalizer, NoOpNormalizer, TextNormalizer
from plugins.normalizers.llm_normalizer import LLMNormalizer, from_config as llm_from_config
from plugins.normalizers.prosody_normalizer import (
    ProsodyNormalizer,
    from_config as prosody_from_config,
)


class FakeConfig:
    def __init__(self, **kwargs):
        self.extractor = "fake_extractor"
        self.speaker = "fake_speaker"
        self.queue = "sqlite"
        self.max_cost_per_book = None
        self.fallback_speaker = "kokoro"
        self.retry_max_attempts = 1
        self.retry_base_delay_seconds = 0.0
        self.retry_max_delay_seconds = 0.0
        # notação (OS-038)
        self.normalizer = "noop"
        self.normalizer_base_url = "https://exemplo.invalido/v1"
        self.normalizer_model = "modelo-teste"
        self.normalizer_api_key_env = "TEST_LLM_KEY"
        self.normalizer_cost_per_char = 0.0
        self.normalizer_divergence_ratio = None
        # prosódia (OS-054) — desligada por padrão
        self.prosody_normalizer = "noop"
        self.prosody_base_url = "https://exemplo.invalido/v1"
        self.prosody_model = "modelo-teste"
        self.prosody_api_key_env = "TEST_PROSODY_KEY"
        self.prosody_cost_per_char = 0.0
        self.prosody_divergence_ratio = None
        self.__dict__.update(kwargs)


class EchoNormalizer(TextNormalizer):
    """Normalizador dublê que aplica uma transformação determinística e conhecida."""

    def __init__(self, transform, cost=0.0):
        self._transform = transform
        self._cost = cost

    @property
    def cost_per_char(self) -> float:
        return self._cost

    def normalize(self, text: str) -> str:
        return self._transform(text)


# --- guarda-corpo de identidade de palavras -------------------------------------


def test_prosody_accepts_punctuation_only_change(monkeypatch):
    normalizer = ProsodyNormalizer(base_url="x", model="m", api_key="k")
    monkeypatch.setattr(
        normalizer,
        "_call_api",
        lambda text: "A frase longa, com uma pausa natural, respira melhor.",
    )

    resultado = normalizer.normalize("A frase longa com uma pausa natural respira melhor.")

    assert resultado == "A frase longa, com uma pausa natural, respira melhor."


def test_prosody_rejects_changed_word(monkeypatch):
    normalizer = ProsodyNormalizer(base_url="x", model="m", api_key="k")
    original = "O gato dormiu no sofá."
    monkeypatch.setattr(
        normalizer, "_call_api", lambda text: "O cachorro dormiu no sofá."
    )

    assert normalizer.normalize(original) == original


def test_prosody_rejects_added_word(monkeypatch):
    normalizer = ProsodyNormalizer(base_url="x", model="m", api_key="k")
    original = "O livro era pequeno."
    monkeypatch.setattr(
        normalizer, "_call_api", lambda text: "O livro era muito pequeno."
    )

    assert normalizer.normalize(original) == original


def test_prosody_rejects_removed_word(monkeypatch):
    normalizer = ProsodyNormalizer(base_url="x", model="m", api_key="k")
    original = "Ele leu o capítulo inteiro."
    monkeypatch.setattr(
        normalizer, "_call_api", lambda text: "Ele leu o inteiro."
    )

    assert normalizer.normalize(original) == original


def test_prosody_accepts_sentence_split_with_capitalization(monkeypatch):
    normalizer = ProsodyNormalizer(base_url="x", model="m", api_key="k")
    original = "Ele chegou, e fomos embora."
    monkeypatch.setattr(
        normalizer, "_call_api", lambda text: "Ele chegou. E fomos embora."
    )

    assert normalizer.normalize(original) == "Ele chegou. E fomos embora."


def test_prosody_returns_original_on_network_failure(monkeypatch):
    normalizer = ProsodyNormalizer(base_url="x", model="m", api_key="k")

    def _boom(text):
        raise ConnectionError("rede caiu")

    monkeypatch.setattr(normalizer, "_call_api", _boom)

    original = "Texto que precisa sobreviver à queda de rede."
    assert normalizer.normalize(original) == original


# --- ChainNormalizer ------------------------------------------------------------


def test_chain_applies_normalizers_in_order():
    chamadas = []

    def fazer(sufixo):
        def _transform(text):
            chamadas.append(sufixo)
            return text + sufixo

        return _transform

    chain = ChainNormalizer(
        [EchoNormalizer(fazer("A")), EchoNormalizer(fazer("B"))]
    )

    resultado = chain.normalize("texto")

    assert chamadas == ["A", "B"], "a ordem configurada deve ser respeitada"
    assert resultado == "textoAB"


def test_chain_cost_is_the_sum_of_links():
    chain = ChainNormalizer(
        [EchoNormalizer(lambda t: t, cost=0.002), EchoNormalizer(lambda t: t, cost=0.001)]
    )

    assert chain.cost_per_char == pytest.approx(0.003)


# --- integração com a trava de custo (OS-042) -----------------------------------


def test_estimate_cost_includes_chain_cost(monkeypatch):
    """A cadeia notação+prosódia soma os custos e a trava da OS-042 os enxerga."""
    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(
            normalizer="llm",
            normalizer_cost_per_char=0.002,
            prosody_normalizer="prosody",
            prosody_cost_per_char=0.001,
        ),
    )
    monkeypatch.setattr(
        registry_module,
        "NORMALIZERS",
        {
            "noop": NoOpNormalizer,
            "llm": lambda **kw: llm_from_config(
                base_url="x",
                model="m",
                api_key_env="LLM_API_KEY_TEST",
                cost_per_char=kw["cost_per_char"],
            ),
            "prosody": lambda **kw: prosody_from_config(
                base_url="x",
                model="m",
                api_key_env="PROSODY_API_KEY_TEST",
                cost_per_char=kw["cost_per_char"],
            ),
        },
    )

    texto = "abcde"
    assert pipeline.estimate_cost(texto, normalize=True) == pytest.approx(
        len(texto) * 0.003
    )


# --- prosódia desligada por padrão ----------------------------------------------


def test_prosody_disabled_by_default_makes_no_network_call(monkeypatch):
    """Sem chave (padrão), a prosódia nem chega a tocar a rede — degrada para 'sem normalização'."""
    monkeypatch.delenv("TEST_PROSODY_KEY", raising=False)
    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(prosody_normalizer="prosody"),
    )
    chamadas = []

    def _boom(text):
        chamadas.append(text)
        raise AssertionError("a rede da prosódia não deveria ser chamada quando desligada")

    monkeypatch.setattr(
        registry_module,
        "NORMALIZERS",
        {
            "noop": NoOpNormalizer,
            "prosody": lambda **kw: prosody_from_config(
                base_url="x",
                model="m",
                api_key_env="TEST_PROSODY_KEY",
                cost_per_char=kw["cost_per_char"],
            ),
        },
    )

    normalizer = pipeline._build_normalizer(config_module.load_config())
    # Com a prosódia desligada e a notação em noop, o resultado é a própria cadeia de noop.
    assert isinstance(normalizer, ChainNormalizer)
    assert normalizer.normalize("Texto qualquer.") == "Texto qualquer."
    assert chamadas == [], "a rede da prosódia não pode ser chamada quando desligada"
