"""Pick the right parser for each upload type and return cleaned page text.

Supported types: pdf, txt, docx. The entry point is extract_pages() — ingestion
calls it with the on-disk path and the file_type from the documents table.
After parsing, I always run text_cleanup.clean_pages() before chunking.
"""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError
from app.rag.docx_parser import extract_docx_pages
from app.rag.pdf_parser import PageText, extract_pdf_pages
from app.rag.text_cleanup import clean_pages


def _extract_txt(path: str | Path) -> list[PageText]:
    """Read a plain .txt file as one page with no page number.

    TXT has no page concept, so page_number is None. The whole file becomes
    one text block that text_splitter will slice into chunks.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return [PageText(page_number=None, text=text)]


def extract_pages(path: str | Path, file_type: str | None) -> list[PageText]:
    """Extract text from an uploaded file and clean it before chunking.

    I normalize file_type (strip dots, lowercase), dispatch to the right parser,
    then run clean_pages() to remove boilerplate and repeated headers.

    Raises UnsupportedFileTypeError when file_type is not pdf, txt, or docx.
    Returns a list of PageText — may be empty if the file has no readable text.
    """
    normalized = (file_type or "").lower().lstrip(".")
    if normalized == "pdf":
        pages = extract_pdf_pages(path)
    elif normalized == "txt":
        pages = _extract_txt(path)
    elif normalized == "docx":
        pages = extract_docx_pages(path)
    else:
        raise UnsupportedFileTypeError(normalized)
    return clean_pages(pages)
