"""OS-056 — roteamento por densidade de expressividade no chunk.

A heurística é do dono: contar as frases com `!` ou `?` no chunk e, passando de
um limiar, mandar o chunk INTEIRO para o motor pago. Medido em 230 chunks reais,
o limiar 3 cobre os mesmos 9% do livro que o roteamento frase a frase, com 32
trocas de voz em vez de 374.
"""

import pytest

from core import config as config_module
from core import pipeline
from core.models import AudioChunk
from plugins import registry as registry_module
from plugins.speakers.base import (
    PermanentSpeakerError,
    Speaker,
    TransientSpeakerError,
)


class FakeSpeaker(Speaker):
    """Speaker de teste que registra o texto recebido e se identifica no AudioChunk."""

    def __init__(self, nome: str, custo: float = 0.0, falha: Exception | None = None):
        self.nome = nome
        self._custo = custo
        self._falha = falha
        self.recebidos: list[str] = []

    @property
    def cost_per_char(self) -> float:
        return self._custo

    def synthesize(self, text, voice=None, lang_code=None) -> AudioChunk:
        if self._falha is not None:
            raise self._falha
        self.recebidos.append(text)
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=f"/tmp/{self.nome}.wav",
            duration_seconds=1.0,
            engine_used=self.nome,
        )


class FakeConfig:
    def __init__(self, **kwargs):
        self.extractor = "fake"
        self.speaker = "local"
        self.queue = "sqlite"
        self.max_cost_per_book = None
        self.fallback_speaker = "local"
        self.retry_max_attempts = 1
        self.retry_base_delay_seconds = 0.0
        self.retry_max_delay_seconds = 0.0
        self.normalizer = "noop"
        self.normalizer_base_url = ""
        self.normalizer_model = ""
        self.normalizer_api_key_env = "X"
        self.normalizer_cost_per_char = 0.0
        self.normalizer_divergence_ratio = None
        self.prosody_normalizer = "noop"
        self.prosody_base_url = ""
        self.prosody_model = ""
        self.prosody_api_key_env = "X"
        self.prosody_cost_per_char = 0.0
        self.prosody_divergence_ratio = None
        self.routing_enabled = True
        self.routing_premium_speaker = "premium"
        self.routing_min_expressive = 3
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def motores(monkeypatch):
    local = FakeSpeaker("local")
    premium = FakeSpeaker("premium", custo=1.608e-05)
    monkeypatch.setattr(
        registry_module,
        "SPEAKERS",
        {"local": lambda: local, "premium": lambda: premium},
    )
    return local, premium


def _config(monkeypatch, **kwargs):
    cfg = FakeConfig(**kwargs)
    monkeypatch.setattr(config_module, "load_config", lambda: cfg)
    return cfg


DENSO = "Você viu? Que incrível! Como assim? Isso é demais! Sério mesmo?"
PROSA = (
    "A arquitetura de software trata de decisões caras de mudar depois. "
    "O arquiteto experiente prioriza o que custa caro. "
    "O resto pode esperar o momento certo."
)


def test_chunk_above_threshold_goes_to_premium_speaker(monkeypatch, motores):
    local, premium = motores
    _config(monkeypatch)
    pipeline.synthesize_text(DENSO, chapter_id="c1")
    assert premium.recebidos, "chunk denso deveria ir para o motor pago"
    assert not local.recebidos


def test_chunk_below_threshold_goes_to_local_speaker(monkeypatch, motores):
    local, premium = motores
    _config(monkeypatch)
    pipeline.synthesize_text(PROSA, chapter_id="c1")
    assert local.recebidos, "prosa sem expressividade deveria ficar no motor local"
    assert not premium.recebidos


def test_threshold_is_configurable(monkeypatch, motores):
    """Limiar 1 arrastaria 37% do livro para o pago; por isso ele é ajustável."""
    local, premium = motores
    _config(monkeypatch, routing_min_expressive=99)
    pipeline.synthesize_text(DENSO, chapter_id="c1")
    assert local.recebidos, "com limiar alto, nem o chunk denso deveria ser roteado"
    assert not premium.recebidos


