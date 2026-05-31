"""DOCX -> plain text via python-docx (paragraphs + tables).

No real page numbers in DOCX, so we return one big PageText with page_number=None.
Legacy .doc is not supported — only .docx.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from docx.table import Table

from app.rag.pdf_parser import PageText


# Flatten a DOCX table to one line per row: cell | cell | cell.
def _table_lines(table: Table) -> list[str]:
    lines: list[str] = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        cells = [cell for cell in cells if cell]
        if cells:
            lines.append(" | ".join(cells))
    return lines


# Return DOCX text as a single PageText with page_number=None.
# Empty input yields one empty PageText so downstream splitting marks the doc failed.
def extract_docx_pages(path: str | Path) -> list[PageText]:
    document = DocxDocument(str(path))

    parts: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    for table in document.tables:
        parts.extend(_table_lines(table))

    return [PageText(page_number=None, text="\n".join(parts))]
