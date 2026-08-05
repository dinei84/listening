from processing.cleaner import clean_text


def test_clean_text_removes_repeated_header_across_pages():
    pages = [
        "MY BOOK TITLE\nThis is page one content.",
        "MY BOOK TITLE\nThis is page two content.",
    ]
    result = clean_text(pages)
    assert result == "This is page one content.\nThis is page two content."


def test_clean_text_removes_repeated_footer_across_pages():
    pages = [
        "This is page one content.\nConfidential - Internal Use Only",
        "This is page two content.\nConfidential - Internal Use Only",
    ]
    result = clean_text(pages)
    assert result == "This is page one content.\nThis is page two content."


def test_clean_text_fixes_hyphenation_across_line_break():
    pages = ["This is a demon-\nstration of hyphenation."]
    result = clean_text(pages)
    assert result == "This is a demonstration of hyphenation."


def test_clean_text_preserves_paragraph_breaks():
    pages = ["First paragraph.\n\nSecond paragraph, still on the same page."]
    result = clean_text(pages)
    assert result == "First paragraph.\n\nSecond paragraph, still on the same page."


def test_clean_text_handles_empty_input():
    assert clean_text([]) == ""
    assert clean_text(["", "   "]) == ""


# --- OS-035: junção de linhas quebradas pelo PDF --------------------------------


def test_clean_text_joins_lines_that_continue_a_sentence():
    """Quebra de linha do PDF no meio da frase vira espaço, não pausa no áudio."""
    pages = [
        (
            "A engenharia de seguranca e um campo\n"
            "que exige conhecimento amplo e\n"
            "multidisciplinar constante."
        )
    ]
    result = clean_text(pages)
    assert result == (
        "A engenharia de seguranca e um campo que exige conhecimento amplo e "
        "multidisciplinar constante."
    )


def test_clean_text_preserves_paragraph_boundaries_when_joining():
    """Linha em branco separa parágrafos — essa pausa é legítima e deve sobreviver."""
    pages = [
        (
            "Primeiro paragrafo que continua\nna linha seguinte.\n\n"
            "Segundo paragrafo tambem quebrado\nem duas linhas."
        )
    ]
    result = clean_text(pages)
    assert result == (
        "Primeiro paragrafo que continua na linha seguinte.\n\n"
        "Segundo paragrafo tambem quebrado em duas linhas."
    )


def test_clean_text_keeps_break_after_sentence_end():
    """Linha que termina frase mantém a quebra — não vira um bloco só."""
    pages = ["Primeira frase completa.\nSegunda frase completa."]
    result = clean_text(pages)
    assert result == "Primeira frase completa.\nSegunda frase completa."


def test_clean_text_join_runs_after_hyphenation_fix():
    """Hifenização é resolvida antes da junção; palavra partida não vira duas."""
    pages = [
        "Isto e uma demons-\ntracao de hifenizacao que continua\nna proxima linha."
    ]
    result = clean_text(pages)
    assert result == (
        "Isto e uma demonstracao de hifenizacao que continua na proxima linha."
    )


def test_clean_text_joins_sentence_split_across_pages():
    """Frase que atravessa a fronteira de página também é unida."""
    pages = ["O texto comeca aqui e", "continua na pagina seguinte."]
    result = clean_text(pages)
    assert result == "O texto comeca aqui e continua na pagina seguinte."


def test_clean_text_does_not_join_after_colon_or_semicolon():
    """`:` e `;` encerram a linha para efeito de junção (pausa intencional)."""
    pages = ["Considere o seguinte:\nprimeiro item da lista."]
    result = clean_text(pages)
    assert result == "Considere o seguinte:\nprimeiro item da lista."
