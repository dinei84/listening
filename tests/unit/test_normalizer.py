import os
import tempfile

import pytest

from core import config as config_module
from core import pipeline
from core.models import AudioChunk
from plugins import registry as registry_module
from plugins.normalizers import llm_normalizer as llm_module
from plugins.normalizers.base import NoOpNormalizer, TextNormalizer
from plugins.normalizers.llm_normalizer import LLMNormalizer
from plugins.speakers.base import Speaker


class FakeConfig:
    def __init__(self, normalizer="noop", **kwargs):
        self.extractor = "fake_extractor"
        self.speaker = "fake_speaker"
        self.queue = "sqlite"
        self.max_cost_per_book = None
        self.fallback_speaker = "kokoro"
        self.retry_max_attempts = 1
        self.retry_base_delay_seconds = 0.0
        self.retry_max_delay_seconds = 0.0
        self.normalizer = normalizer
        self.normalizer_base_url = "https://exemplo.invalido/v1"
        self.normalizer_model = "modelo-teste"
        self.normalizer_api_key_env = "TEST_LLM_KEY"
        self.normalizer_cost_per_char = 0.0
        self.normalizer_divergence_ratio = None
        self.__dict__.update(kwargs)


class RecordingSpeaker(Speaker):
    """Registra o texto que efetivamente chegou ao engine."""

    def __init__(self):
        self.received = []

    @property
    def cost_per_char(self):
        return 0.0

    def synthesize(self, text, voice=None, lang_code=None):
        self.received.append(text)
        fd, path = tempfile.mkstemp(suffix=".wav")
        with os.fdopen(fd, "wb") as f:
            f.write(b"RIFF")
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=path,
            duration_seconds=1.0,
            engine_used="recording",
        )


@pytest.fixture
def speaker(monkeypatch):
    spk = RecordingSpeaker()
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": lambda: spk})
    return spk


# --- contrato -------------------------------------------------------------------


def test_normalizer_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        TextNormalizer()


def test_noop_normalizer_returns_text_unchanged():
    original = "Custou R$ 50 e a pág. 42 explica o resto."
    assert NoOpNormalizer().normalize(original) == original


def test_noop_normalizer_costs_nothing():
    assert NoOpNormalizer().cost_per_char == 0.0


# --- integração com o pipeline ---------------------------------------------------


def test_book_without_optin_never_calls_normalizer(monkeypatch, speaker):
    """Regressão: sem opt-in, nada muda e nenhuma rede é tocada."""
    chamadas = []

    class ExplodingNormalizer(TextNormalizer):
        @property
        def cost_per_char(self):
            return 0.001

        def normalize(self, text):
            chamadas.append(text)
            raise AssertionError("normalizer não deveria ser chamado sem opt-in")

    monkeypatch.setattr(config_module, "load_config", lambda: FakeConfig())
    monkeypatch.setattr(
        registry_module,
        "NORMALIZERS",
        {"noop": NoOpNormalizer, "llm": ExplodingNormalizer},
    )

    original = "Uma frase qualquer para sintetizar."
    pipeline.synthesize_text(original, chapter_id="c1")

    assert chamadas == []
    assert speaker.received == [original]


def test_optin_book_has_text_normalized_before_synthesis(monkeypatch, speaker):
    class UpperNormalizer(TextNormalizer):
        @property
        def cost_per_char(self):
            return 0.0

        def normalize(self, text):
            return text.upper()

    # O livro opta por normalizar; a config diz QUAL normalizador é usado.
    monkeypatch.setattr(
        config_module, "load_config", lambda: FakeConfig(normalizer="llm")
    )
    monkeypatch.setattr(
        registry_module,
        "NORMALIZERS",
        {"noop": NoOpNormalizer, "llm": lambda **kw: UpperNormalizer()},
    )

    pipeline.synthesize_text("frase original.", chapter_id="c1", normalize=True)

    assert speaker.received == ["FRASE ORIGINAL."]


# --- guarda-corpo ----------------------------------------------------------------


def test_llm_output_used_when_within_threshold(monkeypatch):
    normalizer = LLMNormalizer(
        base_url="https://x/v1", model="m", api_key="k", divergence_ratio=0.5
    )
    # Normalização legítima EXPANDE: "R$ 50" -> "cinquenta reais".
    monkeypatch.setattr(
        normalizer, "_call_api", lambda text: "Custou cinquenta reais no total."
    )

    resultado = normalizer.normalize("Custou R$ 50 no total.")

    assert resultado == "Custou cinquenta reais no total."


def test_llm_output_discarded_when_text_shrinks_too_much(monkeypatch, caplog):
    """O modo de falha mais grave: a LLM resume e some com conteúdo."""
    normalizer = LLMNormalizer(
        base_url="https://x/v1", model="m", api_key="k", divergence_ratio=0.5
    )
    original = "Primeira frase longa do parágrafo. " * 10
    monkeypatch.setattr(normalizer, "_call_api", lambda text: "Resumo curto.")

    resultado = normalizer.normalize(original)

    assert resultado == original, "saída divergente deveria ser descartada"


