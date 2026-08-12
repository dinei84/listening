import functools
import os
import re
import tempfile
from pathlib import Path

import kokoro
import soundfile as sf
import torch
import yaml
from langdetect import DetectorFactory, LangDetectException, detect

from core.models import AudioChunk
from plugins.speakers.base import Speaker
from processing.chunker import is_false_sentence_boundary

# O langdetect é não-determinístico por padrão: a mesma string pode devolver idiomas
# diferentes entre execuções. Fixar a seed torna a detecção reproduzível.
DetectorFactory.seed = 0

DEFAULT_LANG_CODE = "a"

# Idioma do langdetect -> lang_code do Kokoro (ALIASES/LANG_CODES em kokoro/pipeline.py).
# Idioma detectado fora deste mapa cai para DEFAULT_LANG_CODE.
LANG_CODE_BY_LANGUAGE = {
    "en": "a",
    "es": "e",
    "fr": "f",
    "hi": "h",
    "it": "i",
    "pt": "p",
    "ja": "j",
    "zh-cn": "z",
    "zh-tw": "z",
}

# Voz padrão por lang_code. Nomes conferidos empiricamente na listagem de
# `voices/*.pt` do repositório hexgrad/Kokoro-82M no Hugging Face (OS-020) — não há
# lista estática no pacote. Escolhida a primeira voz feminina de cada idioma, mantendo
# `af_heart` no inglês para não mudar o comportamento que já existia.
VOICE_BY_LANG_CODE = {
    "a": "af_heart",
    "b": "bf_alice",
    "e": "ef_dora",
    "f": "ff_siwis",
    "h": "hf_alpha",
    "i": "if_sara",
    "j": "jf_alpha",
    "p": "pf_dora",
    "z": "zf_xiaoxiao",
}

# Catálogo de vozes selecionáveis por idioma (OS-053), com o MESMO levantamento da
# OS-020. CONTRATO DE ORDENAÇÃO: a lista de cada idioma começa pela voz padrão atual
# (`VOICE_BY_LANG_CODE`) — ela é o padrão de quem não escolhe, e ordenar alfabeticamente
# quebraria o comportamento de todo livro já existente (em inglês, af_alloy viria antes
# de af_heart). Usado pela API para validar a voz escolhida contra o idioma do livro.
VOICES_BY_LANG_CODE = {
    "a": [
        "af_heart",
        "af_alloy",
        "af_aoede",
        "af_bella",
        "af_jessica",
        "af_kore",
        "af_nicole",
        "af_nova",
        "af_river",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_echo",
        "am_eric",
        "am_fenrir",
        "am_liam",
        "am_michael",
        "am_onyx",
        "am_puck",
        "am_santa",
    ],
    "b": [
        "bf_alice",
        "bf_emma",
        "bf_isabella",
        "bf_lily",
        "bm_daniel",
        "bm_fable",
        "bm_george",
        "bm_lewis",
    ],
    "e": ["ef_dora", "em_alex", "em_santa"],
    "f": ["ff_siwis"],
    "h": ["hf_alpha", "hf_beta", "hm_omega", "hm_psi"],
    "i": ["if_sara", "im_nicola"],
    "j": [
        "jf_alpha",
        "jf_gongitsune",
        "jf_nezumi",
        "jf_tebukuro",
        "jm_kumo",
    ],
    "p": ["pf_dora", "pm_alex", "pm_santa"],
    "z": [
        "zf_xiaoxiao",
        "zf_xiaobei",
        "zf_xiaoni",
        "zf_xiaoyi",
        "zm_yunjian",
        "zm_yunxi",
        "zm_yunxia",
        "zm_yunyang",
    ],
}

# Abaixo deste tamanho o langdetect erra muito ("Hello" vira finlandês, "Capitulo 1"
# vira romeno — medido na OS-020). A detecção estabilizou a partir de ~20 caracteres
# nas amostras testadas; 40 dá o dobro de margem. Textos menores que isso reaproveitam
# o último idioma detectado com sucesso na mesma instância.
MIN_DETECTION_CHARS = 40

