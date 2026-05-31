"""Retrieve relevant chunks — hybrid router picks strategy, always one document."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chunk import DocumentChunk
from app.rag.embedding_service import Embedder, get_embedding_service
from app.rag.prompt_builder import filter_usable_chunks
from app.rag.rag_logging import CHUNK_LOG_PREVIEW_CHARS, log_retrieved_chunks
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

logger = logging.getLogger("app.rag.retrieval_service")

SUMMARY_MAX_CHUNKS = 6


# Chunks plus optional direct answer or a no-LLM fallback message.
@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[DocumentChunk]
    routed: RoutedQuery
    direct_answer: str | None = None
    skip_llm_message: str | None = None


# I route the question, then fetch chunks via metadata rules or pgvector search.
class RetrievalService:

    # Wire chunk repo and embedder for retrieval.
    def __init__(self, db: Session, embedder: Embedder | None = None) -> None:
        self.chunks = ChunkRepository(db)
        self.embedder = embedder or get_embedding_service()

    # Classify the question and return chunks with routing metadata.
    def retrieve(
        self, document_id: uuid.UUID, question: str, top_k: int | None = None
    ) -> RetrievalResult:
        routed = route_question(question)
        logger.info(
            "Retrieval start document_id=%s route=%s question=%r",
            document_id,
            routed.mode.value,
            question[:120],
        )

        if routed.mode is QueryMode.DOCUMENT_BEGINNING:
            result = self._retrieve_document_beginning(document_id, routed)
        elif routed.mode is QueryMode.DOCUMENT_ENDING:
            result = self._retrieve_document_ending(document_id, routed)
        elif routed.mode is QueryMode.PAGE_LOOKUP:
            result = self._retrieve_page_lookup(document_id, question, routed, top_k)
        elif routed.mode is QueryMode.SECTION_LOOKUP:
            result = self._retrieve_section_lookup(document_id, routed)
        elif routed.mode is QueryMode.WHOLE_DOCUMENT_SUMMARY:
            result = self._retrieve_summary(document_id, routed)
        else:
            result = self._retrieve_semantic(document_id, question, routed, top_k)

        return self._finalize_result(document_id, question, result)

    # Fetch the first chunk and build a direct positional answer when possible.
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

    # Fetch the last chunk and build a direct positional answer when possible.
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

    # Fetch chunks for a specific page number, or fall back to semantic search.
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

    # Fetch chunks for a named section and maybe return a direct first sentence.
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

    # Pick representative chunks across the document for summary-style questions.
    def _retrieve_summary(
        self, document_id: uuid.UUID, routed: RoutedQuery
    ) -> RetrievalResult:
        all_chunks = self.chunks.list_by_document(document_id)
        representative = select_representative_chunks(
            all_chunks, max_chunks=SUMMARY_MAX_CHUNKS
        )
        return RetrievalResult(chunks=representative, routed=routed)

    # Embed the question and run pgvector similarity search within one document.
    # I log top-k scores before any threshold decision.
    # With enforcement off (MVP default), any pgvector hit goes to the LLM.
    def _retrieve_semantic(
        self,
        document_id: uuid.UUID,
        question: str,
        routed: RoutedQuery,
        top_k: int | None,
    ) -> RetrievalResult:
        settings = get_settings()
        top_k = top_k or settings.retrieval_top_k
        query_embedding = self.embedder.embed_query(question)
        scored = self.chunks.search_by_document_with_distance(
            document_id, query_embedding, top_k
        )
        if not scored:
            logger.info(
                "Semantic retrieval: no chunks in DB document_id=%s question=%r",
                document_id,
                question[:120],
            )
            return RetrievalResult(chunks=[], routed=routed)

        score_lines: list[str] = []
        for chunk, distance in scored:
            similarity = 1.0 - distance
            preview = chunk.chunk_text.replace("\n", " ")[:CHUNK_LOG_PREVIEW_CHARS]
            score_lines.append(
                f"id={chunk.id} chunk_index={chunk.chunk_index} page={chunk.page_number} "
                f"distance={distance:.4f} similarity={similarity:.4f} preview={preview!r}"
            )

        best_distance = scored[0][1]
        best_similarity = 1.0 - best_distance
        logger.info(
            "Semantic retrieval document_id=%s top_k=%s threshold=%.3f "
            "enforce_threshold=%s best_similarity=%.4f embedder=%s question=%r\n  %s",
            document_id,
            top_k,
            settings.retrieval_min_similarity,
            settings.retrieval_enforce_similarity_threshold,
            best_similarity,
            type(self.embedder).__name__,
            question[:120],
            "\n  ".join(score_lines),
        )

        if (
            settings.retrieval_enforce_similarity_threshold
            and best_similarity < settings.retrieval_min_similarity
        ):
            logger.info(
                "Semantic retrieval: pre-LLM filter dropped weak hits "
                "(best_similarity=%.4f < threshold=%.3f)",
                best_similarity,
                settings.retrieval_min_similarity,
            )
            return RetrievalResult(
                chunks=[],
                routed=routed,
                skip_llm_message=WEAK_EVIDENCE_MESSAGE,
            )

        logger.info(
            "Semantic retrieval: passing %s chunk(s) to LLM (best_similarity=%.4f)",
            len(scored),
            best_similarity,
        )
        return RetrievalResult(
            chunks=[chunk for chunk, _distance in scored],
            routed=routed,
        )

    # Drop empty/unusable chunks and log the final retrieval payload.
    def _finalize_result(
        self,
        document_id: uuid.UUID,
        question: str,
        result: RetrievalResult,
    ) -> RetrievalResult:
        if result.skip_llm_message or result.direct_answer is not None:
            log_retrieved_chunks(
                document_id=document_id,
                question=question,
                route=result.routed.mode.value,
                chunks=result.chunks,
            )
            return result

        usable = filter_usable_chunks(result.chunks)
        if result.chunks and not usable:
            logger.info(
                "Retrieval document_id=%s route=%s: all %s chunk(s) failed usable filter",
                document_id,
                result.routed.mode.value,
                len(result.chunks),
            )
            return RetrievalResult(chunks=[], routed=result.routed)

        if len(usable) != len(result.chunks):
            result = RetrievalResult(chunks=usable, routed=result.routed)

        log_retrieved_chunks(
            document_id=document_id,
            question=question,
            route=result.routed.mode.value,
            chunks=result.chunks,
        )
        return result

