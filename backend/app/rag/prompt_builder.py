"""Build the system + user messages for the LLM.

Rule: answer ONLY from provided context, or say the fixed "not enough info" line.
"""

from __future__ import annotations

from app.models.chunk import DocumentChunk

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The document does not provide enough information to answer this question."
)

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions about a single document. "
    "Answer using ONLY the provided context. Do not use any outside knowledge or "
    "make assumptions. If the context does not contain enough information to "
    f"answer the question, respond exactly with: \"{INSUFFICIENT_CONTEXT_MESSAGE}\""
)


# Format retrieved chunks into labeled text blocks for the LLM prompt.
def build_context(chunks: list[DocumentChunk]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        if chunk.page_number is not None:
            location = f"page {chunk.page_number}, chunk {chunk.chunk_index}"
        else:
            location = f"chunk {chunk.chunk_index}"
        parts.append(f"[Source {chunk.chunk_index} | {location}]\n{chunk.chunk_text}")
    return "\n\n".join(parts)


# Build system + user messages telling the LLM to answer from context only.
# Output: OpenAI-style message list ready for llm.generate or generate_stream.
def build_messages(question: str, chunks: list[DocumentChunk]) -> list[dict[str, str]]:
    context = build_context(chunks)
    user_content = (
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer the question using only the context above."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
