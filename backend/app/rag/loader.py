"""Pick the right parser by file type (pdf / txt / docx) and return page text."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError
from app.rag.docx_parser import extract_docx_pages
from app.rag.pdf_parser import PageText, extract_pdf_pages


# Read a plain .txt file as one page with no page number.
def _extract_txt(path: str | Path) -> list[PageText]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return [PageText(page_number=None, text=text)]


# Extract text from a file as a list of pages.
# Raises UnsupportedFileTypeError when file_type has no parser.
def extract_pages(path: str | Path, file_type: str | None) -> list[PageText]:
    normalized = (file_type or "").lower().lstrip(".")
    if normalized == "pdf":
        return extract_pdf_pages(path)
    if normalized == "txt":
        return _extract_txt(path)
    if normalized == "docx":
        return extract_docx_pages(path)
    raise UnsupportedFileTypeError(normalized)
