"""
Unit tests for the AuthorizationService and OpenFGA client integration.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from src.core.exceptions import AuthorizationError, AuthorizationServiceUnavailableError
from src.services.authorization_service import AuthorizationService


@pytest.mark.asyncio
class TestAuthorizationService:

    async def test_can_read_document_delegates_to_fga_check(self, mock_fga_client):
        mock_fga_client.check.return_value = True
        auth = AuthorizationService(mock_fga_client)

        allowed = await auth.can_read_document("alice", "doc_employee_handbook")

        assert allowed is True
        mock_fga_client.check.assert_called_once_with(
            user="user:alice",
            relation="can_read",
            object="document:doc_employee_handbook",
        )

    async def test_can_read_document_returns_false_when_denied(self, mock_fga_client):
        mock_fga_client.check.return_value = False
        auth = AuthorizationService(mock_fga_client)

        allowed = await auth.can_read_document("alice", "doc_salary_records")
        assert allowed is False

    async def test_require_document_read_raises_authorization_error(self, mock_fga_client):
        mock_fga_client.check.return_value = False
        auth = AuthorizationService(mock_fga_client)

        with pytest.raises(AuthorizationError) as exc_info:
            await auth.require_document_read("alice", "doc_salary_records")

        assert "not authorized to read document" in str(exc_info.value.message)
        assert exc_info.value.status_code == 403

    async def test_get_accessible_document_ids_strips_prefix(self, mock_fga_client):
        mock_fga_client.list_objects.return_value = [
            "document:doc_leave_policy",
            "document:doc_handbook",
        ]
        auth = AuthorizationService(mock_fga_client)

        doc_ids = await auth.get_accessible_document_ids("alice")
        assert doc_ids == ["doc_leave_policy", "doc_handbook"]

    async def test_grant_document_permission_calls_write_tuple(self, mock_fga_client):
        auth = AuthorizationService(mock_fga_client)
        await auth.grant_document_permission("group:hr#member", "viewer", "doc_leave_policy")

        mock_fga_client.write_tuple.assert_called_once_with(
            user="group:hr#member",
            relation="viewer",
            object="document:doc_leave_policy",
        )

    async def test_revoke_document_permission_calls_delete_tuple(self, mock_fga_client):
        auth = AuthorizationService(mock_fga_client)
        await auth.revoke_document_permission("user:alice", "viewer", "doc_leave_policy")

        mock_fga_client.delete_tuple.assert_called_once_with(
            user="user:alice",
            relation="viewer",
            object="document:doc_leave_policy",
        )