# Orçamento de fonemas do modelo Kokoro: acima disso o pipeline faz ps[:510] e segue
# (truncamento silencioso) nos idiomas via espeak (kokoro/pipeline.py, linha 428). O
# inglês é imune — o en_tokenize divide respeitando o limite (OS-034).
MAX_PHONEMES = 510

# Mapa de substituição fonética (OS-037): termos que o G2P do espeak erra sempre.
# Fica em arquivo versionado ao lado deste módulo para que adicionar uma entrada
# não exija mexer em código — ver RUNBOOK.md.
PHONETIC_MAP_PATH = Path(__file__).with_name("phonetic_map.yaml")

SAMPLE_RATE = 24000

# Velocidade da narração. Mantida em 1.0 (articulação natural do modelo) por
# avaliação de escuta: a 0.90 a voz perde tessitura e soa mecânica, e o ganho de
# conforto vem da pausa entre frases, não de arrastar a articulação. O ritmo fino
# fica com o controle de velocidade do player, que escala fala e pausa juntas.
NARRATION_SPEED = 1.0

# Pausa alvo por sinal, em ms. Só sinais de FIM DE FRASE entram aqui — ver
# SENTENCE_END_MARKS para a razão. Os valores ficam abaixo dos 500-800 ms do guia
# de ritmo de propósito: combinados com a pausa que o próprio modelo já produz
# dentro da frase, os números do guia soaram arrastados na escuta real.
PAUSE_MS_BY_MARK = {
    ".": 420,
    # Acima do ponto final de propósito: o Kokoro-82M não tem controle de ênfase
    # (ressalva da decisão #23), então a exclamação só consegue se destacar pelo
    # tempo. É paliativo — dá relevo à frase, não emoção.
    "!": 520,
    "?": 470,
}

# Só se divide o texto em fim de frase. Vírgula, ponto e vírgula e dois pontos
# ficam DE FORA por medida de qualidade: cada segmento é sintetizado como um
# enunciado independente, sem contexto do que vem antes ou depois, então dividir
# dentro da frase faz o modelo aplicar contorno de frase completa (com queda
# final) em cada fragmento. O resultado é entonação achatada e emenda audível —
# regressão medida na escuta da primeira versão desta OS. A pausa interna de
# vírgula que o modelo já produz sozinho (~169 ms) fica como está.
SENTENCE_END_MARKS = ".!?"

DEFAULT_PAUSE_MS = 420
PARAGRAPH_PAUSE_MS = 800

# Margem de segurança do aparo: o corte para no primeiro ponto acima do limiar,
# e consoantes surdas (/s/, /f/, /p/) começam muito baixo — sem esta folga o
# ataque da palavra seria comido.
TRIM_GUARD_MS = 15
TRIM_THRESHOLD = 0.02

_PARAGRAPH_BREAK_RE = re.compile(r"\n\s*\n")
# Divide DEPOIS do sinal, mantendo-o no segmento que ele encerra — a entonação de
# fechamento pertence à frase que termina nele, não à seguinte.
_PAUSE_MARK_RE = re.compile(rf"(?<=[{re.escape(SENTENCE_END_MARKS)}])\s+")


@functools.lru_cache(maxsize=1)
def _phonetic_map() -> dict[str, str]:
    """Carrega o mapa de substituição fonética do YAML versionado; mapa ausente ou ilegível vira mapa vazio (nunca derruba a síntese)."""
    try:
        with PHONETIC_MAP_PATH.open(encoding="utf-8") as arquivo:
            dados = yaml.safe_load(arquivo)
    # Captura ampla intencional: um mapa quebrado não pode impedir o livro de ser
    # sintetizado — degrada para "sem substituição", como o fallback de idioma.
    except Exception:  # noqa: BLE001
        return {}
    return {str(k): str(v) for k, v in (dados or {}).items()}


