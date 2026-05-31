"""Build the system + user messages for the LLM.

Grounded answers from retrieved chunks; insufficient-context only when truly no signal.
"""

from __future__ import annotations

import logging

from app.models.chunk import DocumentChunk

logger = logging.getLogger("app.rag.prompt_builder")

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The document does not provide enough information to answer this question."
)

# Chunks shorter than this after stripping are treated as empty/unusable for generation.
MIN_USABLE_CHUNK_CHARS = 30

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


# True when the model returned the fixed insufficient-context line (exact or trimmed).
def is_insufficient_context_answer(answer: str) -> bool:
    return answer.strip() == INSUFFICIENT_CONTEXT_MESSAGE


# Drop whitespace-only or extremely short chunks that would confuse the LLM.
def filter_usable_chunks(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    usable: list[DocumentChunk] = []
    for chunk in chunks:
        text = (chunk.chunk_text or "").strip()
        if len(text) >= MIN_USABLE_CHUNK_CHARS:
            usable.append(chunk)
    return usable


# Format retrieved chunks into labeled text blocks for the LLM prompt.
def build_context(chunks: list[DocumentChunk]) -> str:
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


# Build system + user messages telling the LLM to answer from context only.
# Output: OpenAI-style message list ready for llm.generate or generate_stream.
def build_messages(question: str, chunks: list[DocumentChunk]) -> list[dict[str, str]]:
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


# Sum character length of context text embedded in the user message.
def context_length_in_messages(messages: list[dict[str, str]]) -> int:
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


# Log chunk count and final prompt context size before an LLM call.
def log_prompt_context(
    *,
    document_id: str,
    question: str,
    route: str,
    chunks: list[DocumentChunk],
    messages: list[dict[str, str]],
) -> None:
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
