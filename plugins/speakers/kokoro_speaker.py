import os
import tempfile

import kokoro
import soundfile as sf
import torch

from core.models import AudioChunk
from plugins.speakers.base import Speaker

PHONEME_LIMIT_ERROR = "Phoneme string too long"
MAX_SPLIT_DEPTH = 10


class KokoroSpeaker(Speaker):
    def __init__(self):
        self._pipeline = None

    @property
    def cost_per_char(self) -> float:
        return 0.0

    def synthesize(self, text: str, voice: str | None = None) -> AudioChunk:
        audio_parts = self._generate_audio(text, voice or "af_heart", depth=0)
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

    def _generate_audio(self, text: str, voice: str, depth: int) -> list[torch.Tensor]:
        """Gera o áudio bruto pro texto; se o Kokoro rejeitar por limite de fonemas, divide por palavra e tenta de novo."""
        pipeline = self._get_pipeline()
        try:
            results = list(pipeline.generate_from_tokens(text, voice=voice, speed=1.0))
        except ValueError as exc:
            if PHONEME_LIMIT_ERROR not in str(exc):
                raise

            first_half, second_half = self._split_in_half_by_word(text)
            if not first_half or not second_half:
                raise RuntimeError(
                    "Kokoro rejeitou o texto por limite de fonemas e ele não pode "
                    f"ser dividido em palavras menores: {exc}"
                ) from exc
            if depth >= MAX_SPLIT_DEPTH:
                raise RuntimeError(
                    "Kokoro rejeitou o texto por limite de fonemas mesmo após "
                    f"{MAX_SPLIT_DEPTH} tentativas de divisão: {exc}"
                ) from exc

            return self._generate_audio(
                first_half, voice, depth + 1
            ) + self._generate_audio(second_half, voice, depth + 1)

        return [result.output.audio for result in results if result.output is not None]

    @staticmethod
    def _split_in_half_by_word(text: str) -> tuple[str, str]:
        """Divide o texto ao meio por palavra. Devolve ("", "") se não houver como dividir (uma única palavra)."""
        words = text.split(" ")
        if len(words) < 2:
            return "", ""
        mid = len(words) // 2
        return " ".join(words[:mid]), " ".join(words[mid:])

    def _get_pipeline(self) -> kokoro.KPipeline:
        if self._pipeline is None:
            self._pipeline = kokoro.KPipeline(lang_code="a")
        return self._pipeline
