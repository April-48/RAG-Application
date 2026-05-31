"""Query router classification tests (legacy file — see test_hybrid_retrieval)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.models.chunk import DocumentChunk
from app.rag.query_router import (
    PositionalStyle,
    QueryMode,
    answer_from_positional_chunk,
    route_question,
)
from app.rag.retrieval_service import RetrievalService


def test_route_beginning_first_sentence() -> None:
    routed = route_question("What is the first sentence of the document?")
    assert routed.mode is QueryMode.DOCUMENT_BEGINNING
    assert routed.positional_style is PositionalStyle.FIRST_SENTENCE


def test_route_semantic_default() -> None:
    routed = route_question("What is the refund policy?")
    assert routed.mode is QueryMode.SEMANTIC


def test_answer_from_beginning_chunk_first_sentence_only() -> None:
    text = "Alpha starts here. Beta follows later."
    answer = answer_from_positional_chunk(PositionalStyle.FIRST_SENTENCE, text)
    assert answer == "Alpha starts here."


def test_beginning_route_uses_first_chunk_not_vector_search() -> None:
    document_id = uuid.uuid4()
    first_chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        chunk_index=0,
        page_number=1,
        chunk_text="The document opens with this line. More text follows.",
        embedding=[0.1] * 384,
    )

    chunks_repo = MagicMock()
    chunks_repo.get_first_chunk.return_value = first_chunk

    embedder = MagicMock()
    service = RetrievalService(MagicMock(), embedder=embedder)
    service.chunks = chunks_repo

    result = service.retrieve(document_id, "What is the first sentence of the document?")

    chunks_repo.get_first_chunk.assert_called_once_with(document_id)
    embedder.embed_query.assert_not_called()
    assert len(result.chunks) == 1
    assert result.chunks[0].chunk_index == 0
