"""
Unit tests for PgVectorStore SQL parameterization and fail-closed logic.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.vector_store.pgvector_store import PgVectorStore


@pytest.mark.asyncio
class TestPgVectorStoreACL:

    async def test_empty_authorized_ids_returns_empty_list_without_db_query(self):
        """When authorized document IDs list is empty, execute is never called (fail closed)."""
        mock_session = AsyncMock(spec=AsyncSession)
        store = PgVectorStore(mock_session)

        results = await store.similarity_search(
            query_embedding=[0.1] * 384,
            authorized_document_ids=[],
            tenant_id="org_acme",
        )

        assert results == []
        mock_session.execute.assert_not_called()

    async def test_query_binds_authorized_ids_and_tenant_id_parameters(self):
        """Verify the SQL query parameters contain authorized IDs and tenant ID."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        store = PgVectorStore(mock_session)
        await store.similarity_search(
            query_embedding=[0.1] * 384,
            authorized_document_ids=["doc_1", "doc_2"],
            tenant_id="org_acme",
        )

        # Check call arguments
        assert mock_session.execute.call_count == 2  # 1 for SET LOCAL, 1 for SELECT
        second_call = mock_session.execute.call_args_list[1]
        params = second_call.args[1]

        assert "authorized_doc_ids" in params
        assert "tenant_id" in params
        assert params["tenant_id"] == "org_acme"
        assert set(params["authorized_doc_ids"]) == {"doc_1", "doc_2"}

