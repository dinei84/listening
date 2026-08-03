import os
import tempfile

import kokoro
import soundfile as sf

from core.models import AudioChunk
from plugins.speakers.base import Speaker


class KokoroSpeaker(Speaker):
    def __init__(self):
        self._pipeline = None

    @property
    def cost_per_char(self) -> float:
        return 0.0

    def synthesize(self, text: str, voice: str | None = None) -> AudioChunk:
        pipeline = self._get_pipeline()
        results = pipeline.generate_from_tokens(
            text, voice=voice or "af_heart", speed=1.0
        )
        audio_parts = []
        for result in results:
            if result.output is not None:
                audio_parts.append(result.output.audio)

        if not audio_parts:
            raise RuntimeError("Kokoro generated no audio")

        import torch

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

    def _get_pipeline(self) -> kokoro.KPipeline:
        if self._pipeline is None:
            self._pipeline = kokoro.KPipeline(lang_code="a")
        return self._pipeline
