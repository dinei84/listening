import os
import tempfile

import kokoro
import soundfile as sf
import torch
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


class KokoroSpeaker(Speaker):
    def __init__(self):
        self._pipelines: dict[str, kokoro.KPipeline | None] = {}
        self._last_lang_code = DEFAULT_LANG_CODE

    @property
    def cost_per_char(self) -> float:
        return 0.0

    def synthesize(self, text: str, voice: str | None = None) -> AudioChunk:
        pipeline, lang_code = self._get_pipeline(self._detect_lang_code(text))
        results = pipeline(
            text, voice=voice or VOICE_BY_LANG_CODE[lang_code], speed=1.0
        )
        audio_parts = [
            result.output.audio for result in results if result.output is not None
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
