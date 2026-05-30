"""DOCX -> plain text via python-docx (paragraphs + tables).

No real page numbers in DOCX, so we return one big PageText with page_number=None.
Legacy .doc is not supported — only .docx.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from docx.table import Table

from app.rag.pdf_parser import PageText


def _table_lines(table: Table) -> list[str]:
    """Flatten a table to one line per row: ``cell | cell | cell``."""
    lines: list[str] = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        cells = [cell for cell in cells if cell]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def extract_docx_pages(path: str | Path) -> list[PageText]:
    """Return the DOCX text as a single page.

    Paragraph text comes first, then table text. Empty input yields a single
    empty `PageText`, matching the PDF/TXT flow where the downstream splitter
    produces no chunks (and the document is marked ``failed``).
    """
    document = DocxDocument(str(path))

    parts: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    for table in document.tables:
        parts.extend(_table_lines(table))

    return [PageText(page_number=None, text="\n".join(parts))]
