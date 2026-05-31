"""Classify user questions and extract answers from positional text.

Before I search pgvector, I look at the question wording. Some questions are
better handled with simple rules than with embeddings:
  - "Summarize the document" → pick chunks spread across the whole file
  - "What is on page 5?" → fetch chunks tagged with page_number=5
  - "First sentence of the document" → read chunk 0 directly, skip the LLM

This module uses phrase matching and regex only — no extra LLM call.
RetrievalService reads the RoutedQuery output and picks the right fetch strategy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class QueryMode(str, Enum):
    """Which retrieval strategy fits this question.

    SEMANTIC — default: embed the question and search pgvector.
    DOCUMENT_BEGINNING / DOCUMENT_ENDING — fetch first or last chunk.
    PAGE_LOOKUP — fetch chunks by page number (PDF only).
    SECTION_LOOKUP — find a heading that matches a section name.
    WHOLE_DOCUMENT_SUMMARY — sample chunks from start, middle, and end.
    """

    SEMANTIC = "semantic"
    DOCUMENT_BEGINNING = "document_beginning"
    DOCUMENT_ENDING = "document_ending"
    PAGE_LOOKUP = "page_lookup"
    SECTION_LOOKUP = "section_lookup"
    WHOLE_DOCUMENT_SUMMARY = "whole_document_summary"


class PositionalStyle(str, Enum):
    """How to cut an answer out of chunk text without calling the LLM.

    Used for questions like "first sentence" or "last paragraph".
    EXCERPT returns a short trimmed preview (about 300 chars).
    """

    FIRST_SENTENCE = "first_sentence"
    FIRST_PARAGRAPH = "first_paragraph"
    LAST_SENTENCE = "last_sentence"
    LAST_PARAGRAPH = "last_paragraph"
    EXCERPT = "excerpt"


# Fixed replies when retrieval finds nothing useful — ChatService sends these
# straight to the user without calling the LLM.
WEAK_EVIDENCE_MESSAGE = (
    "I could not find enough evidence in the uploaded document to answer this question."
)
SECTION_NOT_FOUND_MESSAGE = (
    "I could not find a section matching that name in the uploaded document."
)
PAGE_NOT_FOUND_MESSAGE = (
    "I could not find content for that page in the uploaded document."
)

# Section names that actually mean "the whole document", not a real heading.
_DOCUMENT_SCOPE_NAMES = frozenset(
    {"document", "doc", "this document", "the document", "whole document", "entire document"}
)

# Phrase lists below drive route_question(). I check if any phrase appears
# anywhere in the lowercased question (substring match, not exact match).

_SUMMARY_PHRASES = (
    "summarize the document",
    "summarize this document",
    "summary of the document",
    "document summary",
    "full summary",
    "give me a summary",
    "provide a summary",
    "overview of the document",
    "overview of this document",
    "main points",
    "key points",
    "what are the main points",
    "what are the key points",
)

_FIRST_SENTENCE_DOC_PHRASES = (
    "first sentence of the document",
    "first sentence of this document",
    "opening sentence of the document",
    "opening sentence",
    "what is the first sentence",
)

_FIRST_PARAGRAPH_DOC_PHRASES = ("first paragraph of the document", "first paragraph")

_BEGINNING_DOC_PHRASES = (
    "beginning of the document",
    "start of the document",
    "what does the document start with",
    "document start with",
    "how does the document begin",
)

_LAST_SENTENCE_DOC_PHRASES = (
    "last sentence of the document",
    "last sentence of this document",
    "final sentence of the document",
    "closing sentence of the document",
    "what is the last sentence",
)

_LAST_PARAGRAPH_DOC_PHRASES = (
    "last paragraph of the document",
    "final paragraph of the document",
    "last paragraph",
)

_ENDING_DOC_PHRASES = (
    "end of the document",
    "conclusion of the document",
    "how does the document end",
    "document end",
    "document conclude",
)

# Matches "page 5", "Page 12", etc. Group 1 is the page number string.
_PAGE_NUMBER_RE = re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE)

# Regex patterns to pull a section title out of the question text.
# Each pattern has one capture group for the section name.
_SECTION_NAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"first sentence of (?:the )?['\"]?(.+?)['\"]?(?:\s+section)?\??$",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:what is|what's|tell me about|describe) (?:in )?(?:the )?['\"]?(.+?)['\"]?\s+section",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:the )?['\"]?(.+?)['\"]?\s+section(?:\s+say|\s+cover|\s+about)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"section (?:called|named|titled)?\s*['\"]?(.+?)['\"]?\??$",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class RoutedQuery:
    """Output of question classification — tells RetrievalService what to do.

    mode is always set. The other fields are hints for specific modes:
      page_number for PAGE_LOOKUP
      section_name for SECTION_LOOKUP
      positional_style for beginning/ending/section first-sentence questions
    """

    mode: QueryMode
    positional_style: PositionalStyle | None = None
    page_number: int | None = None
    section_name: str | None = None


def retrieval_mode_info(routed: RoutedQuery) -> dict[str, str | int | None]:
    """API-friendly retrieval metadata for chat responses and history."""
    return {
        "retrieval_mode": routed.mode.value,
        "retrieval_page": routed.page_number,
        "retrieval_section": routed.section_name,
    }


def route_question(question: str) -> RoutedQuery:
    """Pick a retrieval mode from the question wording.

    I check patterns in priority order: summary → page → section → beginning
    → ending → semantic (fallback). First match wins.

    Returns a RoutedQuery. RetrievalService uses it to decide whether to search
    pgvector, read chunk 0, look up a page, etc.
    """
    q = question.strip()
    q_lower = q.lower()

    if any(phrase in q_lower for phrase in _SUMMARY_PHRASES):
        return RoutedQuery(mode=QueryMode.WHOLE_DOCUMENT_SUMMARY)

    page_match = _PAGE_NUMBER_RE.search(q)
    if page_match is not None and "page" in q_lower:
        return RoutedQuery(
            mode=QueryMode.PAGE_LOOKUP,
            page_number=int(page_match.group(1)),
        )

    section_name = _extract_section_name(q)
    if section_name is not None:
        style: PositionalStyle | None = None
        if "first sentence" in q_lower:
            style = PositionalStyle.FIRST_SENTENCE
        return RoutedQuery(
            mode=QueryMode.SECTION_LOOKUP,
            section_name=section_name,
            positional_style=style,
        )

    if any(phrase in q_lower for phrase in _FIRST_SENTENCE_DOC_PHRASES):
        return RoutedQuery(
            mode=QueryMode.DOCUMENT_BEGINNING,
            positional_style=PositionalStyle.FIRST_SENTENCE,
        )
    if any(phrase in q_lower for phrase in _FIRST_PARAGRAPH_DOC_PHRASES):
        return RoutedQuery(
            mode=QueryMode.DOCUMENT_BEGINNING,
            positional_style=PositionalStyle.FIRST_PARAGRAPH,
        )
    if any(phrase in q_lower for phrase in _BEGINNING_DOC_PHRASES):
        return RoutedQuery(
            mode=QueryMode.DOCUMENT_BEGINNING,
            positional_style=PositionalStyle.EXCERPT,
        )

    if any(phrase in q_lower for phrase in _LAST_SENTENCE_DOC_PHRASES):
        return RoutedQuery(
            mode=QueryMode.DOCUMENT_ENDING,
            positional_style=PositionalStyle.LAST_SENTENCE,
        )
    if any(phrase in q_lower for phrase in _LAST_PARAGRAPH_DOC_PHRASES):
        return RoutedQuery(
            mode=QueryMode.DOCUMENT_ENDING,
            positional_style=PositionalStyle.LAST_PARAGRAPH,
        )
    if any(phrase in q_lower for phrase in _ENDING_DOC_PHRASES):
        return RoutedQuery(
            mode=QueryMode.DOCUMENT_ENDING,
            positional_style=PositionalStyle.EXCERPT,
        )

    return RoutedQuery(mode=QueryMode.SEMANTIC)


def _extract_section_name(question: str) -> str | None:
    """Try to pull a section title from the question, or return None.

    I only run when the question mentions "section" or "first sentence of".
    If the captured name is really "the document", I ignore it — that is not
    a section heading.
    """
    q_lower = question.lower()
    if "section" not in q_lower and "first sentence of" not in q_lower:
        return None

    for pattern in _SECTION_NAME_PATTERNS:
        match = pattern.search(question)
        if not match:
            continue
        name = _clean_section_name(match.group(1))
        if name and normalize_section_name(name) not in _DOCUMENT_SCOPE_NAMES:
            return name
    return None


def _clean_section_name(raw: str) -> str:
    """Trim quotes and trailing punctuation from a regex capture group."""
    cleaned = raw.strip().strip("\"'")
    cleaned = re.sub(r"[?.!,;:]+$", "", cleaned).strip()
    return cleaned


def normalize_section_name(name: str) -> str:
    """Normalize a section title so fuzzy heading matching works.

    Lowercase, collapse whitespace, strip markdown # prefixes and trailing : .
    "  Introduction:  " and "introduction" should compare equal.
    """
    normalized = re.sub(r"\s+", " ", name.strip().lower().strip("\"'"))
    normalized = re.sub(r"^#+\s*", "", normalized)
    normalized = normalized.rstrip(":.")
    return normalized


def extract_first_sentence(text: str) -> str:
    """Return the first sentence from a chunk of text.

    I look for text ending in . ! or ?. If there is no sentence boundary,
    I fall back to the first line, then the whole stripped text.
    """
    stripped = text.strip()
    if not stripped:
        return ""
    match = re.search(r"^(.+?[.!?])(?:\s|$)", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    first_line = stripped.split("\n", 1)[0].strip()
    return first_line or stripped


def extract_first_paragraph(text: str) -> str:
    """Return the first paragraph — blocks separated by blank lines."""
    stripped = text.strip()
    if not stripped:
        return ""
    paragraphs = re.split(r"\n\s*\n", stripped)
    first = paragraphs[0].strip()
    if first:
        return first
    return stripped.split("\n", 1)[0].strip() or stripped


def extract_last_sentence(text: str) -> str:
    """Return the last sentence from a chunk of text.

    Same idea as extract_first_sentence but from the end. Falls back to the
    last non-empty line when there are no . ! ? boundaries.
    """
    stripped = text.strip()
    if not stripped:
        return ""
    sentences = re.findall(r"[^.!?]+[.!?]", stripped)
    if sentences:
        return sentences[-1].strip()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    return lines[-1] if lines else stripped


def extract_last_paragraph(text: str) -> str:
    """Return the last paragraph — blocks separated by blank lines."""
    stripped = text.strip()
    if not stripped:
        return ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", stripped) if p.strip()]
    if paragraphs:
        return paragraphs[-1]
    lines = [line.strip() for line in stripped.strip().splitlines() if line.strip()]
    return lines[-1] if lines else stripped


def extract_beginning_excerpt(text: str, *, max_len: int = 300) -> str:
    """Return a short preview from the start of the text (default 300 chars).

    I use the first paragraph, then truncate with "..." if it is too long.
    """
    excerpt = extract_first_paragraph(text)
    if len(excerpt) <= max_len:
        return excerpt
    return excerpt[:max_len].rstrip() + "..."


def extract_ending_excerpt(text: str, *, max_len: int = 300) -> str:
    """Return a short preview from the end of the text (default 300 chars).

    I use the last paragraph, then truncate with "..." at the front if needed.
    """
    excerpt = extract_last_paragraph(text)
    if len(excerpt) <= max_len:
        return excerpt
    return "..." + excerpt[-max_len:].lstrip()


def answer_from_positional_chunk(
    style: PositionalStyle, chunk_text: str
) -> str:
    """Build a direct answer from one chunk without calling the LLM.

    Picks the right extract_* helper based on PositionalStyle.
    Used when RetrievalService sets direct_answer on RetrievalResult.
    """
    if style is PositionalStyle.FIRST_SENTENCE:
        return extract_first_sentence(chunk_text)
    if style is PositionalStyle.FIRST_PARAGRAPH:
        return extract_first_paragraph(chunk_text)
    if style is PositionalStyle.LAST_SENTENCE:
        return extract_last_sentence(chunk_text)
    if style is PositionalStyle.LAST_PARAGRAPH:
        return extract_last_paragraph(chunk_text)
    if style is PositionalStyle.EXCERPT:
        return extract_beginning_excerpt(chunk_text)
    return chunk_text.strip()


def looks_like_heading(line: str) -> bool:
    """Guess whether a line is a section heading rather than body text.

    Heuristics: markdown # prefix, ends with :, ALL CAPS short line, or
    just a short line under 100 chars. Long paragraphs return False.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 150:
        return False
    if stripped.startswith("#"):
        return True
    if stripped.endswith(":") and len(stripped) < 100:
        return True
    if stripped.isupper() and len(stripped.split()) <= 12:
        return True
    return len(stripped) < 100


