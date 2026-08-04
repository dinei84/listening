from storage import uploads


def test_pdf_path_for_returns_same_path_for_api_and_worker():
    book_id = "book-123"
    expected = uploads.UPLOAD_DIR / f"{book_id}.pdf"

    assert uploads.pdf_path_for(book_id) == expected
    assert uploads.pdf_path_for(book_id) == uploads.pdf_path_for(book_id)
