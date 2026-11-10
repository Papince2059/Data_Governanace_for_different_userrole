"""
Local embedding generation using sentence-transformers.
No API key required. Model runs entirely locally.
Default model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
"""
from __future__ import annotations

import asyncio
from typing import Optional
from sentence_transformers import SentenceTransformer

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class LocalEmbedder:
    """
    Generates embeddings using sentence-transformers/all-MiniLM-L6-v2.
    Dimension: 384. Runs entirely locally.
    """
    _model: Optional[SentenceTransformer] = None

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    def _get_model(self) -> SentenceTransformer:
        if LocalEmbedder._model is None:
            logger.info("loading_embedding_model", model=self.model_name)
            LocalEmbedder._model = SentenceTransformer(self.model_name)
        return LocalEmbedder._model

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns list of 384 floats."""
        model = self._get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch. Returns list of embeddings."""
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    async def aembed_text(self, text: str) -> list[float]:
        """Async non-blocking wrapper for single text embedding."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.embed_text, text)

    async def aembed_batch(self, texts: list[str]) -> list[list[float]]:
        """Async non-blocking wrapper for batch text embedding."""
        if not texts:
            return []
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.embed_batch, texts)

