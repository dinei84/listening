from processing.chunker import chunk_text
from processing.cleaner import clean_text
from processing.sanitizer import sanitize_text


def test_sanitize_removes_markdown_emphasis_markers():
    text = "O **negrito**, o *italico* e o `codigo` ficam."
    assert sanitize_text(text) == "O negrito, o italico e o codigo ficam."


def test_sanitize_removes_headings_quotes_and_list_markers():
    text = "## Titulo\n> uma citacao\n- item um\n* item dois\n1. item tres"
    result = sanitize_text(text)
    assert "##" not in result
    assert ">" not in result
    assert result.count("-") == 0
    assert "*" not in result
    assert "1." not in result
    assert "Titulo" in result
    assert "uma citacao" in result
    assert "item um" in result
    assert "item dois" in result
    assert "item tres" in result


def test_sanitize_maps_math_symbols_to_portuguese():
    text = "x ≠ 0, y ± 1, a → b, v ≈ 10."
    result = sanitize_text(text)
    assert "diferente de" in result
    assert "mais ou menos" in result
    assert "leva a" in result
    assert "aproximadamente" in result
    assert "≠" not in result
    assert "±" not in result
    assert "→" not in result
    assert "≈" not in result


def test_sanitize_drops_table_separator_rows():
    text = "| Nome | Valor |\n|---|---|---|\n| A | 1 |\n| B | 2 |"
    result = sanitize_text(text)
    assert "|---|---|---|" not in result
    assert "Nome, Valor" in result
    assert "A, 1" in result
    assert "B, 2" in result


def test_sanitize_shortens_urls_and_emails():
    text = (
        "Veja https://exemplo.com.br/docs?id=42&ref=abc ou escreva para "
        "joao@email.com."
    )
    result = sanitize_text(text)
    assert "link" in result
    assert "endereço de e-mail" in result
    assert "https://" not in result
    assert "joao@email.com" not in result


def test_sanitize_handles_code_block_without_reading_symbols():
    text = (
        "Texto antes.\n```python\ndef calcular(x):\n    return x * 2\n```\n"
        "Texto depois."
    )
    result = sanitize_text(text)
    assert "def calcular" not in result
    assert "return x * 2" not in result
    assert "trecho de código omitido" in result
    assert "Texto antes." in result
    assert "Texto depois." in result


def test_sanitize_leaves_plain_prose_untouched():
    text = (
        "A engenharia de seguranca requer metodos formais e verificacao "
        "rigorosa de protocolos. O resultado foi 5, nao 10."
    )
    assert sanitize_text(text) == text


def test_sanitize_preserves_lone_asterisk_in_prose():
    text = "Para marcar, escreva um * no fim da linha."
    assert sanitize_text(text) == text


def test_sanitize_preserves_dialogue_dash():
    text = "— Voce quer ir? — Sim, claro."
    assert sanitize_text(text) == text


def test_chunk_and_clean_contracts_unchanged():
    long_sentence = " ".join(["palavra"] * 60)
    assert chunk_text(long_sentence, max_chars=50) == [long_sentence]

    pages = ["Linha um.\nLinha dois.", "Linha um.\nOutra coisa."]
    cleaned = clean_text(pages)
    assert "Outra coisa" in cleaned


def test_pipeline_applies_sanitize_before_chunking(monkeypatch):
    from core import config as config_module
    from core import pipeline as pipeline_module
    from core.models import AudioChunk
    from plugins import registry as registry_module
    from plugins.speakers.base import Speaker

    class _Config:
        extractor = "e"
        speaker = "fake"
        queue = "sqlite"
        retry_max_attempts = 3
        retry_base_delay_seconds = 1.0
        retry_max_delay_seconds = 30.0

    class _RecordingSpeaker(Speaker):
        @property
        def cost_per_char(self):
            return 0.0

        def synthesize(self, text, voice=None, lang_code=None):
            self.texts = getattr(self, "texts", [])
            self.texts.append(text)
            return AudioChunk(
                chapter_id="",
                sequence=0,
                file_path="/tmp/fake.wav",
                duration_seconds=1.0,
                engine_used="fake",
            )

    monkeypatch.setattr(config_module, "load_config", lambda: _Config())
    speaker = _RecordingSpeaker()
    monkeypatch.setattr(registry_module, "SPEAKERS", {"fake": lambda: speaker})

    pipeline_module.synthesize_text(
        "O **negrito** e *italico*. Veja https://exemplo.com.",
        chapter_id="ch1",
    )

    assert speaker.texts == ["O negrito e italico. Veja link."]


# --- Correções de revisão (defeitos encontrados na revisão da OS-040) -----------


def test_sanitize_reads_brazilian_currency_as_reais_after_the_number():
    """R$ é real, não dólar — e em português a moeda vem DEPOIS do número."""
    assert sanitize_text("Custou R$ 50 no total.") == "Custou 50 reais no total."
    assert sanitize_text("Preco: R$ 1.200,00.") == "Preco: 1.200,00 reais."


def test_sanitize_reads_other_currencies_after_the_number():
    assert sanitize_text("Custou $ 50.") == "Custou 50 dólares."
    assert sanitize_text("Custou € 30.") == "Custou 30 euros."
    assert sanitize_text("Custou £ 20.") == "Custou 20 libras."


def test_sanitize_keeps_sentence_starting_with_a_number():
    """Número no início de frase não é item de lista — não pode ser comido."""
    assert sanitize_text("42. Esse e o numero da resposta.") == (
        "42. Esse e o numero da resposta."
    )
    assert sanitize_text("800. Carlos Magno foi coroado.") == (
        "800. Carlos Magno foi coroado."
    )


def test_sanitize_still_strips_real_numbered_list():
    """Lista numerada de verdade (itens consecutivos) continua sendo limpa."""
    texto = "1. Primeiro item\n2. Segundo item\n3. Terceiro item"
    assert sanitize_text(texto) == "Primeiro item\nSegundo item\nTerceiro item"
