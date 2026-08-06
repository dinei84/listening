import json
import logging
import os
import re
import urllib.error
import urllib.request

from plugins.normalizers.base import TextNormalizer

logger = logging.getLogger(__name__)

# Instrução deliberadamente restritiva: o risco desta OS não é o modelo ser fraco,
# é ele "ajudar demais" e alterar o texto do autor (seção 2 da OS-038).
SYSTEM_PROMPT = (
    "Você prepara texto em português do Brasil para narração em voz sintetizada.\n"
    "Aplique APENAS estas transformações:\n"
    "1. Escreva números, valores e datas por extenso (R$ 50 -> cinquenta reais; "
    "1984 -> mil novecentos e oitenta e quatro).\n"
    "2. Expanda abreviações (pág. -> página; séc. XIX -> século dezenove; "
    "Dr. -> doutor).\n"
    "3. Ajuste apenas a pontuação necessária para pausas naturais de leitura.\n\n"
    "REGRAS ABSOLUTAS:\n"
    "- NÃO resuma, NÃO reescreva, NÃO corrija estilo, NÃO traduza.\n"
    "- NÃO acrescente nem remova informação.\n"
    "- Responda SOMENTE com o texto final. Sem comentários, sem preâmbulo, "
    "sem aspas em volta, sem markdown."
)

# Quanto o texto pode encolher/crescer antes de ser considerado suspeito. A
# normalização legítima EXPANDE (números por extenso), então o limite é assimétrico:
# crescer bastante é esperado, encolher é sinal de resumo — o modo de falha grave.
DEFAULT_MAX_GROWTH = 2.0
DEFAULT_MAX_SHRINK = 0.85

# Frases com que um modelo tagarela costuma prefaciar a resposta. Elas passariam
# pelo teste de tamanho, então são detectadas à parte.
_PREAMBLE_RE = re.compile(
    r"^\s*(aqui está|aqui vai|segue|texto formatado|versão formatada|claro[,!]|"
    r"here('s| is)|sure[,!])",
    re.IGNORECASE,
)


class LLMNormalizer(TextNormalizer):
    """Normaliza o texto via LLM num endpoint compatível com OpenAI; qualquer falha ou saída suspeita devolve o texto original."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None,
        cost_per_char: float = 0.0,
        divergence_ratio: float | None = None,
        timeout_seconds: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._cost_per_char = cost_per_char
        self._timeout = timeout_seconds
        # divergence_ratio simplifica a configuração: um único número define os dois
        # lados da janela aceitável.
        if divergence_ratio is None:
            self._max_growth = DEFAULT_MAX_GROWTH
            self._max_shrink = DEFAULT_MAX_SHRINK
        else:
            self._max_growth = 1.0 + divergence_ratio
            self._max_shrink = 1.0 - divergence_ratio
        # Cache por texto: retomada (OS-022) e re-priorização (OS-032) não podem
        # multiplicar o custo reenviando o mesmo trecho.
        self._cache: dict[str, str] = {}

    @property
    def cost_per_char(self) -> float:
        return self._cost_per_char

    def normalize(self, text: str) -> str:
        """Devolve o texto normalizado pela LLM, ou o original em qualquer falha, saída vazia ou divergência suspeita."""
        if not text.strip() or self._api_key is None:
            return text
        if text in self._cache:
            return self._cache[text]

        try:
            saida = self._call_api(text)
        # Captura ampla intencional: normalização é melhoria opcional — rede,
        # credencial ou resposta malformada nunca podem derrubar o livro.
        except Exception as exc:  # noqa: BLE001
            logger.warning("Normalizador indisponível (%s); usando texto original", exc)
            return text

        aceito = self._accept(text, saida)
        # Toda rejeição do guarda-corpo loga WARNING, mas a aceitação era silenciosa:
        # sem esta linha, "normalizou e nada mudou" e "nunca foi chamado" produzem
        # exatamente o mesmo log, e não há como saber qual dos dois aconteceu.
        if aceito != text:
            logger.info(
                "Normalizador aplicado: %d -> %d caracteres", len(text), len(aceito)
            )
        else:
            logger.info("Normalizador não alterou o trecho (%d caracteres)", len(text))
        self._cache[text] = aceito
        return aceito

    def _accept(self, original: str, saida: str | None) -> str:
        """Aplica o guarda-corpo: devolve a saída da LLM só se ela for plausível, senão o original."""
        if not saida or not saida.strip():
            logger.warning("Normalizador devolveu vazio; usando texto original")
            return original

        limpo = saida.strip()
        if _PREAMBLE_RE.match(limpo):
            logger.warning(
                "Normalizador respondeu com preâmbulo de conversa; usando texto original"
            )
            return original

        razao = len(limpo) / len(original)
        if razao < self._max_shrink or razao > self._max_growth:
            logger.warning(
                "Normalizador divergiu demais (razão %.2f, aceitável entre %.2f e %.2f); "
                "usando texto original",
                razao,
                self._max_shrink,
                self._max_growth,
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
) -> LLMNormalizer:
    """Constrói o LLMNormalizer lendo a chave da variável de ambiente indicada; sem chave, o normalizador degrada para 'sem normalização'."""
    api_key = os.environ.get(api_key_env)
    if not api_key:
        logger.warning(
            "Variável de ambiente %s não definida; normalização desligada "
            "(o texto segue para a síntese sem alteração)",
            api_key_env,
        )
    return LLMNormalizer(
        base_url=base_url,
        model=model,
        api_key=api_key,
        cost_per_char=cost_per_char,
        divergence_ratio=divergence_ratio,
    )
