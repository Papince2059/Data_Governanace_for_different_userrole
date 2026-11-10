"""
Critical Test Suite: Pre-Retrieval ACL Filtering Guarantees.

Verifies:
1. When OpenFGA returns empty authorized docs, the vector store is NEVER queried.
2. When OpenFGA fails or is unreachable, the system fails closed (503 / exception), vector store NEVER called.
3. Vector store is queried with ONLY the authorized doc IDs from OpenFGA.
4. Alice cannot access Finance documents.
5. Helen can access salary records; Alice cannot.
6. Revocation takes effect immediately on subsequent calls (no stale cache).
7. Tenant isolation is enforced inside the retrieval query parameters.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.core.exceptions import AuthorizationServiceUnavailableError
from src.infrastructure.vector_store.pgvector_store import DocumentChunkResult


@pytest.mark.asyncio
class TestPreRetrievalACLFiltering:

    async def test_vector_store_never_called_when_no_authorized_docs(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """CRITICAL: If OpenFGA returns 0 authorized docs, similarity_search is NEVER called."""
        mock_fga_client.list_objects.return_value = []

        ctx = await retrieval_service.retrieve(
            query="What is the employee salary structure?",
            user_id="alice",
            tenant_id="org_acme",
        )

        # Assert: PgVectorStore was never executed
        mock_vector_store.similarity_search.assert_not_called()
        assert ctx.chunks == []
        assert ctx.authorized_doc_count == 0
        assert ctx.retrieved_chunk_count == 0

    async def test_vector_store_never_called_when_openfga_fails_closed(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """CRITICAL: When OpenFGA is unavailable, retrieval fails closed and never calls vector store."""
        mock_fga_client.list_objects.side_effect = AuthorizationServiceUnavailableError(
            "OpenFGA service unreachable"
        )

        with pytest.raises(AuthorizationServiceUnavailableError):
            await retrieval_service.retrieve(
                query="What are the leave policies?",
                user_id="alice",
                tenant_id="org_acme",
            )

        # Assert: Vector store was never called
        mock_vector_store.similarity_search.assert_not_called()

    async def test_vector_store_called_only_with_authorized_document_ids(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """Vector search receives strictly the IDs returned from OpenFGA ListObjects."""
        mock_fga_client.list_objects.return_value = [
            "document:doc_employee_handbook",
            "document:doc_leave_policy",
        ]
        mock_vector_store.similarity_search.return_value = [
            DocumentChunkResult(
                chunk_id="c1",
                document_id="doc_leave_policy",
                document_title="Leave Policy",
                chunk_index=0,
                content="Leave policy content...",
                similarity=0.88,
                tenant_id="org_acme",
            )
        ]

        ctx = await retrieval_service.retrieve(
            query="How many PTO days do I get?",
            user_id="alice",
            tenant_id="org_acme",
        )

        mock_vector_store.similarity_search.assert_called_once()
        call_kwargs = mock_vector_store.similarity_search.call_args.kwargs
        passed_ids = call_kwargs.get("authorized_document_ids")
        passed_tenant = call_kwargs.get("tenant_id")

        assert set(passed_ids) == {"doc_employee_handbook", "doc_leave_policy"}
        assert passed_tenant == "org_acme"
        assert len(ctx.chunks) == 1
        assert ctx.chunks[0].document_id == "doc_leave_policy"

    async def test_alice_cannot_query_finance_documents(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """Alice asking about Finance documents only gets her HR docs checked; finance docs excluded."""
        # OpenFGA returns only Alice's permitted HR docs
        mock_fga_client.list_objects.return_value = [
            "document:doc_employee_handbook",
            "document:doc_leave_policy",
        ]
        mock_vector_store.similarity_search.return_value = []

        ctx = await retrieval_service.retrieve(
            query="Show me the quarterly revenue and financial statements",
            user_id="alice",
            tenant_id="org_acme",
        )

        passed_ids = mock_vector_store.similarity_search.call_args.kwargs.get("authorized_document_ids")
        assert "doc_quarterly_revenue" not in passed_ids
        assert "doc_financial_statements" not in passed_ids
        assert "doc_financial_forecast" not in passed_ids

    async def test_helen_can_access_salary_records_alice_cannot(self, auth_service):
        """Helen (HR Manager) has salary access; Alice (HR Analyst) does not."""
        mock_fga = auth_service.fga

        # Mock OpenFGA responses for Alice vs Helen
        async def mock_check(user, relation, object):
            if "salary_records" in object:
                return user == "user:helen"
            return True

        mock_fga.check.side_effect = mock_check

        alice_allowed = await auth_service.can_read_document("alice", "doc_salary_records")
        helen_allowed = await auth_service.can_read_document("helen", "doc_salary_records")

        assert alice_allowed is False
        assert helen_allowed is True

    async def test_permission_revocation_invalidates_immediately(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """Revoking an OpenFGA permission denies access on the very next request."""
        # 1. Initial request: Alice has access
        mock_fga_client.list_objects.return_value = ["document:doc_employee_handbook"]
        ctx1 = await retrieval_service.retrieve("handbook rules", "alice", "org_acme")
        assert ctx1.authorized_doc_count == 1
        assert mock_vector_store.similarity_search.call_count == 1

        # 2. Revocation event occurs -> OpenFGA now returns empty list
        mock_fga_client.list_objects.return_value = []

        # 3. Subsequent request: Immediately blocked without calling vector store
        ctx2 = await retrieval_service.retrieve("handbook rules", "alice", "org_acme")
        assert ctx2.authorized_doc_count == 0
        assert ctx2.chunks == []
        # Vector store still only called once from request 1
        assert mock_vector_store.similarity_search.call_count == 1

    async def test_tenant_isolation_enforced_in_retrieval(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """Retrieval query is always scoped to user's tenant_id."""
        mock_fga_client.list_objects.return_value = ["document:doc_1"]
        await retrieval_service.retrieve("query text", "alice", "org_acme")

        call_kwargs = mock_vector_store.similarity_search.call_args.kwargs
        assert call_kwargs.get("tenant_id") == "org_acme"

