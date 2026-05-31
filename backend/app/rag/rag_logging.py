"""Logging helpers for the retrieval stage.

I keep this in its own file so retrieval_service and prompt_builder can both
log chunk details without creating a circular import between them.
"""

from __future__ import annotations

import logging
import uuid

from app.models.chunk import DocumentChunk

logger = logging.getLogger("app.rag.retrieval_service")

# How many characters of chunk text to show in log previews.
CHUNK_LOG_PREVIEW_CHARS = 250


def log_retrieved_chunks(
    *,
    document_id: uuid.UUID,
    question: str,
    route: str,
    chunks: list[DocumentChunk],
    scored: list[tuple[DocumentChunk, float]] | None = None,
) -> None:
    """Write one INFO log line summarizing what retrieval returned.

    For each chunk I log id, chunk_index, page, and a short text preview.
    When scored is provided (semantic search), I also log distance and similarity.

    pgvector returns cosine *distance* — lower means a better match.
    similarity = 1.0 - distance, so higher similarity means closer to the question.

    Call this after retrieval finishes so you can debug "why did the LLM see X?"
    from docker logs or local uvicorn output.
    """
    if not chunks:
        logger.info(
            "Retrieval document_id=%s route=%s question=%r chunks=0",
            document_id,
            route,
            question[:120],
        )
        return

    score_by_id: dict[uuid.UUID, float] = {}
    if scored:
        score_by_id = {chunk.id: distance for chunk, distance in scored}

    lines: list[str] = []
    for chunk in chunks:
        distance = score_by_id.get(chunk.id)
        score_part = ""
        if distance is not None:
            similarity = 1.0 - distance
            score_part = f" distance={distance:.4f} similarity={similarity:.4f}"
        preview = chunk.chunk_text.replace("\n", " ")[:CHUNK_LOG_PREVIEW_CHARS]
        lines.append(
            f"id={chunk.id} chunk_index={chunk.chunk_index} "
            f"page={chunk.page_number}{score_part} preview={preview!r}"
        )

    logger.info(
        "Retrieval document_id=%s route=%s question=%r chunks=%s\n  %s",
        document_id,
        route,
        question[:120],
        len(chunks),
        "\n  ".join(lines),
    )
