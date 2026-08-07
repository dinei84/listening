import os

import pytest
import torch

from core.models import AudioChunk
from plugins.speakers import kokoro_speaker as kokoro_speaker_module
from plugins.speakers.base import Speaker
from plugins.speakers.kokoro_speaker import KokoroSpeaker

PT_TEXT = (
    "A engenharia de seguranca requer metodos formais e verificacao rigorosa "
    "de protocolos criptograficos em sistemas distribuidos modernos."
)
EN_TEXT = (
    "Security engineering requires formal methods and rigorous verification "
    "of cryptographic protocols in modern distributed systems."
)
DE_TEXT = (
    "Die Sicherheitstechnik erfordert formale Methoden und eine strenge "
    "Ueberpruefung kryptographischer Protokolle in verteilten Systemen."
)


def _fake_result(num_samples=100):
    class FakeResult:
        def __init__(self):
            self.output = type("Output", (), {"audio": torch.ones(1, num_samples)})()

    return FakeResult()


class FakeG2P:
    """Dublê do G2P do Kokoro: fonemas determinísticos na proporção do texto (densidade ~1.19, a medida de pt no OS-034)."""

    def __init__(self, density=1.19):
        self.density = density

    def __call__(self, text):
        return "x" * int(len(text) * self.density), None


class FakePipeline:
    """Dublê do KPipeline: registra cada síntese recebida."""

    def __init__(self, lang_code, num_results=1, g2p_density=1.19):
        self.lang_code = lang_code
        self.num_results = num_results
        self.g2p = FakeG2P(density=g2p_density)
        self.calls = []

    def __call__(self, text, voice, speed):
        self.calls.append((text, voice, speed))
        for _ in range(self.num_results):
            yield _fake_result()


class PipelineFactory:
    """Substitui a construção real do KPipeline, registrando cada lang_code construído."""

    def __init__(self, num_results=1, unavailable=()):
        self.num_results = num_results
        self.unavailable = set(unavailable)
        self.built = []
        self.pipelines = {}

    def __call__(self, lang_code):
        self.built.append(lang_code)
        if lang_code in self.unavailable:
            raise ImportError(f"misaki[{lang_code}] nao instalado")
        pipeline = FakePipeline(lang_code, num_results=self.num_results)
        self.pipelines[lang_code] = pipeline
        return pipeline

    def single_call(self):
        """Devolve (lang_code, (text, voice, speed)) da única síntese feita."""
        all_calls = [
            (pipeline.lang_code, call)
            for pipeline in self.pipelines.values()
            for call in pipeline.calls
        ]
        assert len(all_calls) == 1, f"esperava 1 sintese, houve {len(all_calls)}"
        return all_calls[0]


@pytest.fixture
def pipeline_factory(monkeypatch):
    factory = PipelineFactory()
    monkeypatch.setattr(KokoroSpeaker, "_build_pipeline", factory)
    return factory


def test_speaker_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Speaker()


def test_kokoro_speaker_cost_per_char_is_zero():
    speaker = KokoroSpeaker()
    assert speaker.cost_per_char == 0.0


def test_kokoro_speaker_synthesize_returns_audio_chunk_with_engine_used_kokoro(
    pipeline_factory,
):
    chunk = KokoroSpeaker().synthesize(EN_TEXT)
    assert chunk.engine_used == "kokoro"
    assert isinstance(chunk, AudioChunk)
    os.remove(chunk.file_path)


