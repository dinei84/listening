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
