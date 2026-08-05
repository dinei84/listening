"""Spike de performance da síntese (OS-031) — medição fora do caminho de produção.

Mede, com um texto fixo e reproduzível:
  1. Linha de base: um chunk por chamada ao pipeline, com escrita do .wav (fluxo atual).
  2. Batching: N chunks numa única chamada a KPipeline.__call__ (List[str]).
  3. Tamanho de chunk: DEFAULT_MAX_CHARS vs chunks maiores.
  4. Overhead: G2P vs inferência vs escrita do .wav.

Não altera nenhum módulo de produção. Executar: venv/bin/python scripts/spike_synthesis_performance.py
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import soundfile as sf
import torch
from kokoro import KPipeline

from processing.chunker import chunk_text

VOICE = "af_heart"
SAMPLE_RATE = 24000
REPO_ID = "hexgrad/Kokoro-82M"

# Parágrafos-base em inglês (prosa de engenharia de segurança, mesmo idioma do baseline
# real). O corpus final é montado repetindo-os com prefixo de seção, produzindo ~20
# chunks distintos com max_chars=1000 — tamanho fixo e reproduzível.
_PARAGRAPHS = [
    """Security engineering is the discipline of building systems that remain dependable
in the face of malice as well as accidents. It is an interdisciplinary field that
draws upon computer science, economics, psychology, and organizational behavior.
The fundamental problem is that human beings are not always rational, and attackers
are willing to spend enormous effort to break through the barriers we erect.""",
    """One of the core insights of the discipline is that security is not a product but
a process. A system that is secure at the moment of deployment may become vulnerable
hours later as new attack techniques emerge and as the environment changes around it.
This is why monitoring, logging, and incident response are just as important as the
initial design choices.""",
    """Threat modeling forces us to think about what could go wrong before we build
anything. We enumerate the assets that matter, the actors who might wish to harm them,
and the capabilities those actors possess. Only after that analysis can we make a
reasoned decision about where to spend our limited budget for protection.""",
    """Cryptographic protocols provide the mathematical foundation for much of modern
security. They allow two parties to communicate over an untrusted channel while
preserving confidentiality, integrity, and authenticity. However, a protocol is only
as strong as its implementation, and history is full of subtle flaws that took years
to discover.""",
    """The supply chain is another fertile ground for attacks. A single compromised
dependency can poison thousands of downstream systems without anyone noticing.
Software composition analysis has become a standard practice precisely because of this
risk, and yet the problem continues to grow as ecosystems become more interconnected.""",
    """Authentication systems must balance convenience against resistance to attack.
Passwords are easy to steal and difficult to remember, yet they remain ubiquitous.
Multi-factor authentication adds layers of defense, but each factor introduces its own
failure modes and usability costs that users must learn to tolerate.""",
    """Access control is about deciding who may do what, and under which conditions.
The principle of least privilege states that every user and every program should
operate with the minimum authority necessary to complete its assigned tasks. Following
this principle limits the damage that any single compromise can inflict.""",
    """Audit logs provide the raw material for forensic analysis after an incident.
They must be tamper-evident, complete, and retained for long enough to support
investigations that may begin months after the original event. Balancing log volume
against storage cost is a constant engineering tension.""",
    """Secure software development lifecycle practices embed security into every phase
of the process. Threat modeling happens during design, static analysis runs at every
commit, and penetration testing occurs before major releases. The goal is to catch
defects early, when they are cheapest to repair.""",
    """Defense in depth acknowledges that no single control is perfect. We layer
independent barriers so that an attacker who defeats one layer still faces the next.
This redundancy makes the whole system harder to penetrate than any of its parts.""",
    """Incident response is a discipline that cannot be improvised in the moment. Teams
rehearse their procedures, maintain runbooks, and practice tabletop exercises so that
when a real emergency arrives, the muscle memory takes over.""",
    """Finally, security culture matters more than any technology. Organizations that
