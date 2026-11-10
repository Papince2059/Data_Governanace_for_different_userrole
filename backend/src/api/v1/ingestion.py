"""
Ingestion Status and Event Streaming API.
Provides job tracking and real-time SSE progress updates for document ingestion.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth import get_current_user
from src.core.exceptions import NotFoundError
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import IngestionEvent, IngestionJob, User
from src.streaming.sse import format_sse

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


class IngestionJobResponse(BaseModel):
    id: str
    document_id: str
    status: str
    progress: int
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> IngestionJobResponse:
    """Fetch the latest status of an ingestion job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise NotFoundError("ingestion_job", job_id)

    query = select(IngestionJob).where(IngestionJob.id == job_uuid)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise NotFoundError("ingestion_job", job_id)

    return IngestionJobResponse(
        id=str(job.id),
        document_id=str(job.document_id),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        progress=job.progress,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else "",
        updated_at=job.updated_at.isoformat() if job.updated_at else "",
    )


@router.get("/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream ingestion events for a specific job using Server-Sent Events (SSE).
    Clients connect to watch real-time extraction, chunking, embedding, and indexing progress.
    """
    async def event_generator():
        from src.infrastructure.database.connection import get_db_session

        last_seen_ids = set()
        finished = False

        while not finished:
            async for session in get_db_session():
                try:
                    job_uuid = uuid.UUID(job_id)
                except ValueError:
                    yield format_sse("error", {"message": "Invalid job ID"})
                    return

                # Get new events
                query = (
                    select(IngestionEvent)
                    .where(IngestionEvent.job_id == job_uuid)
                    .order_by(IngestionEvent.created_at.asc())
                )
                result = await session.execute(query)
                events = result.scalars().all()

                for ev in events:
                    ev_str_id = str(ev.id)
                    if ev_str_id not in last_seen_ids:
                        last_seen_ids.add(ev_str_id)
                        yield format_sse(
                            ev.event_type,
                            {
                                "job_id": job_id,
                                "event_type": ev.event_type,
                                "message": ev.message,
                                "metadata": ev.details or {},
                                "timestamp": ev.created_at.isoformat() if ev.created_at else "",
                            },
                        )
                        if ev.event_type in ("ingestion.completed", "ingestion.failed"):
                            finished = True

                # Check job directly if no explicit terminal event yet
                if not finished:
                    job_result = await session.execute(
                        select(IngestionJob).where(IngestionJob.id == job_uuid)
                    )
                    job = job_result.scalar_one_or_none()
                    if job and str(job.status) in ("completed", "failed"):
                        finished = True
                break

            if not finished:
                await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