def _apply_phonetic_map(text: str) -> str:
    """Troca os termos do mapa fonético pela grafia que o G2P pronuncia certo, preservando o resto do texto."""
    # O padrão é derivado do mapa a cada chamada de propósito: cachear os dois
    # separadamente os deixaria fora de sincronia se o mapa mudasse. O `re` já
    # mantém cache interno de padrões compilados, então o custo é desprezível.
    mapa = _phonetic_map()
    if not mapa:
        return text

    # Termos mais longos primeiro: evita que um termo curto case antes de um
    # mais específico que o contenha.
    alternativas = "|".join(re.escape(t) for t in sorted(mapa, key=len, reverse=True))
    # (?<!\w) / (?!\w) em vez de \b: também funciona para termos que começam ou
    # terminam em caractere não-alfanumérico, e nunca casa dentro de outra palavra.
    padrao = re.compile(rf"(?<!\w)({alternativas})(?!\w)", re.IGNORECASE)

    por_minuscula = {k.lower(): v for k, v in mapa.items()}
    return padrao.sub(lambda m: por_minuscula[m.group(1).lower()], text)


def _split_into_pause_segments(text: str) -> list[tuple[str, int]]:
    """Divide o texto em segmentos de fala, cada um com a pausa em ms que deve segui-lo; o último segmento recebe pausa zero."""
    segmentos: list[tuple[str, int]] = []
    paragrafos = [p for p in _PARAGRAPH_BREAK_RE.split(text) if p.strip()]

    for indice, paragrafo in enumerate(paragrafos):
        partes = _juntar_falsas_fronteiras(_PAUSE_MARK_RE.split(paragrafo.strip()))
        for parte in partes:
            parte = parte.strip()
            if parte:
                segmentos.append(
                    (parte, PAUSE_MS_BY_MARK.get(parte[-1], DEFAULT_PAUSE_MS))
                )
        if segmentos and indice < len(paragrafos) - 1:
            texto_final, _ = segmentos[-1]
            segmentos[-1] = (texto_final, PARAGRAPH_PAUSE_MS)

    if segmentos:
        texto_final, _ = segmentos[-1]
        segmentos[-1] = (texto_final, 0)
    return segmentos


def _juntar_falsas_fronteiras(partes: list[str]) -> list[str]:
    """Recola os pedaços separados por um ponto de abreviação ('Dr. Silva'), que não é fim de oração."""
    resultado: list[str] = []
    for parte in partes:
        if resultado and is_false_sentence_boundary(resultado[-1]):
            resultado[-1] = f"{resultado[-1]} {parte}"
        else:
            resultado.append(parte)
    return resultado


def _silence(milliseconds: int) -> torch.Tensor:
    """Devolve um tensor de silêncio com a duração pedida, na taxa de amostragem do Kokoro."""
    return torch.zeros(int(milliseconds / 1000 * SAMPLE_RATE))


def _trim_silence(audio: torch.Tensor) -> torch.Tensor:
    """Apara o silêncio das bordas do segmento, preservando uma margem de guarda; áudio inteiramente silencioso volta intacto."""
    flat = audio.flatten()
    amplitude = flat.abs()
    pico = float(amplitude.max())
    if pico == 0.0:
        return flat

    acima = (amplitude > pico * TRIM_THRESHOLD).nonzero()
    if acima.numel() == 0:
        return flat

    guarda = int(TRIM_GUARD_MS / 1000 * SAMPLE_RATE)
    inicio = max(0, int(acima[0]) - guarda)
    fim = min(flat.shape[-1], int(acima[-1]) + 1 + guarda)
    return flat[inicio:fim]


def _phoneme_count(text: str, g2p) -> int:
    """Conta os fonemas que o G2P do Kokoro geraria para o texto (medição real, não estimativa por caracteres)."""
    return len(g2p(text)[0])


