"""RAG helper unit tests — splitter, prompt builder, loader, source shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import UnsupportedFileTypeError
from app.models.chunk import DocumentChunk
from app.rag.loader import extract_pages
from app.rag.pdf_parser import PageText
from app.rag.prompt_builder import build_messages
from app.rag.text_splitter import split_pages, split_text
from app.services.chat_service import _chunk_to_source


def test_text_splitter_creates_chunks_with_metadata() -> None:
    long_text = "word " * 400
    pages = [PageText(page_number=2, text=long_text)]
    chunks = split_pages(pages, chunk_size=100, overlap=20)

    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 2
    assert chunks[0].chunk_text
    assert all(c.chunk_index == i for i, c in enumerate(chunks))


def test_split_text_returns_empty_for_blank_input() -> None:
    assert split_text("   ") == []


def test_prompt_builder_includes_context_and_question() -> None:
    import uuid

    chunks = [
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            chunk_text="The refund policy allows returns within 30 days.",
            embedding=None,
        )
    ]
    question = "What is the refund window?"
    messages = build_messages(question, chunks)

    assert messages[0]["role"] == "system"
    user_content = messages[1]["content"]
    assert "Context:" in user_content
    assert "refund policy" in user_content
    assert f"Question: {question}" in user_content


def test_loader_rejects_unsupported_extension() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        extract_pages("/tmp/fake.doc", "doc")


def test_source_object_shape_is_consistent() -> None:
    import uuid

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=3,
        page_number=5,
        chunk_text="Sample cited text.",
        embedding=None,
    )
    source = _chunk_to_source(chunk)
    assert set(source.keys()) == {"chunk_index", "page_number", "chunk_text"}
    assert source["chunk_index"] == 3
    assert source["page_number"] == 5
    assert source["chunk_text"] == "Sample cited text."


def test_txt_loader_reads_plain_text(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("Hello from a text file.", encoding="utf-8")
    pages = extract_pages(path, "txt")
    assert len(pages) == 1
    assert "Hello from a text file." in pages[0].text
