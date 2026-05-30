"""PDF -> text per page using PyMuPDF (fitz). Keeps page numbers for citations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class PageText:
    """Extracted text for a single page.

    `page_number` is 1-based for paged formats (PDF) and ``None`` for formats
    without pages (e.g. plain text).
    """

    page_number: int | None
    text: str


def extract_pdf_pages(path: str | Path) -> list[PageText]:
    """Return per-page text for a PDF file."""
    pages: list[PageText] = []
    with fitz.open(str(path)) as doc:
        for index, page in enumerate(doc, start=1):
            pages.append(PageText(page_number=index, text=page.get_text()))
    return pages
