"""Turn extracted pages into overlapping chunks (default 1000 chars, 200 overlap)."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.pdf_parser import PageText

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200


# In-memory chunk before I save it to document_chunks (text + optional embedding).
@dataclass
class Chunk:
    chunk_index: int
    chunk_text: str
    page_number: int | None
    embedding: list[float] | None = None


# Split one text block into overlapping character windows.
# Output: list of non-empty string pieces; empty input yields [].
def split_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
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


# Split pages into a flat, globally-indexed list of Chunk objects.
def split_pages(
    pages: list[PageText],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
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
