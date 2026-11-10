"""
Integration test suite for FastAPI REST endpoints.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from tests.conftest import make_jwt


@pytest.mark.asyncio
class TestAPIEndpoints:

    async def test_health_live_endpoint(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_unauthenticated_requests_return_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/me")
            assert resp.status_code == 401

            resp2 = await client.get("/api/v1/documents")
            assert resp2.status_code == 401

            resp3 = await client.post("/api/v1/permissions/grant", json={})
            assert resp3.status_code == 401

    async def test_admin_route_forbidden_for_regular_user(self):
        import uuid
        from unittest.mock import MagicMock
        from src.api.v1.auth import get_current_user
        from src.infrastructure.database.models import UserRole

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.role = UserRole.MEMBER
        mock_user.tenant_id = uuid.uuid4()

        token = make_jwt(user_id="alice", tenant_id="org_acme", is_admin=False)
        headers = {"Authorization": f"Bearer {token}"}

        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/permissions/grant",
                    headers=headers,
                    json={
                        "user_or_group": "user:bob",
                        "relation": "viewer",
                        "resource_type": "document",
                        "resource_id": "doc_salary_records",
                    },
                )
                # Regular user cannot grant permissions
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user, None)

