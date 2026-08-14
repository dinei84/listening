import io
import json
import os
import tempfile
import urllib.error
import urllib.request
import wave

from core.models import AudioChunk
from plugins.speakers.base import PermanentSpeakerError, Speaker, TransientSpeakerError

ENDPOINT = "https://api.openai.com/v1/audio/speech"

# Preço derivado de MEDIÇÃO, não de tabela: US$ 0,015 para 933 caracteres,
# lidos no painel da OpenAI em 11/08/2026. A gpt-4o-mini-tts é cobrada por token
# de áudio, não por caractere, então não há preço por caractere publicado — este
# é o custo real observado, convertido para a unidade que o contrato usa.
# Livro de 533.371 caracteres -> US$ 8,58.
COST_PER_CHAR = 0.015 / 933

# Limite documentado da API. É ele que faz o pipeline dividir o texto antes de
# chamar (OS-043), então este Speaker sempre recebe um pedaço que cabe.
MAX_REQUEST_CHARS = 4096

# Status que vale retentar com backoff (OS-043). O resto é falha permanente:
# retentar credencial inválida ou texto rejeitado só queima tempo e dinheiro.
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


def _is_quota_exhausted(exc: urllib.error.HTTPError) -> bool:
    """True quando o 429 é saldo esgotado, e não limite de taxa passageiro."""
    try:
        corpo = json.loads(exc.read().decode())
    # Captura ampla intencional: corpo ausente ou malformado não pode transformar
    # um erro de rede em outro erro; na dúvida, trata como limite de taxa.
    except Exception:  # noqa: BLE001
        return False
    erro = corpo.get("error", {})
    return (
        erro.get("type") == "insufficient_quota"
        or erro.get("code") == "credit_balance_exhausted"
    )


class OpenAISpeaker(Speaker):
    """Speaker que sintetiza via API da OpenAI (`/v1/audio/speech`), com custo por caractere derivado de medição real."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        voice: str | None = None,
        instructions: str | None = None,
        timeout_seconds: float = 120.0,
    ):
        self._api_key = (
            api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        )
        # Modelo, voz e instruções vêm do ambiente quando não informados, para
        # caberem no mesmo .env da chave. O pipeline instancia o Speaker sem
        # argumentos (`SPEAKERS[nome]()`), então não há por onde passar config.
        self._model = model or os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
        self._voice = voice or os.environ.get("OPENAI_TTS_VOICE", "nova")
        self._instructions = (
            instructions
            if instructions is not None
            else os.environ.get("OPENAI_INSTRUCTIONS", "")
        )
        self._timeout = timeout_seconds

    @property
    def cost_per_char(self) -> float:
        return COST_PER_CHAR

    @property
    def max_request_chars(self) -> int | None:
        return MAX_REQUEST_CHARS

    def synthesize(
        self, text: str, voice: str | None = None, lang_code: str | None = None
    ) -> AudioChunk:
        """Sintetiza o texto na API da OpenAI e devolve o AudioChunk; lang_code é ignorado porque o modelo detecta o idioma do próprio texto."""
        # Falha rápida com aviso, decisão do dono em 13/08/2026: sem chave o livro
        # para com mensagem clara, em vez de degradar calado para outra voz e o
        # usuário descobrir pelo ouvido.
        if not self._api_key:
            raise PermanentSpeakerError(
                "OPENAI_API_KEY não configurada — defina a chave no .env ou no "
                "ambiente para usar o Speaker da OpenAI."
            )

        audio = self._call_api(text, voice or self._voice)
        file_path = os.path.join(tempfile.gettempdir(), f"openai_{hash(text)}.wav")
        with open(file_path, "wb") as arquivo:
            arquivo.write(audio)

        # A duração vem do cabeçalho do próprio WAV devolvido pela API: é a fonte
        # confiável, e evita supor taxa de amostragem que pode mudar no futuro.
        with wave.open(io.BytesIO(audio), "rb") as lido:
            duration = lido.getnframes() / lido.getframerate()

        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=file_path,
            duration_seconds=duration,
            engine_used="openai",
        )

    def _call_api(self, text: str, voice: str) -> bytes:
        """Monta o payload e traduz erro HTTP para a classificação que o retry da OS-043 espera."""
        payload = {
            "model": self._model,
            "input": text,
            "voice": voice,
            # wav devolve RIFF com cabeçalho, que é o que o _merge_wav_files do
            # pipeline sabe concatenar. Pedir mp3 traria dado comprimido que, lido
            # como PCM, vira estática — o erro que já custou um diagnóstico errado
            # na ElevenLabs durante o spike.
            "response_format": "wav",
        }
        # `instructions` é o controle de estilo da gpt-4o-mini-tts e NÃO é faturado
        # junto com o `input`, diferente do SSML do Azure (+54% medido).
        if self._instructions.strip():
            payload["instructions"] = self._instructions

        try:
            return self._post(payload)
        except urllib.error.HTTPError as exc:
            # 429 é ambíguo: pode ser limite de taxa (passa sozinho) ou saldo
            # esgotado (nunca passa). Tratar os dois como transitório fez o livro
            # degradar calado para o motor local durante rodadas inteiras, enquanto
            # o dono achava que a IA estava sendo usada. O corpo da resposta separa
            # os dois casos, então é ele que decide.
            if exc.code == 429 and _is_quota_exhausted(exc):
                raise PermanentSpeakerError(
                    "OpenAI recusou por falta de crédito na conta — retentar não "
                    "resolve. Adicione créditos em "
                    "https://platform.openai.com/settings/organization/billing/"
                ) from exc
            if exc.code in RETRYABLE_STATUS:
                raise TransientSpeakerError(
                    f"OpenAI respondeu {exc.code}; tentativa pode ser repetida"
                ) from exc
            raise PermanentSpeakerError(
                f"OpenAI respondeu {exc.code}; a requisição não deve ser repetida"
            ) from exc
        except urllib.error.URLError as exc:
            raise TransientSpeakerError(
                f"falha de rede ao chamar a OpenAI: {exc}"
            ) from exc

    def _post(self, payload: dict) -> bytes:
        """Único ponto que toca a rede — sempre mockado nos testes, para nenhum teste fazer chamada paga."""
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            return response.read()


def from_config(
    api_key_env: str = "OPENAI_API_KEY",
    model: str = "gpt-4o-mini-tts",
    voice: str = "nova",
    instructions: str = "",
) -> OpenAISpeaker:
    """Constrói o OpenAISpeaker lendo a chave da variável de ambiente indicada."""
    return OpenAISpeaker(
        api_key=os.environ.get(api_key_env),
        model=model,
        voice=voice,
        instructions=instructions,
    )
