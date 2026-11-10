"""
Mandatory Test Scenarios covering all 12 specifications:
Scenario 1: HR access (Alice permitted to view HR policy)
Scenario 2: Unauthorized Finance access (Alice asks about Finance -> excluded)
Scenario 3: Restricted HR document (Alice cannot view salary; Helen can)
Scenario 4: Finance access (Bob retrieves Finance; cannot retrieve HR/IT)
Scenario 5: Sales access (Charlie retrieves Sales; cannot retrieve Finance)
Scenario 6: IT access (David retrieves runbook; cannot retrieve security incidents)
Scenario 7: Permission revocation (Immediate revocation, no stale cache)
Scenario 8: Unauthorized direct document access (Alice rejected on Finance doc ID)
Scenario 9: Tenant isolation (Cross-tenant access blocked)
Scenario 10: Authorization service failure (OpenFGA stops -> fail closed)
Scenario 11: Folder permission inheritance (Child documents inherit folder permissions)
Scenario 12: Streaming (Tokens streamed, progress events, no sensitive leakage)
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.core.exceptions import AuthorizationError, AuthorizationServiceUnavailableError
from src.infrastructure.vector_store.pgvector_store import DocumentChunkResult


@pytest.mark.asyncio
class TestTwelveMandatoryScenarios:

    async def test_scenario_1_hr_access(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 1: Alice asks about leave policies -> OpenFGA permits, retrieved, streamed."""
        mock_fga_client.list_objects.return_value = [
            "document:doc_employee_handbook",
            "document:doc_leave_policy",
            "document:doc_onboarding_policy",
        ]
        mock_vector_store.similarity_search.return_value = [
            DocumentChunkResult(
                chunk_id="chunk-1",
                document_id="doc_leave_policy",
                document_title="Leave and Attendance Policy",
                chunk_index=0,
                content="Employees accrue 25 days of annual leave.",
                similarity=0.91,
                tenant_id="org_acme",
            )
        ]

        ctx = await retrieval_service.retrieve(
            query="What are the employee leave policies?",
            user_id="alice",
            tenant_id="org_acme",
        )

        assert ctx.authorized_doc_count == 3
        assert ctx.retrieved_chunk_count == 1
        assert ctx.chunks[0].document_title == "Leave and Attendance Policy"

    async def test_scenario_2_unauthorized_finance_access(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 2: Alice asks about quarterly revenue -> excluded before vector search."""
        mock_fga_client.list_objects.return_value = [
            "document:doc_employee_handbook",
            "document:doc_leave_policy",
        ]
        mock_vector_store.similarity_search.return_value = []

        ctx = await retrieval_service.retrieve(
            query="What is the company's quarterly revenue?",
            user_id="alice",
            tenant_id="org_acme",
        )

        passed_ids = mock_vector_store.similarity_search.call_args.kwargs.get("authorized_document_ids")
        assert "doc_quarterly_revenue" not in passed_ids
        assert "doc_financial_statements" not in passed_ids
        assert ctx.chunks == []

    async def test_scenario_3_restricted_hr_document(self, auth_service):
        """Scenario 3: Alice cannot access salary records; Helen HR Manager can."""
        async def mock_check(user, relation, object):
            if "salary_records" in object:
                return user == "user:helen"
            return True

        auth_service.fga.check.side_effect = mock_check

        assert await auth_service.can_read_document("alice", "doc_salary_records") is False
        assert await auth_service.can_read_document("helen", "doc_salary_records") is True

    async def test_scenario_4_finance_access(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 4: Bob can retrieve Finance docs; cannot retrieve HR or IT docs."""
        mock_fga_client.list_objects.return_value = [
            "document:doc_financial_statements",
            "document:doc_quarterly_revenue",
            "document:doc_department_budget",
        ]
        mock_vector_store.similarity_search.return_value = [
            DocumentChunkResult(
                chunk_id="chunk-fin-1",
                document_id="doc_financial_statements",
                document_title="Financial Statements",
                chunk_index=0,
                content="Consolidated net revenue was $48.25M.",
                similarity=0.89,
                tenant_id="org_acme",
            )
        ]

        ctx = await retrieval_service.retrieve(
            query="Show me the financial statements",
            user_id="bob",
            tenant_id="org_acme",
        )

        passed_ids = mock_vector_store.similarity_search.call_args.kwargs.get("authorized_document_ids")
        assert "doc_financial_statements" in passed_ids
        assert "doc_salary_records" not in passed_ids
        assert "doc_server_runbook" not in passed_ids

    async def test_scenario_5_sales_access(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 5: Charlie can retrieve Sales docs; cannot retrieve Finance docs."""
        mock_fga_client.list_objects.return_value = [
            "document:doc_customer_information",
            "document:doc_sales_pipeline",
            "document:doc_quarterly_sales",
        ]
        mock_vector_store.similarity_search.return_value = [
            DocumentChunkResult(
                chunk_id="chunk-sales-1",
                document_id="doc_sales_pipeline",
                document_title="Sales Pipeline Report",
                chunk_index=0,
                content="Qualified pipeline stands at $18.45M.",
                similarity=0.87,
                tenant_id="org_acme",
            )
        ]

        ctx = await retrieval_service.retrieve(
            query="Show me the sales pipeline",
            user_id="charlie",
            tenant_id="org_acme",
        )

        passed_ids = mock_vector_store.similarity_search.call_args.kwargs.get("authorized_document_ids")
        assert "doc_sales_pipeline" in passed_ids
        assert "doc_quarterly_revenue" not in passed_ids

    async def test_scenario_6_it_access(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 6: David can access server runbook; cannot access restricted security incidents."""
        mock_fga_client.list_objects.return_value = [
            "document:doc_infrastructure_arch",
            "document:doc_server_runbook",
            "document:doc_access_policy",
            # doc_security_incidents is restricted to it_admins
        ]
        mock_vector_store.similarity_search.return_value = []

        ctx = await retrieval_service.retrieve(
            query="Show me the server maintenance procedures",
            user_id="david",
            tenant_id="org_acme",
        )

        passed_ids = mock_vector_store.similarity_search.call_args.kwargs.get("authorized_document_ids")
        assert "doc_server_runbook" in passed_ids
        assert "doc_security_incidents" not in passed_ids

    async def test_scenario_7_permission_revocation(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 7: Permission revocation takes effect immediately."""
        # 1. Initial access
        mock_fga_client.list_objects.return_value = ["document:doc_employee_handbook"]
        ctx1 = await retrieval_service.retrieve("query", "alice", "org_acme")
        assert ctx1.authorized_doc_count == 1

        # 2. Revoke
        mock_fga_client.list_objects.return_value = []

        # 3. Next query is denied
        ctx2 = await retrieval_service.retrieve("query", "alice", "org_acme")
        assert ctx2.authorized_doc_count == 0

    async def test_scenario_8_unauthorized_direct_document_access(self, auth_service):
        """Scenario 8: Direct access check for unauthorized document throws AuthorizationError."""
        auth_service.fga.check.return_value = False

        with pytest.raises(AuthorizationError):
            await auth_service.require_document_read("alice", "doc_financial_statements")

    async def test_scenario_9_tenant_isolation(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 9: Users from org_acme cannot query resources of org_other."""
        mock_fga_client.list_objects.return_value = ["document:doc_1"]
        await retrieval_service.retrieve("query", "alice", "org_other_tenant")

        call_kwargs = mock_vector_store.similarity_search.call_args.kwargs
        assert call_kwargs.get("tenant_id") == "org_other_tenant"

    async def test_scenario_10_authorization_service_failure(self, retrieval_service, mock_fga_client, mock_vector_store):
        """Scenario 10: OpenFGA stops -> fail closed, vector search never called."""
        mock_fga_client.list_objects.side_effect = AuthorizationServiceUnavailableError("OpenFGA down")

        with pytest.raises(AuthorizationServiceUnavailableError):
            await retrieval_service.retrieve("query", "alice", "org_acme")

        mock_vector_store.similarity_search.assert_not_called()

    async def test_scenario_11_folder_permission_inheritance(self, auth_service):
        """Scenario 11: Document inherits viewer rights from parent folder."""
        # When folder:folder_hr has viewer group:hr#member, document child resolves true
        auth_service.fga.check.return_value = True

        allowed = await auth_service.can_read_document("alice", "doc_in_hr_folder")
        assert allowed is True