def test_llm_output_discarded_when_text_explodes(monkeypatch):
    """Modelo tagarela que inventa conteúdo também é descartado."""
    normalizer = LLMNormalizer(
        base_url="https://x/v1", model="m", api_key="k", divergence_ratio=0.5
    )
    original = "Frase curta."
    monkeypatch.setattr(normalizer, "_call_api", lambda text: "palavra " * 500)

    assert normalizer.normalize(original) == original


def test_llm_output_discarded_when_model_adds_preamble(monkeypatch):
    """Modo de falha comum: 'Aqui está o texto formatado:' passaria pelo teste de tamanho."""
    normalizer = LLMNormalizer(
        base_url="https://x/v1", model="m", api_key="k", divergence_ratio=0.5
    )
    original = "Custou R$ 50 no total."
    monkeypatch.setattr(
        normalizer,
        "_call_api",
        lambda text: "Aqui está o texto formatado:\n\nCustou cinquenta reais no total.",
    )

    resultado = normalizer.normalize(original)

    assert "Aqui está o texto formatado" not in resultado


def test_llm_network_failure_falls_back_to_original_text(monkeypatch):
    normalizer = LLMNormalizer(base_url="https://x/v1", model="m", api_key="k")

    def _boom(text):
        raise ConnectionError("rede caiu")

    monkeypatch.setattr(normalizer, "_call_api", _boom)

    original = "Texto que precisa sobreviver à queda de rede."
    assert normalizer.normalize(original) == original


def test_llm_empty_response_falls_back_to_original(monkeypatch):
    normalizer = LLMNormalizer(base_url="https://x/v1", model="m", api_key="k")
    monkeypatch.setattr(normalizer, "_call_api", lambda text: "   ")

    original = "Texto original."
    assert normalizer.normalize(original) == original


# --- cache -----------------------------------------------------------------------


def test_same_text_is_not_resent_to_the_llm(monkeypatch):
    """Retomada (OS-022) e re-priorização (OS-032) não podem multiplicar o custo."""
    normalizer = LLMNormalizer(base_url="https://x/v1", model="m", api_key="k")
    chamadas = []

    def _fake(text):
        chamadas.append(text)
        return text + " normalizado"

    monkeypatch.setattr(normalizer, "_call_api", _fake)

    normalizer.normalize("mesmo trecho")
    normalizer.normalize("mesmo trecho")
    normalizer.normalize("outro trecho")

    assert len(chamadas) == 2, f"o segundo idêntico deveria vir do cache: {chamadas}"


# --- custo -----------------------------------------------------------------------


def test_llm_normalizer_declares_cost_per_char():
    normalizer = LLMNormalizer(
        base_url="https://x/v1", model="m", api_key="k", cost_per_char=0.0000012
    )
    assert normalizer.cost_per_char == 0.0000012


def test_llm_normalizer_reads_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("MINHA_CHAVE", "segredo-123")
    normalizer = llm_module.from_config(
        base_url="https://x/v1", model="m", api_key_env="MINHA_CHAVE"
    )
    assert normalizer._api_key == "segredo-123"


def test_missing_api_key_degrades_to_noop(monkeypatch):
    """Sem chave, não pode quebrar o livro — degrada para 'sem normalização'."""
    monkeypatch.delenv("CHAVE_QUE_NAO_EXISTE", raising=False)
    normalizer = llm_module.from_config(
        base_url="https://x/v1", model="m", api_key_env="CHAVE_QUE_NAO_EXISTE"
    )

    original = "Texto que precisa passar intacto."
    assert normalizer.normalize(original) == original


# --- integração com a trava de custo (OS-042) ------------------------------------


def test_cost_estimate_includes_normalizer_when_optin(monkeypatch):
    """Sem isso o nível médio escaparia da trava de custo da OS-042."""

    class PaidSpeaker(Speaker):
        @property
        def cost_per_char(self):
            return 0.0

        def synthesize(self, text, voice=None, lang_code=None):
            raise AssertionError("não deveria sintetizar ao estimar")

    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(normalizer="llm", normalizer_cost_per_char=0.002),
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": PaidSpeaker})
    monkeypatch.setattr(
        registry_module,
        "NORMALIZERS",
        {
            "noop": NoOpNormalizer,
            "llm": lambda **kw: LLMNormalizer(
                base_url="x", model="m", api_key="k", cost_per_char=kw["cost_per_char"]
            ),
        },
    )

    texto = "abcde"
    sem_norm = pipeline.estimate_cost(texto)
    com_norm = pipeline.estimate_cost(texto, normalize=True)

    assert sem_norm == 0.0
    assert com_norm == pytest.approx(len(texto) * 0.002)


def test_cost_estimate_without_optin_ignores_normalizer_cost(monkeypatch):
    class FreeSpeaker(Speaker):
        @property
        def cost_per_char(self):
            return 0.0

        def synthesize(self, text, voice=None, lang_code=None):
            raise AssertionError("não deveria sintetizar ao estimar")

    monkeypatch.setattr(
        config_module,
        "load_config",
        lambda: FakeConfig(normalizer="llm", normalizer_cost_per_char=0.002),
    )
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake_speaker": FreeSpeaker})

    assert pipeline.estimate_cost("abcde") == 0.0
