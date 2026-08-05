from processing.chunker import chunk_text


def test_chunk_text_never_splits_a_sentence():
    text = "Sentence one. Sentence two. Sentence three."
    chunks = chunk_text(text, max_chars=20)
    assert chunks == ["Sentence one.", "Sentence two.", "Sentence three."]


def test_chunk_text_respects_max_chars_when_possible():
    text = "Sentence one. Sentence two. Sentence three."
    chunks = chunk_text(text, max_chars=27)
    assert chunks == ["Sentence one. Sentence two.", "Sentence three."]


def test_chunk_text_keeps_oversized_single_sentence_as_one_chunk():
    long_sentence = (
        "This is a single very long sentence that exceeds the configured "
        "maximum chunk size by itself."
    )
    text = f"Short one. {long_sentence} Short two."
    chunks = chunk_text(text, max_chars=20)
    assert chunks == ["Short one.", long_sentence, "Short two."]
    assert len(long_sentence) > 20


def test_chunk_text_handles_empty_input():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_contract_unchanged():
    # Contrato da OS-008 (regressão): uma sentença sem .!? interno nunca é
    # cortada ao meio, mesmo que estoure sozinha o max_chars.
    long_sentence = " ".join(["palavra"] * 60)
    chunks = chunk_text(long_sentence, max_chars=50)
    assert chunks == [long_sentence]
    assert len(long_sentence) > 50


# --- OS-035: abreviações não são fim de sentença --------------------------------


def test_chunk_text_does_not_split_on_common_abbreviations():
    texto = "Segundo o Dr. Silva a arquitetura mudou muito nos ultimos anos."
    # max_chars pequeno forçaria a fronteira logo após "Dr." se ela fosse
    # tratada como fim de sentença.
    assert chunk_text(texto, max_chars=14) == [texto]


def test_chunk_text_does_not_split_on_page_abbreviation():
    texto = "Ver pag. 42 do manual para os detalhes completos do procedimento."
    assert chunk_text(texto, max_chars=14) == [texto]


def test_chunk_text_does_not_split_on_name_initial():
    texto = "O autor Robert C. Martin escreveu diversos livros sobre o assunto."
    assert chunk_text(texto, max_chars=14) == [texto]


def test_chunk_text_still_splits_on_real_sentence_end():
    texto = "Primeira frase. Segunda frase."
    assert chunk_text(texto, max_chars=20) == ["Primeira frase.", "Segunda frase."]
