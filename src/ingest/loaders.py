"""Load source PDFs into per-page text."""

from pathlib import Path

import pymupdf


def load_pdf(path: Path) -> list[str]:
    """Return the text of each page, in order. Index i is page i+1 in the PDF."""
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]
