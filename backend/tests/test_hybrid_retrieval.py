"""Hybrid retrieval tests — router modes, metadata lookup, evidence threshold."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.core.config import get_settings
from app.models.chunk import DocumentChunk
from app.rag.query_router import (
    PositionalStyle,
    QueryMode,
    SECTION_NOT_FOUND_MESSAGE,
    WEAK_EVIDENCE_MESSAGE,
    extract_first_sentence,
    route_question,
    select_representative_chunks,
)
from app.rag.retrieval_service import RetrievalService


def _chunk(
    *,
    document_id: uuid.UUID,
    chunk_index: int,
    text: str,
    page_number: int | None = None,
) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        page_number=page_number,
        chunk_text=text,
        embedding=[0.1] * 384,
    )


def test_route_semantic_default() -> None:
    routed = route_question("What is the refund policy?")
    assert routed.mode is QueryMode.SEMANTIC


def test_route_document_beginning_first_sentence() -> None:
    routed = route_question("What is the first sentence of the document?")
    assert routed.mode is QueryMode.DOCUMENT_BEGINNING
    assert routed.positional_style is PositionalStyle.FIRST_SENTENCE


def test_route_section_lookup() -> None:
    routed = route_question("What is the first sentence of the Methods section?")
    assert routed.mode is QueryMode.SECTION_LOOKUP
    assert routed.section_name == "Methods"
    assert routed.positional_style is PositionalStyle.FIRST_SENTENCE


def test_route_page_lookup() -> None:
    routed = route_question("What is on page 2?")
    assert routed.mode is QueryMode.PAGE_LOOKUP
    assert routed.page_number == 2


def test_route_summary() -> None:
    routed = route_question("Give me a summary of the document")
    assert routed.mode is QueryMode.WHOLE_DOCUMENT_SUMMARY


def test_semantic_route_uses_vector_search() -> None:
    document_id = uuid.uuid4()
    vector_hit = _chunk(
        document_id=document_id,
        chunk_index=2,
        text="Refund within 30 days.",
    )

    chunks_repo = MagicMock()
    chunks_repo.search_by_document_with_distance.return_value = [(vector_hit, 0.2)]

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 384

    service = RetrievalService(MagicMock(), embedder=embedder)
    service.chunks = chunks_repo

    result = service.retrieve(document_id, "What is the refund window?")

    embedder.embed_query.assert_called_once()
    chunks_repo.search_by_document_with_distance.assert_called_once()
    assert result.routed.mode is QueryMode.SEMANTIC
    assert len(result.chunks) == 1
    assert result.chunks[0].chunk_index == 2
    assert result.direct_answer is None
    assert result.skip_llm_message is None


def test_document_beginning_uses_first_chunk_not_vector_search() -> None:
    document_id = uuid.uuid4()
    first_chunk = _chunk(
        document_id=document_id,
        chunk_index=0,
        text="The document opens with this line. More text follows.",
    )

    chunks_repo = MagicMock()
    chunks_repo.get_first_chunk.return_value = first_chunk
    embedder = MagicMock()

    service = RetrievalService(MagicMock(), embedder=embedder)
    service.chunks = chunks_repo

    result = service.retrieve(document_id, "What is the first sentence of the document?")

    chunks_repo.get_first_chunk.assert_called_once_with(document_id)
    embedder.embed_query.assert_not_called()
    assert result.chunks[0].chunk_index == 0
    assert result.direct_answer == "The document opens with this line."


def test_section_first_sentence_uses_heading_lookup() -> None:
    document_id = uuid.uuid4()
    intro_chunk = _chunk(
        document_id=document_id,
        chunk_index=1,
        text="Introduction\nThis section opens with facts. More follows.",
    )
    other_chunk = _chunk(
        document_id=document_id,
        chunk_index=0,
        text="Title page content.",
    )

    chunks_repo = MagicMock()
    chunks_repo.list_by_document.return_value = [other_chunk, intro_chunk]

    service = RetrievalService(MagicMock(), embedder=MagicMock())
    service.chunks = chunks_repo

    result = service.retrieve(
        document_id, "What is the first sentence of the Introduction section?"
    )

    chunks_repo.list_by_document.assert_called_once_with(document_id)
    assert result.routed.mode is QueryMode.SECTION_LOOKUP
    assert result.direct_answer == "This section opens with facts."
    assert [c.chunk_index for c in result.chunks] == [1]


def test_page_lookup_uses_page_metadata() -> None:
    document_id = uuid.uuid4()
    page_chunk = _chunk(
        document_id=document_id,
        chunk_index=3,
        page_number=2,
        text="Content on page two.",
    )

    chunks_repo = MagicMock()
    chunks_repo.has_page_metadata.return_value = True
    chunks_repo.get_chunks_by_page.return_value = [page_chunk]
    embedder = MagicMock()

    service = RetrievalService(MagicMock(), embedder=embedder)
    service.chunks = chunks_repo

    result = service.retrieve(document_id, "What is on page 2?")

    chunks_repo.get_chunks_by_page.assert_called_once_with(document_id, 2)
    embedder.embed_query.assert_not_called()
    assert result.routed.mode is QueryMode.PAGE_LOOKUP
    assert len(result.chunks) == 1
    assert result.chunks[0].page_number == 2


def test_unknown_section_returns_no_answer() -> None:
    document_id = uuid.uuid4()
    chunks_repo = MagicMock()
    chunks_repo.list_by_document.return_value = [
        _chunk(
            document_id=document_id,
            chunk_index=0,
            text="No headings here, just body text.",
        )
    ]

    service = RetrievalService(MagicMock(), embedder=MagicMock())
    service.chunks = chunks_repo

    result = service.retrieve(
        document_id, "Tell me about the Nonexistent section"
    )

    assert result.chunks == []
    assert result.skip_llm_message == SECTION_NOT_FOUND_MESSAGE


def test_semantic_below_threshold_returns_no_answer_when_enforced() -> None:
    document_id = uuid.uuid4()
    weak_hit = _chunk(
        document_id=document_id,
        chunk_index=0,
        text="Unrelated boilerplate.",
    )

    chunks_repo = MagicMock()
    chunks_repo.search_by_document_with_distance.return_value = [(weak_hit, 0.95)]

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 384

    service = RetrievalService(MagicMock(), embedder=embedder)
    service.chunks = chunks_repo

    settings = get_settings()
    with (
        patch.object(settings, "retrieval_min_similarity", 0.32),
        patch.object(settings, "retrieval_enforce_similarity_threshold", True),
    ):
        result = service.retrieve(document_id, "What is the CEO's favorite color?")

    assert result.chunks == []
    assert result.skip_llm_message == WEAK_EVIDENCE_MESSAGE


def test_semantic_below_threshold_still_returns_chunks_when_not_enforced() -> None:
    document_id = uuid.uuid4()
    weak_hit = _chunk(
        document_id=document_id,
        chunk_index=0,
        text="Limitations include small sample size.",
    )

    chunks_repo = MagicMock()
    chunks_repo.search_by_document_with_distance.return_value = [(weak_hit, 0.95)]

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 384

    service = RetrievalService(MagicMock(), embedder=embedder)
    service.chunks = chunks_repo

    settings = get_settings()
    with (
        patch.object(settings, "retrieval_min_similarity", 0.32),
        patch.object(settings, "retrieval_enforce_similarity_threshold", False),
    ):
        result = service.retrieve(
            document_id, "What limitations does the paper mention?"
        )

    assert result.chunks == [weak_hit]
    assert result.skip_llm_message is None


def test_summary_retrieves_representative_chunks() -> None:
    document_id = uuid.uuid4()
    all_chunks = [
        _chunk(
            document_id=document_id,
            chunk_index=i,
            text=f"Chunk {i}.",
            page_number=i + 1,
        )
        for i in range(10)
    ]

    chunks_repo = MagicMock()
    chunks_repo.list_by_document.return_value = all_chunks

    service = RetrievalService(MagicMock(), embedder=MagicMock())
    service.chunks = chunks_repo

    result = service.retrieve(document_id, "Give me a summary of the document")

    assert result.routed.mode is QueryMode.WHOLE_DOCUMENT_SUMMARY
    indices = [chunk.chunk_index for chunk in result.chunks]
    assert indices[0] == 0
    assert indices[-1] == 9
    assert len(result.chunks) <= 6
    assert indices == sorted(indices)


def test_select_representative_chunks_even_spacing() -> None:
    chunks = list(range(12))
    selected = select_representative_chunks(chunks, max_chunks=6)
    assert selected[0] == 0
    assert selected[-1] == 11
    assert len(selected) == 6


def test_extract_first_sentence() -> None:
    text = "Hello world. This is the second sentence."
    assert extract_first_sentence(text) == "Hello world."
