"""
Unit tests for the DocumentChunker.
"""
from __future__ import annotations

import pytest
from src.ingestion.chunker import DocumentChunker


class TestDocumentChunker:

    def test_empty_string_returns_no_chunks(self):
        chunker = DocumentChunker()
        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   \n\n   ") == []

    def test_short_document_creates_single_chunk(self):
        chunker = DocumentChunker(chunk_size=100, overlap=10)
        text = "This is a brief corporate policy document covering employee responsibilities."
        chunks = chunker.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].word_count == 10
        assert chunks[0].content == text

    def test_long_document_creates_multiple_overlapping_chunks(self):
        chunker = DocumentChunker(chunk_size=50, overlap=10)
        # 120 words
        words = [f"word{i}" for i in range(120)]
        text = " ".join(words)
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 3
        # Verify indices are sequential
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

        # Verify overlap: end of chunk 0 should equal start of chunk 1
        chunk_0_words = chunks[0].content.split()
        chunk_1_words = chunks[1].content.split()
        assert chunk_0_words[-10:] == chunk_1_words[:10]