def test_kokoro_speaker_synthesize_writes_audio_file(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(EN_TEXT)
    assert os.path.exists(chunk.file_path)
    assert chunk.file_path.endswith(".wav")
    os.remove(chunk.file_path)


def test_kokoro_speaker_concatenates_multiple_results_into_single_audio_chunk(
    monkeypatch,
):
    factory = PipelineFactory(num_results=3)
    monkeypatch.setattr(KokoroSpeaker, "_build_pipeline", factory)

    chunk = KokoroSpeaker().synthesize(EN_TEXT)

    assert isinstance(chunk, AudioChunk)
    assert factory.built == ["a"]
    assert chunk.duration_seconds == pytest.approx(300 / 24000)
    os.remove(chunk.file_path)


def test_kokoro_speaker_detects_portuguese_and_uses_correct_lang_code(
    pipeline_factory,
):
    chunk = KokoroSpeaker().synthesize(PT_TEXT)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pf_dora"
    os.remove(chunk.file_path)


def test_kokoro_speaker_detects_english_and_uses_correct_lang_code(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(EN_TEXT)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_falls_back_to_english_for_unmapped_language(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(DE_TEXT)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_falls_back_to_english_when_pipeline_is_unavailable(monkeypatch):
    factory = PipelineFactory(unavailable={"p"})
    monkeypatch.setattr(KokoroSpeaker, "_build_pipeline", factory)

    chunk = KokoroSpeaker().synthesize(PT_TEXT)

    lang_code, (_, voice, _) = factory.single_call()
    assert factory.built == ["p", "a"]
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_caches_pipeline_per_language(pipeline_factory):
    speaker = KokoroSpeaker()

    for text in (PT_TEXT, PT_TEXT, EN_TEXT, PT_TEXT):
        os.remove(speaker.synthesize(text).file_path)

    assert pipeline_factory.built == ["p", "a"]


def test_kokoro_speaker_handles_short_text_without_crashing(pipeline_factory):
    chunk = KokoroSpeaker().synthesize("Ola")

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "a"
    assert voice == "af_heart"
    os.remove(chunk.file_path)


def test_kokoro_speaker_short_text_reuses_last_detected_language(pipeline_factory):
    speaker = KokoroSpeaker()

    os.remove(speaker.synthesize(PT_TEXT).file_path)
    os.remove(speaker.synthesize("Capitulo 2").file_path)

    assert pipeline_factory.built == ["p"]
    assert [call[0] for call in pipeline_factory.pipelines["p"].calls] == [
        PT_TEXT,
        "Capitulo 2",
    ]


def test_kokoro_speaker_explicit_voice_overrides_detected_default(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(PT_TEXT, voice="pm_alex")

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pm_alex"
    os.remove(chunk.file_path)


def test_kokoro_speaker_synthesize_uses_forced_lang_code_when_given(pipeline_factory):
    chunk = KokoroSpeaker().synthesize(EN_TEXT, lang_code="p")

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pf_dora"
    os.remove(chunk.file_path)


def test_kokoro_speaker_synthesize_falls_back_to_detection_when_lang_code_is_none(
    pipeline_factory,
):
    chunk = KokoroSpeaker().synthesize(PT_TEXT, lang_code=None)

    lang_code, (_, voice, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert voice == "pf_dora"
    os.remove(chunk.file_path)


# Frase longa em português SEM pontuação interna (.!?), só espaços entre palavras:
# ~660 caracteres -> ~785 fonemas no dublê (densidade 1.19), bem acima de 510.
LONG_PT_TEXT = " ".join(
    [
        "a",
        "engenharia",
        "de",
        "seguranca",
        "requer",
        "metodos",
        "formais",
        "e",
        "verificacao",
        "rigorosa",
        "de",
        "protocolos",
        "criptograficos",
        "em",
        "sistemas",
        "distribuidos",
        "modernos",
    ]
    * 6
)


def test_kokoro_speaker_splits_oversized_sentence_before_synthesis(pipeline_factory):
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize(LONG_PT_TEXT, lang_code="p")

    pipeline = pipeline_factory.pipelines["p"]
    assert len(pipeline.calls) > 1
    for piece, _, _ in pipeline.calls:
        assert len(pipeline.g2p(piece)[0]) <= 510
    os.remove(chunk.file_path)


def test_kokoro_speaker_never_splits_mid_word(pipeline_factory):
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize(LONG_PT_TEXT, lang_code="p")

    original_words = LONG_PT_TEXT.split()
    piece_words = [
        word
        for call in pipeline_factory.pipelines["p"].calls
        for word in call[0].split()
    ]
    assert piece_words == original_words
    os.remove(chunk.file_path)


LONG_PT_TEXT_WITH_PUNCT = " ".join(
    [
        (
            "a engenharia exige metodos formais e verificacao rigorosa, "
            "com protocolos criptograficos seguros, auditoria constante e "
            "testes exaustivos de sistemas criticos; tudo sob controle de versao"
        )
    ]
    * 5
)


def test_kokoro_speaker_splits_oversized_text_at_clause_boundaries(
    pipeline_factory,
):
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize(LONG_PT_TEXT_WITH_PUNCT, lang_code="p")

    pipeline = pipeline_factory.pipelines["p"]
    assert len(pipeline.calls) > 1
    original_words = LONG_PT_TEXT_WITH_PUNCT.split()
    piece_words = [word for call in pipeline.calls for word in call[0].split()]
    assert piece_words == original_words
    for piece, _, _ in pipeline.calls:
        assert len(pipeline.g2p(piece)[0]) <= 510
    os.remove(chunk.file_path)


def test_kokoro_speaker_returns_single_audio_chunk_for_oversized_text(
    pipeline_factory,
):
    chunk = KokoroSpeaker().synthesize(LONG_PT_TEXT, lang_code="p")

    assert isinstance(chunk, AudioChunk)
    assert len(pipeline_factory.pipelines["p"].calls) > 1
    os.remove(chunk.file_path)


def test_kokoro_speaker_short_text_unchanged(pipeline_factory):
    speaker = KokoroSpeaker()
    chunk = speaker.synthesize(PT_TEXT, lang_code="p")

    lang_code, (text, _, _) = pipeline_factory.single_call()
    assert lang_code == "p"
    assert text == PT_TEXT
    os.remove(chunk.file_path)


# --- OS-037: dicionário de substituição fonética --------------------------------


def test_phonetic_map_replaces_known_term_before_synthesis(
    pipeline_factory, monkeypatch
):
    monkeypatch.setattr(
        kokoro_speaker_module, "_phonetic_map", lambda: {"UML": "u ême ele"}
    )
    speaker = KokoroSpeaker()

    speaker.synthesize("O diagrama UML mostra as classes.", lang_code="p")

    _, (texto, _, _) = pipeline_factory.single_call()
    assert "u ême ele" in texto
    assert "UML" not in texto


def test_phonetic_map_respects_word_boundaries(pipeline_factory, monkeypatch):
    """Não trocar dentro de outra palavra: 'API' não pode casar em 'RAPIDEZ'."""
    monkeypatch.setattr(
        kokoro_speaker_module, "_phonetic_map", lambda: {"API": "a pê i"}
    )
    speaker = KokoroSpeaker()

    speaker.synthesize("A RAPIDEZ da API impressiona.", lang_code="p")

    _, (texto, _, _) = pipeline_factory.single_call()
    assert "RAPIDEZ" in texto, f"a palavra foi corrompida: {texto!r}"
    assert "a pê i" in texto


def test_phonetic_map_is_case_insensitive(pipeline_factory, monkeypatch):
    monkeypatch.setattr(
        kokoro_speaker_module, "_phonetic_map", lambda: {"JSON": "djêizon"}
    )
    speaker = KokoroSpeaker()

    speaker.synthesize("O arquivo json foi salvo.", lang_code="p")

    _, (texto, _, _) = pipeline_factory.single_call()
    assert "djêizon" in texto


def test_text_without_mapped_terms_is_unchanged(pipeline_factory, monkeypatch):
    monkeypatch.setattr(
        kokoro_speaker_module, "_phonetic_map", lambda: {"UML": "u ême ele"}
    )
    speaker = KokoroSpeaker()
    original = "Uma frase comum sem nenhum termo do mapa."

    speaker.synthesize(original, lang_code="p")

    _, (texto, _, _) = pipeline_factory.single_call()
    assert texto == original


def test_missing_or_empty_map_does_not_break_synthesis(pipeline_factory, monkeypatch):
    monkeypatch.setattr(kokoro_speaker_module, "_phonetic_map", dict)
    speaker = KokoroSpeaker()
    original = "Texto qualquer com UML e API."

    chunk = speaker.synthesize(original, lang_code="p")

    _, (texto, _, _) = pipeline_factory.single_call()
    assert texto == original
    assert chunk.engine_used == "kokoro"


def test_phonetic_map_does_not_change_audio_chunk_count(pipeline_factory, monkeypatch):
    """Regressão OS-021/034: a substituição continua produzindo UM AudioChunk."""
    monkeypatch.setattr(
        kokoro_speaker_module, "_phonetic_map", lambda: {"UML": "u ême ele"}
    )
    speaker = KokoroSpeaker()

    chunk = speaker.synthesize("Diagrama UML de exemplo.", lang_code="p")

    assert isinstance(chunk, AudioChunk)
    assert chunk.sequence == 0


def test_phonetic_map_file_loads_real_entries():
    """O mapa versionado carrega e tem só entradas com evidência (ver relatório)."""
    mapa = kokoro_speaker_module._phonetic_map()
    assert isinstance(mapa, dict)
    assert mapa, "o mapa inicial não pode estar vazio"
    assert "UML" in mapa


# --- OS-045: ritmo e temporização ------------------------------------------


def test_synthesize_uses_narration_speed(monkeypatch):
    """178 WPM medidos no speed 1.0 fixo; o alvo do guia para texto simples é 140-160."""
    factory = PipelineFactory()
    monkeypatch.setattr(
        KokoroSpeaker, "_build_pipeline", lambda self, lang: factory(lang)
    )
    KokoroSpeaker().synthesize(PT_TEXT, lang_code="p")
    _, (_, _, speed) = factory.single_call()
    assert speed == kokoro_speaker_module.NARRATION_SPEED
    assert speed < 1.0


def test_split_into_pause_segments_keeps_mark_with_preceding_text():
    segmentos = kokoro_speaker_module._split_into_pause_segments(
        "Primeiro item, segundo item. Terceira frase."
    )
    textos = [texto for texto, _ in segmentos]
    assert textos == ["Primeiro item,", "segundo item.", "Terceira frase."]


def test_split_into_pause_segments_uses_the_mark_to_pick_the_pause():
    segmentos = kokoro_speaker_module._split_into_pause_segments(
        "Um item, outro item; terceiro item. Fim."
    )
    pausas = [pausa for _, pausa in segmentos]
    virgula, ponto_virgula, ponto, ultimo = pausas
    assert virgula == kokoro_speaker_module.PAUSE_MS_BY_MARK[","]
    assert ponto_virgula == kokoro_speaker_module.PAUSE_MS_BY_MARK[";"]
    assert ponto == kokoro_speaker_module.PAUSE_MS_BY_MARK["."]
    assert ultimo == 0, "o último segmento não é seguido de pausa"


def test_split_into_pause_segments_detects_paragraph():
    segmentos = kokoro_speaker_module._split_into_pause_segments(
        "Fim do bloco.\n\nComeco do outro."
    )
    assert segmentos == [
        ("Fim do bloco.", kokoro_speaker_module.PARAGRAPH_PAUSE_MS),
        ("Comeco do outro.", 0),
    ]


def test_pause_hierarchy_matches_the_guide():
    """Hoje o Kokoro dá 169/195/203 ms para vírgula/ponto-e-vírgula/ponto — indistinguível."""
    marca = kokoro_speaker_module.PAUSE_MS_BY_MARK
    assert (
        marca[","] < marca[";"] < marca["."] < kokoro_speaker_module.PARAGRAPH_PAUSE_MS
    )
    assert 200 <= marca[","] <= 300
    assert 400 <= marca[";"] <= 500
    assert 500 <= marca["."] <= 800
    assert 1000 <= kokoro_speaker_module.PARAGRAPH_PAUSE_MS <= 1200


def test_pause_after_exclamation_is_longer_than_after_period():
    """Paliativo por tempo: o modelo não tem ênfase, então a exclamação se destaca pela pausa."""
    marca = kokoro_speaker_module.PAUSE_MS_BY_MARK
    assert marca["!"] > marca["."]


def test_split_into_pause_segments_does_not_split_on_abbreviation():
    """'Dr.' sobrevive à OS-044 de propósito; não pode virar pausa de fim de frase."""
    segmentos = kokoro_speaker_module._split_into_pause_segments(
        "O Dr. Silva chegou. Depois saiu."
    )
    assert [texto for texto, _ in segmentos] == ["O Dr. Silva chegou.", "Depois saiu."]


def test_silence_samples_match_configured_milliseconds():
    silencio = kokoro_speaker_module._silence(500)
    assert silencio.shape[-1] == int(0.5 * kokoro_speaker_module.SAMPLE_RATE)
    assert float(silencio.abs().max()) == 0.0


def test_trim_silence_removes_padding_but_keeps_guard_margin():
    """Cada segmento traz ~208 ms de padding do modelo; sem aparar, todo vão vira 400 ms."""
    guarda = int(
        kokoro_speaker_module.TRIM_GUARD_MS / 1000 * kokoro_speaker_module.SAMPLE_RATE
    )
    fala = torch.ones(5000)
    com_padding = torch.cat([torch.zeros(4000), fala, torch.zeros(4000)])
    aparado = kokoro_speaker_module._trim_silence(com_padding)
    assert aparado.shape[-1] == fala.shape[-1] + 2 * guarda


def test_trim_silence_keeps_all_silent_audio_untouched():
    """Segmento inteiramente silencioso não pode virar tensor vazio."""
    mudo = torch.zeros(1000)
    assert kokoro_speaker_module._trim_silence(mudo).shape[-1] == 1000
