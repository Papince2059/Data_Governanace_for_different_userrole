"""
Pytest configuration and shared fixtures for Enterprise Data Governance tests.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure backend/ is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Set test environment variables before importing app modules
os.environ["APP_ENV"] = "testing"
os.environ["JWT_SECRET_KEY"] = "super-secret-test-key-minimum-32-characters-long"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["LLM_PROVIDER"] = "mock"

from src.core.config import get_settings
from src.core.security import create_access_token
from src.infrastructure.database.connection import Base
from src.infrastructure.embeddings.local_embedder import LocalEmbedder
from src.infrastructure.openfga.client import OpenFGAClient
from src.infrastructure.vector_store.pgvector_store import (
    DocumentChunkResult,
    PgVectorStore,
)
from src.services.authorization_service import AuthorizationService
from src.services.retrieval_service import RetrievalService


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_fga_client():
    """Mock OpenFGA client for fast, deterministic unit and authorization testing."""
    client = AsyncMock(spec=OpenFGAClient)
    client.check = AsyncMock(return_value=False)
    client.list_objects = AsyncMock(return_value=[])
    client.write_tuple = AsyncMock(return_value=None)
    client.delete_tuple = AsyncMock(return_value=None)
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_embedder():
    """Mock embedder returning fixed 384-dimensional vector."""
    embedder = AsyncMock(spec=LocalEmbedder)
    embedder.aembed_text = AsyncMock(return_value=[0.05] * 384)
    embedder.aembed_batch = AsyncMock(return_value=[[0.05] * 384])
    embedder.embed_text = MagicMock(return_value=[0.05] * 384)
    return embedder


@pytest.fixture
def mock_vector_store():
    """Mock PgVector store for verifying pre-retrieval query parameters."""
    store = AsyncMock(spec=PgVectorStore)
    store.similarity_search = AsyncMock(return_value=[])
    return store


@pytest.fixture
def auth_service(mock_fga_client) -> AuthorizationService:
    return AuthorizationService(fga_client=mock_fga_client)


@pytest.fixture
def retrieval_service(auth_service, mock_embedder, mock_vector_store) -> RetrievalService:
    return RetrievalService(
        authorization_service=auth_service,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
    )


def make_jwt(user_id: str, tenant_id: str = "org_acme", is_admin: bool = False, email: str = "") -> str:
    """Helper to generate valid JWTs for testing."""
    return create_access_token(
        {
            "sub": user_id,
            "email": email or f"{user_id}@acme.com",
            "tenant_id": tenant_id,
            "is_admin": is_admin,
        },
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture
def alice_token() -> str:
    return make_jwt("alice", "org_acme", is_admin=False, email="alice@acme.com")


@pytest.fixture
def bob_token() -> str:
    return make_jwt("bob", "org_acme", is_admin=False, email="bob@acme.com")


@pytest.fixture
def admin_token() -> str:
    return make_jwt("admin", "org_acme", is_admin=True, email="admin@acme.com")

