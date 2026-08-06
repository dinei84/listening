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
