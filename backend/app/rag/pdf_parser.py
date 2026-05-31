"""Extract plain text from PDF files, one page at a time.

I use PyMuPDF (import name: fitz) because it is fast and does not need extra
system dependencies. Page numbers are kept so users can ask "what is on page 5?"
and citations can show a page label in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class PageText:
    """One page of extracted text plus its page number.

    page_number is 1-based for PDFs (page 1 = first page).
    For TXT/DOCX there is no real pagination, so page_number is None.
    """

    page_number: int | None
    text: str


def extract_pdf_pages(path: str | Path) -> list[PageText]:
    """Read a PDF and return one PageText per page.

    I open the file with PyMuPDF, call get_text() on each page, and preserve
    the original page order. Empty pages are still included — cleanup happens
    later in text_cleanup.clean_pages().
    """
    pages: list[PageText] = []
    with fitz.open(str(path)) as doc:
        for index, page in enumerate(doc, start=1):
            pages.append(PageText(page_number=index, text=page.get_text()))
    return pages
