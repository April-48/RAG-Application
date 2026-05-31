"""Classify user questions and extract answers from positional text.

Deterministic rules only — no extra LLM call. Modes drive retrieval in
``RetrievalService`` before generation runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


# Retrieval strategy I pick for a user question before fetching chunks.
class QueryMode(str, Enum):
    SEMANTIC = "semantic"
    DOCUMENT_BEGINNING = "document_beginning"
    DOCUMENT_ENDING = "document_ending"
    PAGE_LOOKUP = "page_lookup"
    SECTION_LOOKUP = "section_lookup"
    WHOLE_DOCUMENT_SUMMARY = "whole_document_summary"


# How I extract a direct answer from chunk text without calling the LLM.
class PositionalStyle(str, Enum):
    FIRST_SENTENCE = "first_sentence"
    FIRST_PARAGRAPH = "first_paragraph"
    LAST_SENTENCE = "last_sentence"
    LAST_PARAGRAPH = "last_paragraph"
    EXCERPT = "excerpt"


WEAK_EVIDENCE_MESSAGE = (
    "I could not find enough evidence in the uploaded document to answer this question."
)
SECTION_NOT_FOUND_MESSAGE = (
    "I could not find a section matching that name in the uploaded document."
)
PAGE_NOT_FOUND_MESSAGE = (
    "I could not find content for that page in the uploaded document."
)

_DOCUMENT_SCOPE_NAMES = frozenset(
    {"document", "doc", "this document", "the document", "whole document", "entire document"}
)

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

_PAGE_NUMBER_RE = re.compile(r"\bpage\s+(\d+)\b", re.IGNORECASE)

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


# Output of question classification — drives retrieval and direct answers.
@dataclass(frozen=True)
class RoutedQuery:
    mode: QueryMode
    positional_style: PositionalStyle | None = None
    page_number: int | None = None
    section_name: str | None = None


# Classify a question into a retrieval mode using deterministic phrase rules.
# Output: RoutedQuery with mode and optional page, section, or style hints.
def route_question(question: str) -> RoutedQuery:
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


# Pull a section title from the question, or None when it is not section-scoped.
def _extract_section_name(question: str) -> str | None:
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


# Trim quotes and trailing punctuation from an extracted section title.
def _clean_section_name(raw: str) -> str:
    cleaned = raw.strip().strip("\"'")
    cleaned = re.sub(r"[?.!,;:]+$", "", cleaned).strip()
    return cleaned


# Normalize a section title for fuzzy heading comparison.
def normalize_section_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", name.strip().lower().strip("\"'"))
    normalized = re.sub(r"^#+\s*", "", normalized)
    normalized = normalized.rstrip(":.")
    return normalized


# Return the first sentence from a chunk of text.
def extract_first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    match = re.search(r"^(.+?[.!?])(?:\s|$)", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    first_line = stripped.split("\n", 1)[0].strip()
    return first_line or stripped


# Return the first paragraph (block separated by blank lines).
def extract_first_paragraph(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    paragraphs = re.split(r"\n\s*\n", stripped)
    first = paragraphs[0].strip()
    if first:
        return first
    return stripped.split("\n", 1)[0].strip() or stripped


# Return the last sentence from a chunk of text.
def extract_last_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    sentences = re.findall(r"[^.!?]+[.!?]", stripped)
    if sentences:
        return sentences[-1].strip()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    return lines[-1] if lines else stripped


# Return the last paragraph (block separated by blank lines).
def extract_last_paragraph(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", stripped) if p.strip()]
    if paragraphs:
        return paragraphs[-1]
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    return lines[-1] if lines else stripped


# Return a short excerpt from the start of a chunk (default max 300 chars).
def extract_beginning_excerpt(text: str, *, max_len: int = 300) -> str:
    excerpt = extract_first_paragraph(text)
    if len(excerpt) <= max_len:
        return excerpt
    return excerpt[:max_len].rstrip() + "..."


# Return a short excerpt from the end of a chunk (default max 300 chars).
def extract_ending_excerpt(text: str, *, max_len: int = 300) -> str:
    excerpt = extract_last_paragraph(text)
    if len(excerpt) <= max_len:
        return excerpt
    return "..." + excerpt[-max_len:].lstrip()


# Build a direct answer from one chunk without calling the LLM.
def answer_from_positional_chunk(
    style: PositionalStyle, chunk_text: str
) -> str:
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


# Heuristic: short, title-like lines count as section headings.
def looks_like_heading(line: str) -> bool:
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


# Find a heading line in chunk text that matches the requested section name.
def find_matching_heading_line(text: str, section_name: str) -> str | None:
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


# Return the first sentence that appears after a section heading in chunk text.
def extract_first_sentence_after_heading(
    chunk_text: str, heading_line: str
) -> str:
    lower_text = chunk_text.lower()
    lower_heading = heading_line.lower()
    idx = lower_text.find(lower_heading)
    if idx < 0:
        return extract_first_sentence(chunk_text)
    after = chunk_text[idx + len(heading_line) :].strip()
    after = after.lstrip(":.- \n")
    return extract_first_sentence(after)


# Locate the chunk index and nearby chunks for a named section.
# Output: (start_index, chunk slice) or None when no heading matches.
def find_section_chunk_indices(
    chunks: list, section_name: str
) -> tuple[int, list] | None:
    for index, chunk in enumerate(chunks):
        if find_matching_heading_line(chunk.chunk_text, section_name):
            end = min(index + 3, len(chunks))
            return index, chunks[index:end]
    return None


# Pick first, last, and evenly spaced chunks for document-level summaries.
def select_representative_chunks(chunks: list, *, max_chunks: int = 6) -> list:
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
