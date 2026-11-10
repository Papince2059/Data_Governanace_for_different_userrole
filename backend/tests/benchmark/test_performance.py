"""
Performance benchmark tests measuring real local latencies.
"""
from __future__ import annotations

import time
import pytest
from unittest.mock import AsyncMock

from src.infrastructure.embeddings.local_embedder import LocalEmbedder
from src.services.authorization_service import AuthorizationService


@pytest.mark.asyncio
class TestPerformanceBenchmarks:

    async def test_local_embedding_latency(self):
        """Measure real local embedding latency with sentence-transformers/all-MiniLM-L6-v2."""
        embedder = LocalEmbedder()
        sample_text = "What is the policy for annual vacation leave and paid time off?"

        # Warmup
        embedder.embed_text("warmup")

        t0 = time.perf_counter()
        vec = embedder.embed_text(sample_text)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert len(vec) == 384
        # Single inference locally should comfortably be under 250ms
        assert elapsed_ms < 500.0
        print(f"\n[BENCHMARK] Local MiniLM Embedding: {elapsed_ms:.2f} ms")

    async def test_authorization_service_call_overhead(self, mock_fga_client):
        """Measure AuthorizationService in-memory dispatch overhead."""
        mock_fga_client.list_objects.return_value = ["document:doc_1", "document:doc_2"]
        auth = AuthorizationService(mock_fga_client)

        t0 = time.perf_counter()
        for _ in range(50):
            await auth.get_accessible_document_ids("alice")
        avg_ms = ((time.perf_counter() - t0) / 50.0) * 1000.0

        assert avg_ms < 5.0
        print(f"[BENCHMARK] Auth Service Dispatch Overhead: {avg_ms:.3f} ms / call")