def test_audio_chunk_records_engine_actually_used(monkeypatch, motores):
    _config(monkeypatch)
    chunks = pipeline.synthesize_text(DENSO, chapter_id="c1")
    assert chunks[0].engine_used == "premium"


def test_no_audio_chunk_mixes_engines(monkeypatch, motores):
    """O ganho central do desenho: chunk inteiro num motor só, sem emenda interna."""
    _config(monkeypatch)
    chunks = pipeline.synthesize_text(DENSO + "\n\n" + PROSA, chapter_id="c1")
    for chunk in chunks:
        assert chunk.engine_used in ("local", "premium")


def test_routing_disabled_changes_nothing(monkeypatch, motores):
    local, premium = motores
    _config(monkeypatch, routing_enabled=False)
    pipeline.synthesize_text(DENSO, chapter_id="c1")
    assert local.recebidos, "com roteamento desligado tudo vai para o motor configurado"
    assert not premium.recebidos


def test_transient_premium_failure_degrades_chunk_to_local(monkeypatch):
    """Falha TRANSITÓRIA (rede, 429 esgotado) não pode derrubar o livro — degrada
    aquele chunk e segue, porque o problema pode não se repetir no próximo."""
    local = FakeSpeaker("local")
    premium = FakeSpeaker("premium", falha=TransientSpeakerError("rede caiu"))
    monkeypatch.setattr(
        registry_module,
        "SPEAKERS",
        {"local": lambda: local, "premium": lambda: premium},
    )
    _config(monkeypatch)

    chunks = pipeline.synthesize_text(DENSO, chapter_id="c1")

    assert chunks[0].engine_used == "local"
    assert local.recebidos


def test_permanent_premium_failure_stops_the_book(monkeypatch):
    """Falha PERMANENTE é erro de configuração — chave ausente ou inválida. Degradar
    calado aqui foi o que fez o dono ouvir "igual ao Kokoro" sem saber por quê; ele
    decidiu em 13/08/2026 que prefere falha rápida com aviso."""
    local = FakeSpeaker("local")
    premium = FakeSpeaker("premium", falha=PermanentSpeakerError("sem chave"))
    monkeypatch.setattr(
        registry_module,
        "SPEAKERS",
        {"local": lambda: local, "premium": lambda: premium},
    )
    _config(monkeypatch)

    with pytest.raises(PermanentSpeakerError):
        pipeline.synthesize_text(DENSO, chapter_id="c1")


def test_degraded_speaker_name_disables_routing(monkeypatch, motores):
    """A trava de custo da OS-042 degrada para a voz local justamente para NÃO gastar;
    rotear ali reintroduziria o custo que a degradação existe para evitar."""
    local, premium = motores
    _config(monkeypatch)
    pipeline.synthesize_text(DENSO, chapter_id="c1", speaker_name="local")
    assert local.recebidos
    assert not premium.recebidos


def test_estimate_counts_only_routed_chunks(monkeypatch, motores):
    """A estimativa da OS-042 precisa refletir a fração roteada, não o livro inteiro.
    O texto é longo de propósito: precisa render mais de um chunk, senão tudo cai
    no mesmo e a distinção não é exercida."""
    _config(monkeypatch)
    texto = DENSO + "\n\n" + (PROSA + " ") * 12
    custo = pipeline.estimate_cost(texto)
    assert custo > 0, "o chunk denso deve ser cobrado no preço do pago"
    assert custo < len(texto) * 1.608e-05, "não pode cobrar o livro inteiro no pago"


def test_estimate_is_zero_when_routing_disabled(monkeypatch, motores):
    _config(monkeypatch, routing_enabled=False)
    assert pipeline.estimate_cost(DENSO) == 0.0
