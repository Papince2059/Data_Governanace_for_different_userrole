"""
Tests for Streaming RAG Chat Service (Scenario 12).
Verifies:
1. Event sequence: conversation.started -> authorization.completed -> retrieval.completed -> generation.started -> token -> citation -> generation.completed
2. Fail-closed error event when OpenFGA is unavailable
3. No leakage of internal prompts, permission tuples, passwords, or filesystem paths.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock

from src.core.exceptions import AuthorizationServiceUnavailableError
from src.infrastructure.llm.mock_adapter import MockLLMProvider
from src.infrastructure.vector_store.pgvector_store import DocumentChunkResult
from src.services.chat_service import ChatService


async def collect_events(generator) -> list[dict]:
    """Parse raw SSE text into structured events."""
    raw = ""
    async for item in generator:
        raw += item

    events = []
    current_event = None
    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event = line.replace("event: ", "").strip()
        elif line.startswith("data: ") and current_event:
            try:
                data = json.loads(line.replace("data: ", "").strip())
                events.append({"event": current_event, "data": data})
            except json.JSONDecodeError:
                pass
            current_event = None
    return events


@pytest.mark.asyncio
class TestStreamingRAG:

    async def test_full_successful_streaming_sequence(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """Verify the exact sequence of SSE events emitted during successful retrieval."""
        mock_fga_client.list_objects.return_value = ["document:doc_leave_policy"]
        mock_vector_store.similarity_search.return_value = [
            DocumentChunkResult(
                chunk_id="c1",
                document_id="doc_leave_policy",
                document_title="Leave and Attendance Policy",
                chunk_index=0,
                content="Employees receive 25 days of paid time off.",
                similarity=0.92,
                tenant_id="org_acme",
            )
        ]

        chat_service = ChatService(
            retrieval_service=retrieval_service,
            llm_provider=MockLLMProvider(),
        )

        events = await collect_events(
            chat_service.stream_response(
                question="What is the leave policy?",
                user_id="alice",
                tenant_id="org_acme",
            )
        )

        event_names = [e["event"] for e in events]
        assert event_names[0] == "conversation.started"
        assert event_names[1] == "authorization.completed"
        assert event_names[2] == "retrieval.completed"
        assert event_names[3] == "generation.started"
        assert "token" in event_names
        assert "citation" in event_names
        assert event_names[-1] == "generation.completed"

        # Check citation details
        citations = [e["data"] for e in events if e["event"] == "citation"]
        assert len(citations) == 1
        assert citations[0]["document_id"] == "doc_leave_policy"
        assert citations[0]["title"] == "Leave and Attendance Policy"

    async def test_streaming_emits_error_when_authorization_fails(
        self, retrieval_service, mock_fga_client
    ):
        """When OpenFGA is down, stream terminates with error event without starting generation."""
        mock_fga_client.list_objects.side_effect = AuthorizationServiceUnavailableError(
            "OpenFGA connection refused"
        )

        chat_service = ChatService(
            retrieval_service=retrieval_service,
            llm_provider=MockLLMProvider(),
        )

        events = await collect_events(
            chat_service.stream_response(
                question="Any question",
                user_id="alice",
                tenant_id="org_acme",
            )
        )

        event_names = [e["event"] for e in events]
        assert "conversation.started" in event_names
        assert "error" in event_names
        assert "generation.started" not in event_names
        assert "token" not in event_names

    async def test_streaming_never_leaks_sensitive_internals(
        self, retrieval_service, mock_fga_client, mock_vector_store
    ):
        """Verify the stream output contains no passwords, server file paths, or raw tuples."""
        mock_fga_client.list_objects.return_value = ["document:doc_1"]
        mock_vector_store.similarity_search.return_value = []

        chat_service = ChatService(
            retrieval_service=retrieval_service,
            llm_provider=MockLLMProvider(),
        )

        raw_output = ""
        async for chunk in chat_service.stream_response("query", "alice", "org_acme"):
            raw_output += chunk

        forbidden_strings = [
            "password123",
            "hashed_password",
            "/app/data/uploads",
            "tuple_key",
            "OPENFGA_STORE_ID",
            "JWT_SECRET",
        ]
        for s in forbidden_strings:
            assert s not in raw_output, f"Security leakage: found '{s}' in stream output!"

