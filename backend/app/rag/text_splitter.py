"""Split extracted pages into overlapping text chunks for embedding.

RAG works on small pieces, not whole documents. Default window is 1000
characters with 200 overlap so sentences at chunk boundaries are not lost.

Example with chunk_size=1000 and overlap=200:
  chunk 0: chars 0–999
  chunk 1: chars 800–1799   (200 chars overlap with chunk 0)
  chunk 2: chars 1600–2599
"""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.pdf_parser import PageText

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200


@dataclass
class Chunk:
    """In-memory chunk before I save it to the document_chunks table.

    chunk_index is global across the whole document (0, 1, 2, …).
    page_number comes from the source page when PDF gave us one.
    embedding starts as None and gets filled in during ingestion.
    """

    chunk_index: int
    chunk_text: str
    page_number: int | None
    embedding: list[float] | None = None


def split_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Split one text block into overlapping character windows.

    I slide a window of chunk_size chars forward by (chunk_size - overlap) each
    step. Empty input returns []. If overlap is too big I clamp it to chunk_size/4
    so the loop always makes progress.
    """
    text = text.strip()
    if not text:
        return []
    if overlap >= chunk_size:
        overlap = chunk_size // 4
    step = max(1, chunk_size - overlap)

    pieces: list[str] = []
    for start in range(0, len(text), step):
        piece = text[start : start + chunk_size].strip()
        if piece:
            pieces.append(piece)
        if start + chunk_size >= len(text):
            break
    return pieces


def split_pages(
    pages: list[PageText],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Split all pages into one flat list of Chunk objects.

    I walk pages in order and assign chunk_index 0, 1, 2, … across the whole
    document. Each piece keeps the page_number from the page it came from.
    This list goes to the embedder, then ChunkRepository.create_many().
    """
    chunks: list[Chunk] = []
    index = 0
    for page in pages:
        for piece in split_text(page.text, chunk_size=chunk_size, overlap=overlap):
            chunks.append(
                Chunk(
                    chunk_index=index,
                    chunk_text=piece,
                    page_number=page.page_number,
                )
            )
            index += 1
    return chunks
