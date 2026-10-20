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


def test_openai_maps_insufficient_quota_to_permanent_error(monkeypatch):
    """429 por falta de crédito NÃO é transitório: retentar nunca resolve, e tratar
    como transitório fez o livro inteiro degradar para o Kokoro em silêncio — o
    dono passou rodadas achando que a IA estava sendo usada e não estava."""
    import io
    import urllib.error

    speaker = _speaker()
    corpo = io.BytesIO(
        b'{"error":{"type":"insufficient_quota","code":"credit_balance_exhausted",'
        b'"message":"You have no credits remaining."}}'
    )

    def explode(*args, **kwargs):
        raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, corpo)

    monkeypatch.setattr(speaker, "_post", explode)
    with pytest.raises(PermanentSpeakerError, match="crédito"):
        speaker.synthesize("Uma frase qualquer.")


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


def test_openai_requires_api_key(monkeypatch):
    """Falha rápida com aviso (decisão do dono, 13/08/2026), em vez de degradar calado.

    `delenv` é obrigatório: o core.config carrega o .env na importação (OS-055), e
    sem isto o teste passa ou falha conforme a máquina tenha ou não uma chave
    configurada — foi o que aconteceu assim que o dono criou o próprio .env."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(PermanentSpeakerError, match="OPENAI_API_KEY"):
        OpenAISpeaker(api_key=None, model="gpt-4o-mini-tts", voice="nova").synthesize(
            "Uma frase."
        )


def _streaming_wav_bytes(seconds: float = 1.0, sample_rate: int = 24000) -> bytes:
    """WAV com tamanho 'desconhecido' (0xFFFFFFFF), que é o que a API realmente devolve."""
    valido = _wav_bytes(seconds, sample_rate)
    desconhecido = (0xFFFFFFFF).to_bytes(4, "little")
    # RIFF size (offset 4) e data size (offset 40) marcados como indefinidos.
    return valido[:4] + desconhecido + valido[8:40] + desconhecido + valido[44:]


def test_openai_duration_is_measured_from_real_bytes(monkeypatch, tmp_path):
    """A API devolve WAV de streaming com data size 0xFFFFFFFF; o `wave` clampa
    getnframes() em 2**31-1 e a duração saía 89.478s para 4,9s reais de áudio.
    A duração alimenta barra de progresso, retomada e navegação por trecho."""
    speaker = _speaker()
    monkeypatch.setattr(
        speaker, "_call_api", lambda text, voice: _streaming_wav_bytes(3.0)
    )
    monkeypatch.setattr(
        "plugins.speakers.openai_speaker.tempfile.gettempdir", lambda: str(tmp_path)
    )

    chunk = speaker.synthesize("Uma frase qualquer.")

    assert chunk.duration_seconds == pytest.approx(3.0, rel=1e-2)


def test_openai_rewrites_streaming_wav_with_real_sizes(monkeypatch, tmp_path):
    """O arquivo gravado precisa ser um WAV bem formado: o player e o
    _merge_wav_files do pipeline leem o cabeçalho para saber o tamanho."""
    speaker = _speaker()
    monkeypatch.setattr(
        speaker, "_call_api", lambda text, voice: _streaming_wav_bytes(2.0)
    )
    monkeypatch.setattr(
        "plugins.speakers.openai_speaker.tempfile.gettempdir", lambda: str(tmp_path)
    )

    chunk = speaker.synthesize("Uma frase qualquer.")

    with wave.open(chunk.file_path, "rb") as arquivo:
        assert arquivo.getnframes() == int(2.0 * 24000)


# --------------------------------------------------------------------------
# OS-063 — timeout de leitura escapava da classificação e matava o livro
# --------------------------------------------------------------------------


def test_openai_read_timeout_is_transient(monkeypatch):
    """Achado na primeira rodada real de um livro inteiro (20/10/2026).

    O timeout de LEITURA acontece no `response.read()`, depois de a conexão estar
    estabelecida, e o `http.client` levanta `TimeoutError` cru — que **não** é
    subclasse de `urllib.error.URLError`. Sem cair numa das duas categorias, ele
    passava pelo `_synthesize_with_retry` (que só captura `TransientSpeakerError`)
    e derrubava o livro: 10 de 641 trechos, com o primeiro chunk roteado para a
    OpenAI levando tudo junto.
    """
    speaker = _speaker()

    def estoura(*args, **kwargs):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(speaker, "_post", estoura)
    with pytest.raises(TransientSpeakerError, match="rede|retent"):
        speaker.synthesize("Uma frase qualquer.")


def test_openai_socket_timeout_is_transient(monkeypatch):
    """`socket.timeout` É `TimeoutError` desde o Python 3.10 — o teste existe para
    travar que a classificação não depende de qual dos dois nomes é usado."""
    import socket

    speaker = _speaker()

    def estoura(*args, **kwargs):
        raise socket.timeout("timed out")

    monkeypatch.setattr(speaker, "_post", estoura)
    with pytest.raises(TransientSpeakerError):
        speaker.synthesize("Uma frase qualquer.")


@pytest.mark.parametrize(
    "erro",
    [
        ConnectionResetError("conexão reiniciada pelo par"),
        ConnectionAbortedError("conexão abortada"),
        BrokenPipeError("cano quebrado"),
        OSError("falha de rede genérica"),
    ],
    ids=["reset", "aborted", "broken-pipe", "oserror"],
)
def test_openai_network_oserror_is_transient(monkeypatch, erro):
    """Toda falha de rede é `OSError`; nenhuma pode escapar sem classificação —
    foi escapar que custou o livro inteiro."""
    speaker = _speaker()

    def estoura(*args, **kwargs):
        raise erro

    monkeypatch.setattr(speaker, "_post", estoura)
    with pytest.raises(TransientSpeakerError):
        speaker.synthesize("Uma frase qualquer.")


def test_openai_http_error_is_classified_before_generic_oserror(monkeypatch):
    """`HTTPError` é subclasse de `URLError`, que é subclasse de `OSError`: se a
    captura genérica vier antes, 401 viraria transitório e o retry ficaria
    repetindo credencial inválida até o fim do backoff."""
    import urllib.error

    speaker = _speaker()

    def estoura(*args, **kwargs):
        raise urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)

    monkeypatch.setattr(speaker, "_post", estoura)
    with pytest.raises(PermanentSpeakerError):
        speaker.synthesize("Uma frase qualquer.")


def test_openai_insufficient_quota_is_still_permanent_after_the_fix(monkeypatch):
    """A classificação de saldo esgotado (429 com corpo) não pode ser engolida
    pela captura genérica nova."""
    import io
    import urllib.error

    speaker = _speaker()
    corpo = io.BytesIO(b'{"error":{"type":"insufficient_quota"}}')

    def estoura(*args, **kwargs):
        raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, corpo)

    monkeypatch.setattr(speaker, "_post", estoura)
    with pytest.raises(PermanentSpeakerError, match="crédito"):
        speaker.synthesize("Uma frase qualquer.")
