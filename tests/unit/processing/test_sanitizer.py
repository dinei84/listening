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


# --- OS-044: notação que o espeak lê errado -------------------------------


def test_sanitize_expands_reference_abbreviations():
    """'séc.'/'cap.'/'pág.' viram sílaba quebrada no G2P ('sék', 'káp', 'pág')."""
    assert sanitize_text("Ver séc. XIX e cap. IV.") == "Ver século XIX e capítulo IV."
    assert sanitize_text("Na pág. 42 e nas págs. 10.") == (
        "Na página 42 e nas páginas 10."
    )
    assert sanitize_text("Ver pp. 33 e fig. 3.") == "Ver páginas 33 e figura 3."
    assert sanitize_text("No vol. 2, ed. 5, art. 12.") == (
        "No volume 2, edição 5, artigo 12."
    )


def test_sanitize_expands_title_abbreviations():
    """'Sr.' sai como 'ésse-érre' e 'cf.' como 'cê-éfe' — letras soletradas."""
    assert sanitize_text("O Sr. Souza e a Sra. Lima.") == (
        "O senhor Souza e a senhora Lima."
    )
    assert sanitize_text("O Prof. Melo, cf. adiante.") == (
        "O professor Melo, conforme adiante."
    )


def test_sanitize_keeps_abbreviations_espeak_already_says_right():
    """Dr./Dra./etc. já são pronunciados certo pelo espeak — não mexer."""
    assert sanitize_text("O Dr. Silva e a Dra. Ana.") == "O Dr. Silva e a Dra. Ana."
    assert sanitize_text("Livros, filmes, etc. sao caros.") == (
        "Livros, filmes, etc. sao caros."
    )


def test_sanitize_does_not_expand_abbreviation_inside_word():
    """'cap' dentro de 'capa'/'recap.' não pode virar 'capítulo'."""
    assert sanitize_text("A capa do livro.") == "A capa do livro."
    assert sanitize_text("Uma recap. do caso.") == "Uma recap. do caso."
    assert sanitize_text("O sred. nao existe.") == "O sred. nao existe."


def test_sanitize_reads_hour_marker_as_pause():
    """'15h30' sai como 'quinze agá trinta' — o h é soletrado."""
    assert sanitize_text("A reuniao e as 15h30.") == "A reuniao e as 15 e 30."
    assert sanitize_text("Entre 9h05 e 18h45.") == "Entre 9 e 05 e 18 e 45."


def test_sanitize_reads_bare_hour_as_horas():
    assert sanitize_text("Comeca as 15h.") == "Comeca as 15 horas."
    assert sanitize_text("Das 8h ate tarde.") == "Das 8 horas ate tarde."


def test_sanitize_expands_numeric_date_to_month_name():
    """'12/03/2019' sai como 'doze zero três dois mil e dezenove'."""
    assert sanitize_text("Publicado em 12/03/2019.") == (
        "Publicado em 12 de março de 2019."
    )
    assert (
        sanitize_text("Em 01/12/99 aconteceu.") == "Em 01 de dezembro de 99 aconteceu."
    )


def test_sanitize_keeps_non_date_slash_untouched():
    """Mês inválido não é data — custo/benefício e 20/25 seguem intactos."""
    assert sanitize_text("A relacao custo/beneficio.") == "A relacao custo/beneficio."
    assert sanitize_text("O placar 20/25/2019 nao e data.") == (
        "O placar 20/25/2019 nao e data."
    )


def test_sanitize_reads_page_range_as_a():
    """'10-15' sai como 'dez menos quinze' — o hífen vira subtração."""
    assert sanitize_text("Veja as paginas 10-15.") == "Veja as paginas 10 a 15."
    assert sanitize_text("Nos capitulos 3-7 do livro.") == (
        "Nos capitulos 3 a 7 do livro."
    )


def test_sanitize_expands_range_after_abbreviation_expansion():
    """Ordem importa: 'págs. 10-15' só é intervalo depois de virar 'páginas'."""
    assert sanitize_text("Ver págs. 10-15.") == "Ver páginas 10 a 15."


def test_sanitize_reads_en_dash_between_numbers_as_a():
    """O travessão curto entre números nunca é subtração."""
    assert sanitize_text("O periodo 1914–1918 foi longo.") == (
        "O periodo 1914 a 1918 foi longo."
    )


def test_sanitize_keeps_subtraction_hyphen_untouched():
    """Sem substantivo de intervalo antes, o hífen pode ser subtração legítima."""
    assert sanitize_text("O saldo caiu 10-15 reais.") == "O saldo caiu 10-15 reais."
    assert sanitize_text("O resultado de 20-8 e doze.") == (
        "O resultado de 20-8 e doze."
    )


def test_sanitize_keeps_hyphenated_word_untouched():
    assert sanitize_text("Um sistema custo-beneficio.") == (
        "Um sistema custo-beneficio."
    )


def test_chunker_still_splits_sentences_after_abbreviation_expansion():
    """A expansão remove o ponto da abreviação; o chunker não pode ganhar fronteira falsa."""
    texto = sanitize_text("Ver o cap. IV agora. Depois vemos o resto.")
    assert texto == "Ver o capítulo IV agora. Depois vemos o resto."
    assert chunk_text(texto, max_chars=30) == [
        "Ver o capítulo IV agora.",
        "Depois vemos o resto.",
    ]
