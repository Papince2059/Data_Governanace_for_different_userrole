"""
Ollama LLM Provider Adapter.
Streams tokens from a locally hosted Ollama instance (e.g. llama3.2, mistral).
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger
from src.infrastructure.llm.base import BaseLLMProvider, LLMMessage, StreamToken
from src.infrastructure.llm.mock_adapter import MockLLMProvider

logger = get_logger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Ollama adapter communicating with local Ollama daemon over HTTP streaming.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamToken]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("done"):
                            yield StreamToken(
                                content="",
                                is_final=True,
                                total_tokens=data.get("eval_count"),
                            )
                            return
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield StreamToken(content=content, is_final=False)
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception as e:
            logger.warning("ollama_health_check_failed", error=str(e))
            return False


def get_llm_provider() -> BaseLLMProvider:
    """Factory function returning the configured LLM provider."""
    settings = get_settings()
    if settings.LLM_PROVIDER == "vertexai":
        from src.infrastructure.llm.vertex_adapter import VertexAIProvider
        return VertexAIProvider()
    elif settings.LLM_PROVIDER == "ollama":
        return OllamaProvider()
    return MockLLMProvider()

