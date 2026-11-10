"""
Retrieval Service — Secure Pre-Retrieval ACL Filtering Pipeline.

SECURITY INVARIANTS:
1. OpenFGA ListObjects determines authorized document IDs BEFORE querying vector database.
2. If OpenFGA is unavailable, fail closed (raise AuthorizationServiceUnavailableError).
3. If authorized document list is empty, return empty context immediately (never search).
4. Authorized IDs and tenant ID are applied directly inside the SQL query WHERE clause.
5. No post-retrieval filtering; unauthorized documents never leave PostgreSQL.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from src.core.exceptions import AuthorizationServiceUnavailableError
from src.core.logging import get_logger
from src.infrastructure.embeddings.local_embedder import LocalEmbedder
from src.infrastructure.vector_store.pgvector_store import (
    DocumentChunkResult,
    PgVectorStore,
)
from src.services.authorization_service import AuthorizationService

logger = get_logger(__name__)


@dataclass
class RetrievalContext:
    """The verified result of a pre-retrieval filtered semantic search."""
    chunks: list[DocumentChunkResult]
    authorized_document_ids: list[str]
    retrieval_latency_ms: float
    authorization_latency_ms: float
    embedding_latency_ms: float
    authorized_doc_count: int
    retrieved_chunk_count: int
    query: str
    user_id: str
    tenant_id: str


class RetrievalService:
    """
    Orchestrates pre-retrieval authorization checks and pgvector similarity search.
    """

    def __init__(
        self,
        authorization_service: AuthorizationService,
        embedder: LocalEmbedder,
        vector_store: PgVectorStore,
    ) -> None:
        self.auth_service = authorization_service
        self.embedder = embedder
        self.vector_store = vector_store

    async def retrieve(
        self,
        query: str,
        user_id: str,
        tenant_id: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> RetrievalContext:
        """
        Execute the pre-retrieval ACL filtered RAG pipeline:
        1. OpenFGA ListObjects -> get authorized document IDs.
        2. If empty -> fail closed, return 0 chunks immediately.
        3. Embed query text locally.
        4. Vector search in PostgreSQL restricted by (id IN authorized_ids AND tenant_id = tenant_id).
        5. Return authorized chunks.
        """
        from src.core.config import get_settings
        settings = get_settings()
        effective_top_k = top_k if top_k is not None else settings.RETRIEVAL_TOP_K
        effective_threshold = similarity_threshold if similarity_threshold is not None else settings.RETRIEVAL_SIMILARITY_THRESHOLD
        logger.info("secure_retrieval_started", user_id=user_id, tenant_id=tenant_id)

        # Step 1: Pre-retrieval ACL check via OpenFGA
        auth_start = time.perf_counter()
        try:
            authorized_doc_ids = await self.auth_service.get_accessible_document_ids(user_id)
        except AuthorizationServiceUnavailableError:
            logger.error("openfga_unavailable_failing_closed", user_id=user_id)
            raise
        except Exception as e:
            logger.error("authorization_check_failed", user_id=user_id, error=str(e))
            raise AuthorizationServiceUnavailableError(
                f"Authorization evaluation failed: {e}"
            )
        auth_latency_ms = (time.perf_counter() - auth_start) * 1000.0

        logger.info(
            "acl_filtering_completed",
            user_id=user_id,
            authorized_doc_count=len(authorized_doc_ids),
            auth_latency_ms=round(auth_latency_ms, 2),
        )

        # Step 2: Fail-closed if no documents are authorized
        if not authorized_doc_ids:
            logger.info("zero_authorized_documents_early_return", user_id=user_id)
            return RetrievalContext(
                chunks=[],
                authorized_document_ids=[],
                retrieval_latency_ms=0.0,
                authorization_latency_ms=auth_latency_ms,
                embedding_latency_ms=0.0,
                authorized_doc_count=0,
                retrieved_chunk_count=0,
                query=query,
                user_id=user_id,
                tenant_id=tenant_id,
            )

        # Step 3: Generate query embedding locally (MiniLM 384 dimensions)
        emb_start = time.perf_counter()
        query_embedding = await self.embedder.aembed_text(query)
        emb_latency_ms = (time.perf_counter() - emb_start) * 1000.0

        # Step 4: Semantic vector search inside PostgreSQL with ACL pre-filter in SQL
        retr_start = time.perf_counter()
        chunks = await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            authorized_document_ids=authorized_doc_ids,
            tenant_id=tenant_id,
            top_k=effective_top_k,
            similarity_threshold=effective_threshold,
        )
        retr_latency_ms = (time.perf_counter() - retr_start) * 1000.0

        logger.info(
            "secure_retrieval_completed",
            user_id=user_id,
            authorized_docs=len(authorized_doc_ids),
            chunks_retrieved=len(chunks),
            auth_latency_ms=round(auth_latency_ms, 2),
            emb_latency_ms=round(emb_latency_ms, 2),
            retrieval_latency_ms=round(retr_latency_ms, 2),
        )

        return RetrievalContext(
            chunks=chunks,
            authorized_document_ids=authorized_doc_ids,
            retrieval_latency_ms=retr_latency_ms,
            authorization_latency_ms=auth_latency_ms,
            embedding_latency_ms=emb_latency_ms,
            authorized_doc_count=len(authorized_doc_ids),
            retrieved_chunk_count=len(chunks),
            query=query,
            user_id=user_id,
            tenant_id=tenant_id,
        )

