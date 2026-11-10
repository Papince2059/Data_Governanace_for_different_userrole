"""
Chat Service — Orchestrator for Permission-Aware Streaming RAG.

SECURITY AND INTEGRITY CONSTRAINTS:
1. OpenFGA authorization runs BEFORE any vector search or generation.
2. If authorization fails or service is down, emits error and terminates immediately.
3. Only authorized document chunks enter the prompt context.
4. Internal prompts, secrets, and raw permission tuples are NEVER streamed.
5. Emits SSE event sequence conforming to the project specification.
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncIterator, Optional

from src.core.exceptions import AuthorizationServiceUnavailableError
from src.core.logging import get_logger
from src.infrastructure.llm.base import BaseLLMProvider, LLMMessage
from src.services.retrieval_service import RetrievalService
from src.streaming.sse import format_sse

logger = get_logger(__name__)


class ChatService:
    """
    Manages streaming conversations with pre-retrieval authorization.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_provider: BaseLLMProvider,
    ) -> None:
        self.retrieval = retrieval_service
        self.llm = llm_provider

    def _build_rag_prompt(self, question: str, chunks: list) -> list[LLMMessage]:
        """
        Assemble the LLM prompt. ONLY authorized chunks are included.
        System prompt strictly forbids hallucinating or leaking internal state.
        """
        if chunks:
            context_blocks = []
            for i, chunk in enumerate(chunks):
                context_blocks.append(
                    f"--- Source {i+1}: {chunk.document_title} (similarity: {chunk.similarity:.2f}) ---\n"
                    f"{chunk.content}"
                )
            context_text = "\n\n".join(context_blocks)
            system_prompt = (
                "You are an enterprise AI assistant for Acme Corporation. "
                "Answer the user's inquiry accurately and professionally based ONLY on the authorized context below.\n"
                "If the context does not contain enough information to answer, state that clearly.\n"
                "Never cite documents outside the provided context.\n\n"
                f"DOCUMENT CONTEXT:\n{context_text}"
            )
        else:
            system_prompt = (
                "You are an enterprise AI assistant for Acme Corporation. "
                "The user has submitted a question, but under the enterprise access control list (ACL) policy, "
                "they do not have permission to view any matching records in the system. "
                "Politely inform the user that no authorized documents were found for their query "
                "and advise them to consult their department manager or IT administrator if they require access."
            )

        return [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=question),
        ]

    async def stream_response(
        self,
        question: str,
        user_id: str,
        tenant_id: str,
        conversation_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream a RAG answer as Server-Sent Events (SSE).
        Enforces:
          1. conversation.started
          2. OpenFGA ACL pre-filter + vector retrieval
          3. authorization.completed
          4. retrieval.completed
          5. generation.started
          6. token (streamed tokens)
          7. citation (source citations)
          8. generation.completed
        """
        conv_id = conversation_id or str(uuid.uuid4())

        # 1. Event: conversation.started
        yield format_sse(
            "conversation.started",
            {"conversation_id": conv_id, "user_id": user_id, "tenant_id": tenant_id},
        )

        # 2. Authorization + Retrieval (Fail-closed on any authorization error)
        try:
            retrieval_ctx = await self.retrieval.retrieve(
                query=question,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        except AuthorizationServiceUnavailableError as e:
            logger.error("chat_authorization_unavailable", user_id=user_id, error=str(e))
            yield format_sse(
                "error",
                {
                    "code": "AUTHORIZATION_SERVICE_UNAVAILABLE",
                    "message": "Authorization engine is unavailable. Retrieval blocked (fail-closed).",
                },
            )
            return
        except Exception as e:
            logger.error("chat_retrieval_failed", user_id=user_id, error=str(e))
            yield format_sse(
                "error",
                {
                    "code": "RETRIEVAL_ERROR",
                    "message": "A secure retrieval error occurred. No context was generated.",
                },
            )
            return

        # 3. Event: authorization.completed
        yield format_sse(
            "authorization.completed",
            {
                "authorized_doc_count": retrieval_ctx.authorized_doc_count,
                "authorization_latency_ms": round(retrieval_ctx.authorization_latency_ms, 2),
            },
        )

        # 4. Event: retrieval.completed
        retrieved_doc_ids = list({c.document_id for c in retrieval_ctx.chunks})
        yield format_sse(
            "retrieval.completed",
            {
                "chunk_count": retrieval_ctx.retrieved_chunk_count,
                "doc_count": len(retrieved_doc_ids),
                "retrieval_latency_ms": round(retrieval_ctx.retrieval_latency_ms, 2),
                "embedding_latency_ms": round(retrieval_ctx.embedding_latency_ms, 2),
            },
        )

        # 5. Build prompt with authorized context only
        messages = self._build_rag_prompt(question, retrieval_ctx.chunks)

        # 6. Event: generation.started
        yield format_sse("generation.started", {"conversation_id": conv_id})

        # 7. Stream LLM tokens
        total_tokens = 0
        try:
            async for token in self.llm.stream_chat(messages):
                if token.is_final:
                    total_tokens = token.total_tokens or total_tokens
                    break
                if token.content:
                    yield format_sse("token", {"content": token.content})
                    total_tokens += 1
        except Exception as e:
            logger.error("llm_generation_failed", error=str(e), user_id=user_id)
            yield format_sse(
                "error",
                {
                    "code": "GENERATION_ERROR",
                    "message": "Model generation encountered an unexpected interruption.",
                },
            )
            return

        # 8. Event: citation (safe citations for each retrieved chunk)
        for chunk in retrieval_ctx.chunks:
            yield format_sse(
                "citation",
                {
                    "document_id": chunk.document_id,
                    "title": chunk.document_title,
                    "chunk_index": chunk.chunk_index,
                    "similarity": round(chunk.similarity, 3),
                },
            )

        # 9. Event: generation.completed
        yield format_sse(
            "generation.completed",
            {
                "conversation_id": conv_id,
                "total_tokens": total_tokens,
                "authorized_doc_count": retrieval_ctx.authorized_doc_count,
                "retrieved_chunk_count": retrieval_ctx.retrieved_chunk_count,
            },
        )

        logger.info(
            "chat_stream_finished",
            user_id=user_id,
            conversation_id=conv_id,
            tokens=total_tokens,
            chunks=retrieval_ctx.retrieved_chunk_count,
        )