def find_matching_heading_line(text: str, section_name: str) -> str | None:
    """Find a heading line inside chunk text that matches the requested section.

    I compare normalized names. Exact match wins. Otherwise I accept a substring
    match when the line also looks_like_heading().
    """
    target = normalize_section_name(section_name)
    if not target:
        return None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        line_norm = normalize_section_name(stripped)
        if line_norm == target:
            return stripped
        if target in line_norm and looks_like_heading(stripped):
            return stripped
    return None


def extract_first_sentence_after_heading(
    chunk_text: str, heading_line: str
) -> str:
    """Return the first sentence that comes after a section heading in the chunk.

    I find the heading position, skip past it and any : . - whitespace,
    then run extract_first_sentence on what remains.
    """
    lower_text = chunk_text.lower()
    lower_heading = heading_line.lower()
    idx = lower_text.find(lower_heading)
    if idx < 0:
        return extract_first_sentence(chunk_text)
    after = chunk_text[idx + len(heading_line) :].strip()
    after = after.lstrip(":.- \n")
    return extract_first_sentence(after)


def find_section_chunk_indices(
    chunks: list, section_name: str
) -> tuple[int, list] | None:
    """Find which chunk contains a section heading and return nearby chunks too.

    I scan chunks in order. When a heading matches section_name, I return
    (start_index, chunks[start_index : start_index + 3]). Up to 3 chunks gives
    the LLM a bit of context after the heading.

    Returns None when no chunk contains a matching heading.
    """
    for index, chunk in enumerate(chunks):
        if find_matching_heading_line(chunk.chunk_text, section_name):
            end = min(index + 3, len(chunks))
            return index, chunks[index:end]
    return None


def select_representative_chunks(chunks: list, *, max_chunks: int = 6) -> list:
    """Pick chunks spread across the document for summary-style questions.

    I always include the first and last chunk. The remaining slots are filled
    with evenly spaced chunks from the middle. If the document has fewer chunks
    than max_chunks, I return all of them.
    """
    if not chunks:
        return []
    if len(chunks) <= max_chunks:
        return list(chunks)

    indices: set[int] = {0, len(chunks) - 1}
    middle_slots = max_chunks - 2
    if middle_slots > 0:
        step = (len(chunks) - 1) / (middle_slots + 1)
        for slot in range(1, middle_slots + 1):
            indices.add(min(int(round(slot * step)), len(chunks) - 1))

    return [chunks[i] for i in sorted(indices)]
