"""Clean up raw text before chunking.

PDF parsers often leave empty lines, copyright footers, and the same header on
every page. This module strips that noise so embeddings and retrieval focus on
real content. It runs right after extract_pages() and before split_pages().
"""

from __future__ import annotations

import re

from app.rag.pdf_parser import PageText

# Lines that look like conference/copyright boilerplate, not document body text.
# I match common phrases like "All rights reserved" or "Proceedings of the".
_BOILERPLATE_RE = re.compile(
    r"(all rights reserved|copyright\s*©|©\s*\d{4}|proceedings of the|"
    r"doi:\s*10\.|isbn[:\s-]|published by|permission to (?:make digital|copy)|"
    r"authorized licensed use limited to|acm reference format|"
    r"ieee catalog number|printed in the united states)",
    re.IGNORECASE,
)

# Lines shorter than this are often page numbers or running headers.
# I only count longer lines when looking for text repeated across pages.
_MIN_REPEAT_LINE_LEN = 12


def clean_page_text(text: str) -> str:
    """Clean one page of extracted text.

    I drop blank lines and lines that match obvious boilerplate patterns.
    The result keeps normal body text, one line per row, joined with newlines.
    """
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _is_boilerplate_line(stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def clean_pages(pages: list[PageText]) -> list[PageText]:
    """Clean every page and remove headers/footers that repeat on many pages.

    Step 1: run clean_page_text on each page and drop pages that end up empty.
    Step 2: if there are at least 3 numbered pages (PDF), find lines that show
    up on many pages — those are usually headers or footers — and remove them.

    The repeat threshold is 40% of page count (minimum 2). So on a 10-page PDF,
    a line must appear on at least 4 pages before I treat it as noise.
    """
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


def is_boilerplate_line(line: str) -> bool:
    """Return True when a line looks like copyright or proceedings noise.

    Very short lines (under 8 chars) are kept — they might be section numbers.
    Longer lines are checked against _BOILERPLATE_RE.
    """
    if len(line) < 8:
        return False
    return _BOILERPLATE_RE.search(line) is not None


def _is_boilerplate_line(line: str) -> bool:
    """Internal alias used by clean_page_text — same logic as is_boilerplate_line."""
    return is_boilerplate_line(line)
