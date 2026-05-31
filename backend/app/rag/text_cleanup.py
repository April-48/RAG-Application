"""Lightweight text cleanup before chunking — empty lines, boilerplate, repeated headers."""

from __future__ import annotations

import re

from app.rag.pdf_parser import PageText

# Lines that are usually copyright / proceedings noise, not document content.
_BOILERPLATE_RE = re.compile(
    r"(all rights reserved|copyright\s*©|©\s*\d{4}|proceedings of the|"
    r"doi:\s*10\.|isbn[:\s-]|published by|permission to (?:make digital|copy)|"
    r"authorized licensed use limited to|acm reference format|"
    r"ieee catalog number|printed in the united states)",
    re.IGNORECASE,
)

# Very short lines that repeat on many pages are often page numbers or running headers.
_MIN_REPEAT_LINE_LEN = 12


# Drop empty lines and obvious boilerplate from one page of extracted text.
def clean_page_text(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _is_boilerplate_line(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


# Clean each page and remove lines repeated across many pages (headers/footers).
def clean_pages(pages: list[PageText]) -> list[PageText]:
    if not pages:
        return []

    cleaned = [
        PageText(page_number=page.page_number, text=clean_page_text(page.text))
        for page in pages
    ]
    cleaned = [page for page in cleaned if page.text.strip()]

    numbered_pages = [page for page in cleaned if page.page_number is not None]
    if len(numbered_pages) >= 3:
        line_counts: dict[str, int] = {}
        for page in numbered_pages:
            seen_on_page: set[str] = set()
            for line in page.text.splitlines():
                if len(line) < _MIN_REPEAT_LINE_LEN:
                    continue
                if line in seen_on_page:
                    continue
                seen_on_page.add(line)
                line_counts[line] = line_counts.get(line, 0) + 1

        threshold = max(2, (len(numbered_pages) * 2) // 5)
        repeated = {
            line for line, count in line_counts.items() if count >= threshold
        }
        if repeated:
            deduped: list[PageText] = []
            for page in cleaned:
                if not page.text:
                    continue
                kept = [line for line in page.text.splitlines() if line not in repeated]
                text = "\n".join(kept).strip()
                if text:
                    deduped.append(PageText(page_number=page.page_number, text=text))
            cleaned = deduped

    return cleaned


def _is_boilerplate_line(line: str) -> bool:
    if len(line) < 8:
        return False
    return _BOILERPLATE_RE.search(line) is not None