reward honesty about failures, provide clear guidance, and hold everyone accountable
tend to suffer fewer serious incidents than those that rely solely on technical
controls.""",
]

# Corpus final: ~5 voltas nos parágrafos com prefixo de seção (vira cada chunk único),
# totalizando ~20k caracteres — fixo e reproduzível.
CORPUS = " ".join(
    f"Section {lap}. {paragraph}" for lap in range(1, 6) for paragraph in _PARAGRAPHS
)


def _concatenate_audio(results: list) -> torch.Tensor:
    """Concatena o áudio de uma lista de Results do Kokoro (a ordem é a ordem de geração)."""
    parts = [r.output.audio for r in results if r.output is not None]
    if not parts:
        raise RuntimeError("Kokoro generated no audio")
    return torch.cat(parts, dim=-1)


def _audio_duration_seconds(audio: torch.Tensor) -> float:
    return audio.numel() / SAMPLE_RATE


def synthesize_single(pipeline: KPipeline, text: str) -> tuple[torch.Tensor, float]:
    """Fluxo de produção: uma chamada ao pipeline com uma string, concatena os Results."""
    start = time.perf_counter()
    results = list(pipeline(text, voice=VOICE, speed=1.0))
    audio = _concatenate_audio(results)
    elapsed = time.perf_counter() - start
    return audio, elapsed


def synthesize_batch(
    pipeline: KPipeline, texts: list[str]
) -> tuple[dict[int, torch.Tensor], float]:
    """Batching: uma única chamada com List[str]; agrupa os Results por text_index e concatena."""
    start = time.perf_counter()
    results = list(pipeline(texts, voice=VOICE, speed=1.0))
    grouped: dict[int, list] = {}
    for result in results:
        idx = result.text_index
        if idx is None:
            idx = 0
        grouped.setdefault(idx, []).append(result)
    by_index: dict[int, torch.Tensor] = {
        idx: _concatenate_audio(results_for_index)
        for idx, results_for_index in grouped.items()
    }
    elapsed = time.perf_counter() - start
    return by_index, elapsed


def write_wav(audio: torch.Tensor, directory: str) -> float:
    """Escreve o .wav em disco e devolve o tempo da escrita (samefile usage of produção)."""
    fd, path = tempfile.mkstemp(suffix=".wav", dir=directory)
    os.close(fd)
    start = time.perf_counter()
    sf.write(path, audio.numpy().flatten(), SAMPLE_RATE)
    elapsed = time.perf_counter() - start
    os.remove(path)
    return elapsed


def _summarize(times: list[float], audio_seconds: float, n_chunks: int) -> dict:
    total = sum(times)
    return {
        "chunks": n_chunks,
        "total_seconds": round(total, 3),
        "seconds_per_chunk": round(total / n_chunks, 4) if n_chunks else None,
        "audio_seconds": round(audio_seconds, 1),
        "audio_ratio": round(audio_seconds / total, 2) if total else None,
    }


def measure_baseline(pipeline: KPipeline, chunks: list[str], reps: int = 3) -> dict:
    """Um chunk por chamada + escrita de .wav por chunk — espelha o KokoroSpeaker atual."""
    per_rep: list[dict] = []
    for _ in range(reps):
        times: list[float] = []
        audio_seconds = 0.0
        for piece in chunks:
            audio, elapsed = synthesize_single(pipeline, piece)
            times.append(elapsed + write_wav(audio, tempfile.gettempdir()))
            audio_seconds += _audio_duration_seconds(audio)
        per_rep.append(_summarize(times, audio_seconds, len(chunks)))

    all_chunk_times = []
    for rep in per_rep:
        all_chunk_times.append(rep["total_seconds"] / rep["chunks"])
    return {
        "per_rep": per_rep,
        "mean_seconds_per_chunk": round(statistics.mean(all_chunk_times), 4),
        "mean_audio_ratio": round(
            statistics.mean(rep["audio_ratio"] for rep in per_rep), 2
        ),
    }


def measure_batched(
    pipeline: KPipeline,
    chunks: list[str],
    batch_size: int,
    write_seconds_per_chunk: float,
    reps: int = 3,
) -> dict:
    per_rep: list[dict] = []
    for _ in range(reps):
        times: list[float] = []
        audio_seconds = 0.0
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            by_index, elapsed = synthesize_batch(pipeline, batch)
            audio_seconds += sum(_audio_duration_seconds(a) for a in by_index.values())
            times.append(elapsed + len(batch) * write_seconds_per_chunk)
        per_rep.append(_summarize(times, audio_seconds, len(chunks)))

    all_chunk_times = []
    for rep in per_rep:
        all_chunk_times.append(rep["total_seconds"] / rep["chunks"])
    return {
        "batch_size": batch_size,
        "per_rep": per_rep,
        "mean_seconds_per_chunk": round(statistics.mean(all_chunk_times), 4),
        "mean_audio_ratio": round(
            statistics.mean(rep["audio_ratio"] for rep in per_rep), 2
        ),
    }


def measure_g2p_only(corpus: str) -> tuple[float, int]:
    """Tempo de G2P puro (sem modelo): pipeline quieto (model=False) percorrendo o texto."""
    quiet = KPipeline(lang_code="a", repo_id=REPO_ID, model=False)
    start = time.perf_counter()
    results = list(quiet(corpus, voice=VOICE, speed=1.0))
    elapsed = time.perf_counter() - start
    return elapsed, len(results)


def main() -> None:
    print("torch:", torch.__version__)
    print("cuda_available:", torch.cuda.is_available())
    print(
        "gpu:",
        torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    )

    chunks_1000 = chunk_text(CORPUS, max_chars=1000)
    print("corpus_chars:", len(CORPUS))
    print("chunk_count_1000:", len(chunks_1000))

    pipeline = KPipeline(lang_code="a", repo_id=REPO_ID)
    # Aquecimento: carrega voz e pesos uma vez, fora das medições.
    synthesize_single(pipeline, chunks_1000[0])
    print("warmup: ok")

    print("\n# baseline (max_chars=1000, um chunk por chamada + .wav)")
    baseline = measure_baseline(pipeline, chunks_1000)
    print(json.dumps(baseline, indent=2, ensure_ascii=False))

    print("\n# overhead: escrita do .wav (média por chunk, fluxo de produção)")
    sample_audio, _ = synthesize_single(pipeline, chunks_1000[0])
    write_times = [write_wav(sample_audio, tempfile.gettempdir()) for _ in range(5)]
    mean_write = statistics.mean(write_times)
    print(
        json.dumps(
            {
                "mean_write_seconds_per_chunk": round(mean_write, 4),
                "per_call": [round(t, 4) for t in write_times],
            },
            indent=2,
        )
    )

    print("\n# overhead: G2P puro (sem inferência)")
    g2p_time, g2p_segments = measure_g2p_only(CORPUS)
    print(
        json.dumps(
            {"g2p_total_seconds": round(g2p_time, 3), "g2p_segments": g2p_segments},
            indent=2,
        )
    )

    print("\n# batching (List[str] numa chamada só)")
    for batch_size in (2, 4, 8, len(chunks_1000)):
        batched = measure_batched(pipeline, chunks_1000, batch_size, mean_write, reps=2)
        print(json.dumps(batched, indent=2, ensure_ascii=False))

    print("\n# tamanho de chunk (mesmo corpus, chunk_text com max_chars maior)")
    for max_chars in (1500, 2000, 3000):
        bigger_chunks = chunk_text(CORPUS, max_chars=max_chars)
        result = measure_baseline(pipeline, bigger_chunks, reps=2)
        result["max_chars"] = max_chars
        result["chunk_count"] = len(bigger_chunks)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
