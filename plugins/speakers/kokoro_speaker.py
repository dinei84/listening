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
        if effective_lang_code in "ab":
            pieces = [text]
        else:
            pieces = _split_by_phoneme_budget(text, pipeline.g2p)

        audio_parts = [
            result.output.audio
            for piece in pieces
            for result in pipeline(piece, voice=voice, speed=1.0)
            if result.output is not None
        ]

        if not audio_parts:
            raise RuntimeError("Kokoro generated no audio")

        audio_tensor = torch.cat(audio_parts, dim=-1)
        audio_array = audio_tensor.numpy().flatten()
        sample_rate = 24000

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
