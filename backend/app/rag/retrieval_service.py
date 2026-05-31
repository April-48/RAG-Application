"""Retrieve relevant chunks for a user question — always scoped to one document.

This is the "R" in RAG. Flow:
  1. route_question() classifies the question (semantic, page lookup, summary, …)
  2. I fetch chunks using metadata rules or pgvector similarity search
  3. I return a RetrievalResult that tells generation what to do next

Three possible outcomes after retrieval:
  - chunks only → pass them to the LLM
  - direct_answer set → skip the LLM, return extracted text (e.g. first sentence)
  - skip_llm_message set → return a fixed error string (page not found, weak hits)
"""

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

# How many chunks to send to the LLM for "summarize the document" questions.
SUMMARY_MAX_CHUNKS = 6


@dataclass(frozen=True)
class RetrievalResult:
    """Everything retrieval hands off to generation or ChatService.

    chunks — the text snippets to cite (and maybe send to the LLM).
    routed — which QueryMode was used, for logging and prompt context.
    direct_answer — when set, ChatService returns this text without calling the LLM.
    skip_llm_message — when set, ChatService returns this fixed message instead.
    Only one of direct_answer and skip_llm_message should be set at a time.
    """

    chunks: list[DocumentChunk]
    routed: RoutedQuery
    direct_answer: str | None = None
    skip_llm_message: str | None = None


class RetrievalService:
    """Fetch chunks for one document based on how the question was classified."""

    def __init__(self, db: Session, embedder: Embedder | None = None) -> None:
        """Wire up chunk repository and embedder for this DB session."""
        self.chunks = ChunkRepository(db)
        self.embedder = embedder or get_embedding_service()

    def retrieve(
        self, document_id: uuid.UUID, question: str, top_k: int | None = None
    ) -> RetrievalResult:
        """Main entry point — classify the question and fetch matching chunks.

        I call route_question() first, then dispatch to the right _retrieve_* helper.
        Every path ends in _finalize_result() which drops empty chunks and logs.
        """
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

    def _retrieve_document_beginning(
        self, document_id: uuid.UUID, routed: RoutedQuery
    ) -> RetrievalResult:
        """Handle "beginning of the document" style questions.

        I fetch chunk_index=0 and cut out the answer with answer_from_positional_chunk.
        No LLM needed — the answer is literally in the first chunk.
        """
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
        """Handle "end of the document" style questions.

        Same idea as _retrieve_document_beginning but I use the last chunk.
        EXCERPT style uses extract_ending_excerpt for a tail preview.
        """
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
        """Handle "what is on page N?" questions.

        If the document has no page metadata (TXT/DOCX), I fall back to semantic
        search because page numbers do not exist. If the page number is missing
        from the question, I also fall back to semantic.

        When the page exists but has no chunks, I set skip_llm_message instead
        of calling the LLM with nothing useful.
        """
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
        """Handle "tell me about the Introduction section" style questions.

        I load all chunks, find one whose text contains a matching heading,
        and return that chunk plus up to two followers for context.

        For "first sentence of X section" I try to extract the sentence right
        after the heading and set direct_answer. Other section questions go to
        the LLM with the matched chunks.
        """
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
        """Handle "summarize the document" style questions.

        I pick chunks from the start, middle, and end so the LLM sees the whole
        document spread, not just the most similar paragraph.
        """
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
        """Default path — embed the question and search pgvector within one document.

        I log every hit with distance and similarity before any threshold check.
        By default (MVP) retrieval_enforce_similarity_threshold is off, so any
        pgvector hit goes to the LLM even if similarity is low.

        When enforcement is on and the best hit is below retrieval_min_similarity,
        I return skip_llm_message instead of wasting an LLM call on weak evidence.
        """
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

    def _finalize_result(
        self,
        document_id: uuid.UUID,
        question: str,
        result: RetrievalResult,
    ) -> RetrievalResult:
        """Last step — filter junk chunks and write retrieval logs.

        When direct_answer or skip_llm_message is already set, I just log and
        return. Otherwise I run filter_usable_chunks() to drop tiny empty snippets.
        If every chunk fails the filter, I return an empty chunk list.
        """
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
