"""Build the system + user messages sent to the LLM.

The LLM only sees retrieved chunk text — no outside knowledge. The system prompt
tells it to answer from context, synthesize across snippets when helpful, and
return a fixed insufficient-context line when nothing in the chunks is relevant.

This module also filters junk chunks and detects when the model gave that
fixed refusal line (so generation can retry once with softer instructions).
"""

from __future__ import annotations

import logging

from app.models.chunk import DocumentChunk

from app.rag.text_cleanup import is_boilerplate_line

logger = logging.getLogger("app.rag.prompt_builder")

# Exact string the LLM must return when chunks have no relevant info.
INSUFFICIENT_CONTEXT_MESSAGE = (
    "The document does not provide enough information to answer this question."
)

# Chunks shorter than this after stripping are treated as empty/unusable.
MIN_USABLE_CHUNK_CHARS = 30

# Only retry the LLM when the prompt already has at least this many context chars.
# Avoids retrying when we truly sent almost nothing.
MIN_CONTEXT_CHARS_FOR_RETRY = 80

# Drop a chunk when this share of its lines match obvious boilerplate patterns.
_MAX_BOILERPLATE_LINE_RATIO = 0.6

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions about a single document. "
    "Use ONLY the provided document context below — do not use outside knowledge "
    "or invent facts not supported by the context.\n\n"
    "Guidelines:\n"
    "- If the context contains relevant information, answer based on that context.\n"
    "- You may synthesize information across multiple retrieved snippets.\n"
    "- If the context only partially answers the question, give the best supported "
    "answer you can and briefly note any uncertainty or gaps.\n"
    "- Only when the retrieved context has NO relevant information for the question, "
    f'respond exactly with: "{INSUFFICIENT_CONTEXT_MESSAGE}"'
)


def is_insufficient_context_answer(answer: str) -> bool:
    """Return True when the model returned the fixed insufficient-context line."""
    return answer.strip() == INSUFFICIENT_CONTEXT_MESSAGE


def filter_usable_chunks(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    """Drop chunks that are too short to help the LLM.

    Whitespace-only or tiny fragments (under MIN_USABLE_CHUNK_CHARS) often come
    from bad PDF extraction. Sending them just wastes prompt space.
    """
    usable: list[DocumentChunk] = []
    for chunk in chunks:
        text = (chunk.chunk_text or "").strip()
        if len(text) >= MIN_USABLE_CHUNK_CHARS:
            usable.append(chunk)
    return usable


def is_obvious_boilerplate_chunk(text: str) -> bool:
    """Return True when most lines in a chunk look like conference/copyright noise.

    I count lines that match is_boilerplate_line(). When 60%+ of lines are noise,
    the whole chunk is probably a header page, not real content.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    boilerplate_lines = sum(1 for line in lines if is_boilerplate_line(line))
    return (boilerplate_lines / len(lines)) >= _MAX_BOILERPLATE_LINE_RATIO


def build_context(chunks: list[DocumentChunk]) -> str:
    """Format retrieved chunks into labeled text blocks for the LLM prompt.

    Each block looks like:
      [Source 0 | id ... | page 3, chunk 0]
      ... chunk text ...

    Page number is included when we have it (PDF). Chunk id helps with debugging.
    """
    parts: list[str] = []
    for chunk in chunks:
        if chunk.page_number is not None:
            location = f"page {chunk.page_number}, chunk {chunk.chunk_index}"
        else:
            location = f"chunk {chunk.chunk_index}"
        chunk_id = str(chunk.id) if chunk.id else f"idx-{chunk.chunk_index}"
        parts.append(
            f"[Source {chunk.chunk_index} | id {chunk_id} | {location}]\n"
            f"{chunk.chunk_text.strip()}"
        )
    return "\n\n".join(parts)


def build_messages(question: str, chunks: list[DocumentChunk]) -> list[dict[str, str]]:
    """Build the OpenAI-style message list for one Q&A turn.

    Returns two messages: system (grounding rules) and user (context + question).
    This list goes straight to llm.generate() or llm.generate_stream().
    """
    context = build_context(chunks)
    user_content = (
        f"Document context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer the question using the document context above. "
        "Synthesize across snippets when helpful."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# Extra instruction appended on the one retry attempt after insufficient-context.
RETRY_INSTRUCTION = (
    "The context may partially answer the question. If any snippet is relevant, "
    "provide the best grounded answer and mention uncertainty. Only return the "
    "insufficient response if none of the context is relevant."
)


def build_retry_messages(
    question: str, chunks: list[DocumentChunk]
) -> list[dict[str, str]]:
    """Same as build_messages but with a softer retry instruction appended.

    generation.py calls this when the first LLM answer was insufficient-context
    but we actually sent a meaningful amount of chunk text.
    """
    messages = build_messages(question, chunks)
    user = messages[1]
    user["content"] = f"{user['content']}\n\n{RETRY_INSTRUCTION}"
    return messages


def context_length_in_messages(messages: list[dict[str, str]]) -> int:
    """Count how many characters of document context are in the user message.

    I parse the "Document context:" section up to "Question:" so logging and
    retry decisions know how much text the LLM actually saw.
    """
    for message in messages:
        if message.get("role") == "user":
            content = message.get("content", "")
            marker = "Document context:\n"
            if marker in content:
                rest = content.split(marker, 1)[1]
                end = rest.find("\n\nQuestion:")
                if end != -1:
                    return len(rest[:end])
            return len(content)
    return 0


def log_prompt_context(
    *,
    document_id: str,
    question: str,
    route: str,
    chunks: list[DocumentChunk],
    messages: list[dict[str, str]],
) -> None:
    """Log chunk count and prompt size right before an LLM call.

    Helps debug "why did the model refuse?" — check context_chars in logs.
    Warns if chunks were passed but context_chars came out as 0 (build bug).
    """
    context_len = context_length_in_messages(messages)
    logger.info(
        "LLM prompt document_id=%s route=%s question=%r chunks=%s context_chars=%s",
        document_id,
        route,
        question[:120],
        len(chunks),
        context_len,
    )
    if chunks and context_len == 0:
        logger.warning(
            "LLM prompt has %s chunks but context_chars=0 — check build_context",
            len(chunks),
        )
