import io
import wave

import pytest

from core.models import AudioChunk
from plugins.speakers.base import (
    PermanentSpeakerError,
    Speaker,
    TransientSpeakerError,
)
from plugins.speakers.openai_speaker import OpenAISpeaker


def _wav_bytes(seconds: float = 1.0, sample_rate: int = 24000) -> bytes:
    """Devolve um WAV válido — é o que a API responde com response_format='wav'."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(sample_rate)
        arquivo.writeframes(b"\x01\x02" * int(seconds * sample_rate))
    return buffer.getvalue()


def _speaker(**kwargs) -> OpenAISpeaker:
    base = {"api_key": "chave-de-teste", "model": "gpt-4o-mini-tts", "voice": "nova"}
    return OpenAISpeaker(**{**base, **kwargs})


def test_openai_speaker_implements_contract():
    assert issubclass(OpenAISpeaker, Speaker)


def test_openai_cost_per_char_matches_measured_price():
    """US$0,015 por 933 caracteres, medido no painel da OpenAI em 11/08/2026."""
    assert _speaker().cost_per_char == pytest.approx(0.015 / 933, rel=1e-3)


def test_openai_declares_request_char_limit():
    """4.096 é o limite da API; é ele que faz o pipeline dividir antes de chamar (OS-043)."""
    assert _speaker().max_request_chars == 4096


def test_openai_synthesize_returns_audio_chunk(monkeypatch, tmp_path):
    speaker = _speaker()
    monkeypatch.setattr(speaker, "_call_api", lambda text, voice: _wav_bytes(2.0))
    monkeypatch.setattr(
        "plugins.speakers.openai_speaker.tempfile.gettempdir", lambda: str(tmp_path)
    )

    chunk = speaker.synthesize("Uma frase qualquer.")

    assert isinstance(chunk, AudioChunk)
    assert chunk.engine_used == "openai"
    assert chunk.duration_seconds == pytest.approx(2.0, rel=1e-2)


def test_openai_writes_playable_wav(monkeypatch, tmp_path):
    """O arquivo gravado precisa ser um WAV válido, sem cabeçalho aninhado."""
    speaker = _speaker()
    monkeypatch.setattr(speaker, "_call_api", lambda text, voice: _wav_bytes(1.0))
    monkeypatch.setattr(
        "plugins.speakers.openai_speaker.tempfile.gettempdir", lambda: str(tmp_path)
    )

    chunk = speaker.synthesize("Uma frase qualquer.")

    with wave.open(chunk.file_path, "rb") as arquivo:
        assert arquivo.getnchannels() == 1
        assert arquivo.getsampwidth() == 2
        assert arquivo.getframerate() == 24000


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_openai_maps_retryable_status_to_transient_error(monkeypatch, status):
    """OS-043: o retry com backoff só age em TransientSpeakerError."""
    import urllib.error

    speaker = _speaker()

    def explode(*args, **kwargs):
        raise urllib.error.HTTPError("url", status, "erro", {}, None)

    monkeypatch.setattr(speaker, "_post", explode)
    with pytest.raises(TransientSpeakerError):
        speaker.synthesize("Uma frase qualquer.")


@pytest.mark.parametrize("status", [400, 401, 403])
def test_openai_maps_client_error_to_permanent_error(monkeypatch, status):
    """Credencial inválida ou texto rejeitado: retentar só queima tempo e dinheiro."""
    import urllib.error

    speaker = _speaker()

    def explode(*args, **kwargs):
        raise urllib.error.HTTPError("url", status, "erro", {}, None)

    monkeypatch.setattr(speaker, "_post", explode)
    with pytest.raises(PermanentSpeakerError):
        speaker.synthesize("Uma frase qualquer.")


def test_openai_network_failure_is_transient(monkeypatch):
    import urllib.error

    speaker = _speaker()

    def explode(*args, **kwargs):
        raise urllib.error.URLError("conexão recusada")

    monkeypatch.setattr(speaker, "_post", explode)
    with pytest.raises(TransientSpeakerError):
        speaker.synthesize("Uma frase qualquer.")


def test_openai_sends_instructions_when_configured(monkeypatch):
    """`instructions` é o controle de estilo da gpt-4o-mini-tts, e não é faturado no input."""
    enviados = {}
    speaker = _speaker(instructions="Narre com calma.")

    def capturar(payload):
        enviados.update(payload)
        return _wav_bytes(0.5)

    monkeypatch.setattr(speaker, "_post", capturar)
    speaker.synthesize("Uma frase qualquer.")

    assert enviados["instructions"] == "Narre com calma."
    assert enviados["response_format"] == "wav"


def test_openai_omits_instructions_when_empty(monkeypatch):
    enviados = {}
    speaker = _speaker(instructions="")

    def capturar(payload):
        enviados.update(payload)
        return _wav_bytes(0.5)

    monkeypatch.setattr(speaker, "_post", capturar)
    speaker.synthesize("Uma frase qualquer.")

    assert "instructions" not in enviados


def test_openai_voice_argument_overrides_configured_voice(monkeypatch):
    enviados = {}
    speaker = _speaker(voice="nova")

    def capturar(payload):
        enviados.update(payload)
        return _wav_bytes(0.5)

    monkeypatch.setattr(speaker, "_post", capturar)
    speaker.synthesize("Uma frase qualquer.", voice="alloy")

    assert enviados["voice"] == "alloy"


def test_openai_requires_api_key():
    """Falha rápida com aviso (decisão do dono, 13/08/2026), em vez de degradar calado."""
    with pytest.raises(PermanentSpeakerError, match="OPENAI_API_KEY"):
        OpenAISpeaker(api_key=None, model="gpt-4o-mini-tts", voice="nova").synthesize(
            "Uma frase."
        )