def _find_natural_boundary(text: str, center: int) -> int | None:
    """Devolve o índice para partir text — depois da pontuação (; : ,) ou no espaço — mais próximo de center, preferindo pontuação a espaço; None se não houver."""
    for target in (",;:", " \t"):
        best = None
        for radius in range(len(text)):
            for pos in (center - radius, center + radius):
                if 0 < pos < len(text) and text[pos] in target:
                    best = pos
                    break
            if best is not None:
                break
        if best is not None:
            split = best + 1 if text[best] in ",;:" else best
            if 0 < split < len(text):
                return split
    return None


def _split_by_phoneme_budget(
    text: str, g2p, max_phonemes: int = MAX_PHONEMES
) -> list[str]:
    """Divide texto cuja fonemização excede max_phonemes em pedaços que não excedam, preferindo fronteiras de ; : , e depois espaço entre palavras; nunca corta no meio de palavra."""
    text = text.strip()
    if _phoneme_count(text, g2p) <= max_phonemes:
        return [text]
    if not re.search(r"\s", text):
        # Palavra única acima do orçamento: impossível dividir sem cortar no meio
        # (~430+ caracteres numa palavra, caso de borda) — emite inteira.
        return [text]

    # Prefere partir em cláusulas (; : ,), acumulando até o orçamento — medição
    # real de cada candidato, sem estimativa por caracteres.
    clauses = [c for c in re.split(r"(?<=[,;:])\s+", text) if c.strip()]
    if len(clauses) > 1:
        pieces: list[str] = []
        current = ""
        for clause in clauses:
            clause = clause.strip()
            if not current:
                current = clause
            elif _phoneme_count(f"{current} {clause}", g2p) <= max_phonemes:
                current = f"{current} {clause}"
            else:
                pieces.append(current)
                current = clause
        if current:
            pieces.append(current)

        result: list[str] = []
        for piece in pieces:
            if _phoneme_count(piece, g2p) <= max_phonemes:
                result.append(piece)
            else:
                result.extend(_split_by_phoneme_budget(piece, g2p, max_phonemes))
        return result

    # Sem cláusulas: divide-e-conquista no meio na fronteira (espaço) mais próxima
    # e recursa em cada metade — sempre reduz o texto, então termina.
    boundary = _find_natural_boundary(text, len(text) // 2)
    if boundary is None:
        return [text]
    return _split_by_phoneme_budget(
        text[:boundary], g2p, max_phonemes
    ) + _split_by_phoneme_budget(text[boundary:], g2p, max_phonemes)


class KokoroSpeaker(Speaker):
    def __init__(self):
        self._pipelines: dict[str, kokoro.KPipeline | None] = {}
        self._last_lang_code = DEFAULT_LANG_CODE

    @property
    def cost_per_char(self) -> float:
        return 0.0

    def synthesize(
        self, text: str, voice: str | None = None, lang_code: str | None = None
    ) -> AudioChunk:
        pipeline, effective_lang_code = self._get_pipeline(
            lang_code if lang_code is not None else self._detect_lang_code(text)
        )
        voice = voice or VOICE_BY_LANG_CODE[effective_lang_code]

        # OS-037: corrige termos que o G2P erra sempre, ANTES de medir/dividir por
        # orçamento de fonemas — a substituição muda o tamanho fonêmico do texto.
        text = _apply_phonetic_map(text)

        # OS-034: idiomas via espeak (todos exceto en-us/en-gb) são truncados
        # silenciosamente em 510 fonemas dentro do Kokoro; inglês é dividido pelo
        # en_tokenize do próprio engine. Para os demais, divide o texto por orçamento
        # de fonemas (medido com g2p) antes de sintetizar — cada pedaço gera áudio que
        # é concatenado num único AudioChunk (mesma granularidade de sempre).
        # OS-045: o texto é dividido nos sinais de pontuação e cada segmento é
        # sintetizado à parte, para que a pausa entre eles seja controlada aqui em vez
        # de herdada do modelo — que colapsa vírgula, ponto e parágrafo em ~200 ms.
        audio_parts: list[torch.Tensor] = []
        for segmento, pausa_ms in _split_into_pause_segments(text):
            # OS-034: idiomas via espeak (todos exceto en-us/en-gb) são truncados
            # silenciosamente em 510 fonemas dentro do Kokoro; inglês é dividido pelo
            # en_tokenize do próprio engine. Para os demais, divide o segmento por
            # orçamento de fonemas (medido com g2p) antes de sintetizar.
            if effective_lang_code in "ab":
                pieces = [segmento]
            else:
                pieces = _split_by_phoneme_budget(segmento, pipeline.g2p)

            falado = [
                result.output.audio
                for piece in pieces
                for result in pipeline(piece, voice=voice, speed=NARRATION_SPEED)
                if result.output is not None
            ]
            if not falado:
                continue

            # Aparar antes de inserir é o que dá controle exato: cada segmento vem com
            # ~208 ms de padding do modelo em cada borda, então concatenar sem aparar
            # produziria um vão fixo de ~400 ms em toda pontuação — longo demais para
            # vírgula e curto demais para ponto, exatamente o que se quer corrigir.
            audio_parts.append(_trim_silence(torch.cat(falado, dim=-1)))
            if pausa_ms:
                audio_parts.append(_silence(pausa_ms))

        if not audio_parts:
            raise RuntimeError("Kokoro generated no audio")

        audio_tensor = torch.cat(audio_parts, dim=-1)
        audio_array = audio_tensor.numpy().flatten()
        sample_rate = SAMPLE_RATE

        tmp_dir = tempfile.gettempdir()
        file_path = os.path.join(tmp_dir, f"kokoro_{hash(text)}.wav")
        sf.write(file_path, audio_array, sample_rate)

        duration = len(audio_array) / sample_rate
        return AudioChunk(
            chapter_id="",
            sequence=0,
            file_path=file_path,
            duration_seconds=duration,
            engine_used="kokoro",
        )

    def _detect_lang_code(self, text: str) -> str:
        """Detecta o idioma do texto e devolve o lang_code do Kokoro; texto curto demais reaproveita o último idioma detectado."""
        if len(text.strip()) < MIN_DETECTION_CHARS:
            return self._last_lang_code

        try:
            language = detect(text)
        except LangDetectException:
            return self._last_lang_code

        self._last_lang_code = LANG_CODE_BY_LANGUAGE.get(language, DEFAULT_LANG_CODE)
        return self._last_lang_code

    def _get_pipeline(self, lang_code: str) -> tuple[kokoro.KPipeline, str]:
        """Devolve o pipeline do idioma (cache lazy, um por lang_code) e o lang_code efetivamente usado."""
        if lang_code != DEFAULT_LANG_CODE:
            if lang_code not in self._pipelines:
                try:
                    self._pipelines[lang_code] = self._build_pipeline(lang_code)
                # Captura ampla intencional: um idioma indisponível neste ambiente
                # (ex: falta misaki[ja]/misaki[zh]) não pode derrubar o livro inteiro.
                # Guarda None pra não tentar reconstruir a cada chunk.
                except Exception:  # noqa: BLE001
                    self._pipelines[lang_code] = None
            pipeline = self._pipelines[lang_code]
            if pipeline is not None:
                return pipeline, lang_code

        # Sem fallback possível se o próprio idioma padrão falhar: deixa o erro subir.
        if DEFAULT_LANG_CODE not in self._pipelines:
            self._pipelines[DEFAULT_LANG_CODE] = self._build_pipeline(DEFAULT_LANG_CODE)
        return self._pipelines[DEFAULT_LANG_CODE], DEFAULT_LANG_CODE

    def _build_pipeline(self, lang_code: str) -> kokoro.KPipeline:
        """Constrói um KPipeline real do Kokoro para o idioma. Único ponto que toca o engine — sempre mockado nos testes."""
        return kokoro.KPipeline(lang_code=lang_code)
