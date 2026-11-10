"""
Google Cloud Vertex AI LLM Provider Adapter.
Streams tokens from Gemini models on Vertex AI using service credentials.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator, Optional

import google.auth
from google.auth.transport.requests import Request
from google import genai
from google.genai import types

from src.core.config import get_settings
from src.core.logging import get_logger
from src.infrastructure.llm.base import BaseLLMProvider, LLMMessage, StreamToken
from src.infrastructure.llm.mock_adapter import MockLLMProvider

logger = get_logger(__name__)


class VertexAIProvider(BaseLLMProvider):
    """
    Adapter communicating with Google Cloud Vertex AI using service credentials.
    Streams Gemini tokens asynchronously using google-genai SDK.
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        self.credentials_path = credentials_path or settings.VERTEX_CREDENTIALS_PATH
        self.location = location or settings.VERTEX_LOCATION
        self.model = model or settings.VERTEX_MODEL
        self._project_id = project_id or settings.VERTEX_PROJECT_ID
        self._client: Optional[genai.Client] = None
        self._mock_fallback = MockLLMProvider()

    def _resolve_project_id(self, creds_path: Path) -> str:
        """Resolve GCP project ID from config or credentials JSON file."""
        if self._project_id:
            return self._project_id
        if creds_path.exists():
            try:
                data = json.loads(creds_path.read_text())
                project = data.get("quota_project_id") or data.get("project_id")
                if project:
                    return project
            except Exception as e:
                logger.warning("failed_to_read_project_from_creds", error=str(e))
        return "project-420160a8-73be-41cf-965"

    def _get_client(self) -> tuple[genai.Client, str]:
        """Initialize and cache the genai.Client authenticated via Vertex credentials."""
        if self._client is not None:
            return self._client, self._project_id

        # Resolve path
        path = Path(self.credentials_path)
        if not path.is_absolute():
            # Check relative to cwd or project root
            root = Path(__file__).resolve().parents[4]
            candidate = root / self.credentials_path
            if candidate.exists():
                path = candidate

        if not path.exists():
            raise FileNotFoundError(f"Vertex AI credentials not found at {path}")

        project_id = self._resolve_project_id(path)
        self._project_id = project_id

        creds, _ = google.auth.load_credentials_from_file(
            str(path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        creds.refresh(Request())

        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=self.location,
            credentials=creds,
        )
        logger.info(
            "vertex_ai_client_initialized",
            project=project_id,
            location=self.location,
            model=self.model,
        )
        return self._client, project_id

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> AsyncIterator[StreamToken]:
        """
        Stream tokens from Vertex AI Gemini.
        If billing or API error occurs, emits a clear diagnostic token and falls back.
        """
        try:
            client, project_id = self._get_client()

            # Separate system prompt and chat contents
            system_instruction = None
            contents = []
            for m in messages:
                if m.role == "system":
                    system_instruction = m.content
                else:
                    role = "user" if m.role == "user" else "model"
                    contents.append(
                        types.Content(
                            role=role,
                            parts=[types.Part.from_text(text=m.content)],
                        )
                    )

            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            total_tokens = 0
            stream = await client.aio.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            )

            async for chunk in stream:
                text = chunk.text or ""
                if text:
                    total_tokens += 1
                    yield StreamToken(content=text, is_final=False)

            yield StreamToken(content="", is_final=True, total_tokens=total_tokens)

        except Exception as e:
            error_str = str(e)
            logger.error("vertex_ai_stream_error", error=error_str, model=self.model)

            # Check if this is a billing disabled error
            if "BILLING_DISABLED" in error_str or "billing to be enabled" in error_str:
                warning = (
                    f"⚠️ [Vertex AI Notice: Google Cloud Project '{self._project_id}' requires billing to be enabled.\n"
                    f"To enable live Vertex AI inference, visit: https://console.developers.google.com/billing/enable?project={self._project_id}\n"
                    f"Falling back to local model response for this request.]\n\n"
                )
            else:
                warning = (
                    f"⚠️ [Vertex AI Error: {error_str}.\n"
                    f"Falling back to local model response for this request.]\n\n"
                )

            yield StreamToken(content=warning, is_final=False)

            # Stream fallback tokens
            async for token in self._mock_fallback.stream_chat(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            ):
                yield token

    async def health_check(self) -> bool:
        """Verify Vertex credentials file presence."""
        try:
            path = Path(self.credentials_path)
            if not path.is_absolute():
                root = Path(__file__).resolve().parents[4]
                if (root / self.credentials_path).exists():
                    return True
            return path.exists()
        except Exception:
            return False

