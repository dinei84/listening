import json
import logging
import os
import re
import urllib.error
import urllib.request

from plugins.normalizers.base import TextNormalizer

logger = logging.getLogger(__name__)

# Instrução dedicada à prosódia: o risco aqui é o modelo "ajudar demais" e mudar o
# texto do autor (seção 6 da OS-054). Diferente da OS-038 (que trata de notação),
# aqui só a pontuação pode mudar — o guarda-corpo é de identidade de palavras, não
# de tamanho.
SYSTEM_PROMPT = (
    "Você prepara a prosódia de texto em português do Brasil para narração em voz "
    "sintetizada. Ajuste APENAS a pontuação para marcar as pausas naturais de leitura:\n"
    "1. Insira vírgulas onde a respiração pede uma pausa curta.\n"
    "2. Troque vírgula por ponto para dividir uma frase longa em duas frases.\n"
    "3. Remova pontuação supérflua.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- NÃO acrescente, remova, troque nem reordene NENHUMA palavra.\n"
    "- NÃO resuma, NÃO reescreva, NÃO corrija estilo, NÃO traduza.\n"
    "- A sequência de palavras deve ser EXATAMENTE a mesma da entrada (mudanças de "
    "maiúscula em início de frase são permitidas).\n"
    "- Responda SOMENTE com o texto final. Sem comentários, sem preâmbulo, "
    "sem aspas em volta, sem markdown."
)

# Frases com que um modelo tagarela costuma prefaciar a resposta; passariam pelo
# teste de palavras, então são detectadas à parte (mesmo padrão da OS-038).
_PREAMBLE_RE = re.compile(
    r"^\s*(aqui está|aqui vai|segue|texto formatado|versão formatada|claro[,!]|"
    r"here('s| is)|sure[,!])",
    re.IGNORECASE,
)

# Guarda-corpo desta OS: a única coisa que importa é a sequência de palavras ser
# idêntica. Remove toda pontuação e diferenciação de maiúsculas, colapsando o
# texto a uma lista de palavras comparável.
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _word_tokens(text: str) -> tuple[str, ...]:
    """Devolve as palavras do texto em minúsculas, sem pontuação nem espaços."""
    return tuple(token.lower() for token in _WORD_RE.findall(text))


class ProsodyNormalizer(TextNormalizer):
    """Segundo passe de LLM que só ajusta a pontuação para respiro; qualquer falha ou saída que altere palavras devolve o texto original."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None,
        cost_per_char: float = 0.0,
        timeout_seconds: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._cost_per_char = cost_per_char
        self._timeout = timeout_seconds
        # Cache por texto: retomada (OS-022) e re-priorização (OS-032) não podem
        # multiplicar o custo reenviando o mesmo trecho.
        self._cache: dict[str, str] = {}

    @property
    def cost_per_char(self) -> float:
        return self._cost_per_char

    def normalize(self, text: str) -> str:
        """Devolve o texto com a pontuação preparada pela LLM, ou o original em qualquer falha, saída vazia ou divergência de palavras."""
        # Sem chave a prosódia fica desligada: não toca a rede e devolve o texto.
        if not text.strip() or self._api_key is None:
            return text
        if text in self._cache:
            return self._cache[text]

        try:
            saida = self._call_api(text)
        # Captura ampla intencional: preparação prosódica é melhoria opcional —
        # rede, credencial ou resposta malformada nunca podem derrubar o livro.
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Normalizador de prosódia indisponível (%s); usando texto original", exc
            )
            return text

        aceito = self._accept(text, saida)
        if aceito != text:
            logger.info(
                "Prosódia aplicada: %d -> %d caracteres", len(text), len(aceito)
            )
        else:
            logger.info("Prosódia não alterou o trecho (%d caracteres)", len(text))
        self._cache[text] = aceito
        return aceito

    def _accept(self, original: str, saida: str | None) -> str:
        """Aplica o guarda-corpo de identidade de palavras: devolve a saída só se a sequência de palavras for idêntica à original, senão o original."""
        if not saida or not saida.strip():
            logger.warning(
                "Normalizador de prosódia devolveu vazio; usando texto original"
            )
            return original

        limpo = saida.strip()
        if _PREAMBLE_RE.match(limpo):
            logger.warning(
                "Normalizador de prosódia respondeu com preâmbulo de conversa; usando texto original"
            )
            return original

        if _word_tokens(original) != _word_tokens(limpo):
            logger.warning(
                "Normalizador de prosódia alterou palavras (sequência divergente); usando texto original"
            )
            return original

        return limpo

    def _call_api(self, text: str) -> str:
        """Faz a chamada ao endpoint compatível com OpenAI e devolve o conteúdo da resposta. Único ponto que toca a rede — sempre mockado nos testes."""
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
            }
        ).encode()
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            body = json.loads(response.read())
        return body["choices"][0]["message"]["content"]


def from_config(
    base_url: str,
    model: str,
    api_key_env: str,
    cost_per_char: float = 0.0,
    divergence_ratio: float | None = None,
) -> ProsodyNormalizer:
    """Constrói o ProsodyNormalizer lendo a chave da variável de ambiente indicada; sem chave, o normalizador degrada para 'sem normalização'."""
    api_key = os.environ.get(api_key_env)
    if not api_key:
        logger.warning(
            "Variável de ambiente %s não definida; preparação prosódica desligada "
            "(o texto segue para a síntese sem ajuste de pontuação)",
            api_key_env,
        )
    return ProsodyNormalizer(
        base_url=base_url,
        model=model,
        api_key=api_key,
        cost_per_char=cost_per_char,
    )
