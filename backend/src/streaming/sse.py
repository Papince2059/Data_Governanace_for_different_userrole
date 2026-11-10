"""
Server-Sent Events (SSE) formatting utilities.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class SSEEvent:
    event: str
    data: dict[str, Any]

    def to_wire(self) -> str:
        """Format event to standard SSE text protocol."""
        payload = json.dumps(self.data)
        return f"event: {self.event}\ndata: {payload}\n\n"


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    """Helper to convert event type and payload to SSE string."""
    return SSEEvent(event=event_type, data=data).to_wire()

