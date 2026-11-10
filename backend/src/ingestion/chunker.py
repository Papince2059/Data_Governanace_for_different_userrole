"""
Document chunker — splits text into semantically coherent overlapping chunks.
Default: 500 words with 50-word overlap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    chunk_index: int
    content: str
    start_char: int
    end_char: int
    word_count: int


class DocumentChunker:
    """
    Splits text documents into overlapping word-based windows for vector embeddings.
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> list[DocumentChunk]:
        """Split string into sequential chunks with overlap."""
        # Normalize excessive line breaks
        cleaned_text = re.sub(r"\n{3,}", "\n\n", text.strip())
        words = cleaned_text.split()

        if not words:
            return []

        chunks: list[DocumentChunk] = []
        start = 0
        chunk_index = 0

        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            content = " ".join(chunk_words)

            # Calculate char offsets in normalized text
            start_char = len(" ".join(words[:start])) + (1 if start > 0 else 0)
            end_char = start_char + len(content)

            chunks.append(
                DocumentChunk(
                    chunk_index=chunk_index,
                    content=content,
                    start_char=start_char,
                    end_char=end_char,
                    word_count=len(chunk_words),
                )
            )

            chunk_index += 1
            if end == len(words):
                break

            # Slide window forward by (chunk_size - overlap)
            start += max(1, self.chunk_size - self.overlap)

        return chunks

