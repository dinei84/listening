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
