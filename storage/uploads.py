from pathlib import Path

UPLOAD_DIR = Path("uploads")


def pdf_path_for(book_id: str) -> Path:
    """Devolve o caminho do PDF enviado para um book_id, dentro de UPLOAD_DIR."""
    return UPLOAD_DIR / f"{book_id}.pdf"


def delete_pdf(book_id: str) -> None:
    """Remove o PDF enviado para um book_id, se existir. Nenhum efeito caso contrário."""
    pdf_path_for(book_id).unlink(missing_ok=True)
