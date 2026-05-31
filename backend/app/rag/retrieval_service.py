"""Retrieve relevant chunks — hybrid router picks strategy, always one document."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chunk import DocumentChunk
from app.rag.embedding_service import Embedder, get_embedding_service
from app.rag.query_router import (
    PAGE_NOT_FOUND_MESSAGE,
    SECTION_NOT_FOUND_MESSAGE,
    WEAK_EVIDENCE_MESSAGE,
    PositionalStyle,
    QueryMode,
    RoutedQuery,
    answer_from_positional_chunk,
    extract_first_sentence_after_heading,
    extract_ending_excerpt,
    find_matching_heading_line,
    find_section_chunk_indices,
    route_question,
    select_representative_chunks,
)
from app.repositories.chunk_repository import ChunkRepository

SUMMARY_MAX_CHUNKS = 6


@dataclass(frozen=True)
class RetrievalResult:
    """Chunks plus optional direct answer or no-LLM fallback message."""

    chunks: list[DocumentChunk]
    routed: RoutedQuery
    direct_answer: str | None = None
    skip_llm_message: str | None = None


class RetrievalService:
    """Route the question, then fetch chunks via metadata or pgvector search."""

    def __init__(self, db: Session, embedder: Embedder | None = None) -> None:
        """Wire chunk repo and embedder for retrieval."""
        self.chunks = ChunkRepository(db)
        self.embedder = embedder or get_embedding_service()

    def retrieve(
        self, document_id: uuid.UUID, question: str, top_k: int | None = None
    ) -> RetrievalResult:
        """Return chunks and routing metadata for a question."""
        routed = route_question(question)

        if routed.mode is QueryMode.DOCUMENT_BEGINNING:
            return self._retrieve_document_beginning(document_id, routed)
        if routed.mode is QueryMode.DOCUMENT_ENDING:
            return self._retrieve_document_ending(document_id, routed)
        if routed.mode is QueryMode.PAGE_LOOKUP:
            return self._retrieve_page_lookup(document_id, question, routed, top_k)
        if routed.mode is QueryMode.SECTION_LOOKUP:
            return self._retrieve_section_lookup(document_id, routed)
        if routed.mode is QueryMode.WHOLE_DOCUMENT_SUMMARY:
            return self._retrieve_summary(document_id, routed)

        return self._retrieve_semantic(document_id, question, routed, top_k)

    def _retrieve_document_beginning(
        self, document_id: uuid.UUID, routed: RoutedQuery
    ) -> RetrievalResult:
        first = self.chunks.get_first_chunk(document_id)
        if first is None:
            return RetrievalResult(chunks=[], routed=routed)
        style = routed.positional_style or PositionalStyle.EXCERPT
        return RetrievalResult(
            chunks=[first],
            routed=routed,
            direct_answer=answer_from_positional_chunk(style, first.chunk_text),
        )

    def _retrieve_document_ending(
        self, document_id: uuid.UUID, routed: RoutedQuery
    ) -> RetrievalResult:
        last = self.chunks.get_last_chunk(document_id)
        if last is None:
            return RetrievalResult(chunks=[], routed=routed)
        style = routed.positional_style or PositionalStyle.EXCERPT
        if style is PositionalStyle.EXCERPT:
            answer = extract_ending_excerpt(last.chunk_text)
        else:
            answer = answer_from_positional_chunk(style, last.chunk_text)
        return RetrievalResult(
            chunks=[last],
            routed=routed,
            direct_answer=answer,
        )

    def _retrieve_page_lookup(
        self,
        document_id: uuid.UUID,
        question: str,
        routed: RoutedQuery,
        top_k: int | None,
    ) -> RetrievalResult:
        page_number = routed.page_number
        if page_number is None:
            return self._retrieve_semantic(document_id, question, routed, top_k)

        if not self.chunks.has_page_metadata(document_id):
            return self._retrieve_semantic(
                document_id,
                question,
                RoutedQuery(mode=QueryMode.SEMANTIC),
                top_k,
            )

        page_chunks = self.chunks.get_chunks_by_page(document_id, page_number)
        if not page_chunks:
            return RetrievalResult(
                chunks=[],
                routed=routed,
                skip_llm_message=PAGE_NOT_FOUND_MESSAGE,
            )
        return RetrievalResult(chunks=page_chunks, routed=routed)

    def _retrieve_section_lookup(
        self, document_id: uuid.UUID, routed: RoutedQuery
    ) -> RetrievalResult:
        section_name = routed.section_name
        if not section_name:
            return RetrievalResult(chunks=[], routed=routed)

        all_chunks = self.chunks.list_by_document(document_id)
        match = find_section_chunk_indices(all_chunks, section_name)
        if match is None:
            return RetrievalResult(
                chunks=[],
                routed=routed,
                skip_llm_message=SECTION_NOT_FOUND_MESSAGE,
            )

        _index, section_chunks = match
        if routed.positional_style is PositionalStyle.FIRST_SENTENCE:
            heading = find_matching_heading_line(
                section_chunks[0].chunk_text, section_name
            )
            if heading is None:
                return RetrievalResult(
                    chunks=section_chunks,
                    routed=routed,
                    skip_llm_message=SECTION_NOT_FOUND_MESSAGE,
                )
            answer = extract_first_sentence_after_heading(
                section_chunks[0].chunk_text, heading
            )
            return RetrievalResult(
                chunks=section_chunks,
                routed=routed,
                direct_answer=answer,
            )

        return RetrievalResult(chunks=section_chunks, routed=routed)

    def _retrieve_summary(
        self, document_id: uuid.UUID, routed: RoutedQuery
    ) -> RetrievalResult:
        all_chunks = self.chunks.list_by_document(document_id)
        representative = select_representative_chunks(
            all_chunks, max_chunks=SUMMARY_MAX_CHUNKS
        )
        return RetrievalResult(chunks=representative, routed=routed)

    def _retrieve_semantic(
        self,
        document_id: uuid.UUID,
        question: str,
        routed: RoutedQuery,
        top_k: int | None,
    ) -> RetrievalResult:
        top_k = top_k or get_settings().retrieval_top_k
        query_embedding = self.embedder.embed_query(question)
        scored = self.chunks.search_by_document_with_distance(
            document_id, query_embedding, top_k
        )
        if not scored:
            return RetrievalResult(chunks=[], routed=routed)

        min_similarity = get_settings().retrieval_min_similarity
        best_distance = scored[0][1]
        best_similarity = 1.0 - best_distance
        if best_similarity < min_similarity:
            return RetrievalResult(
                chunks=[],
                routed=routed,
                skip_llm_message=WEAK_EVIDENCE_MESSAGE,
            )

        return RetrievalResult(
            chunks=[chunk for chunk, _distance in scored],
            routed=routed,
        )
