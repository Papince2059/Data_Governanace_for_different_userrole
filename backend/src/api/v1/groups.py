"""
Groups API.
Lists authorization groups within the tenant.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth import get_current_user
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import Group, User

router = APIRouter(prefix="/groups", tags=["Groups"])


class GroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    organization_id: str
    is_active: bool


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[GroupResponse]:
    """Retrieve all groups within the current user's organization."""
    query = select(Group).where(
        Group.organization_id == current_user.tenant_id,
        Group.is_active == True,
    )
    result = await db.execute(query)
    groups = result.scalars().all()

    return [
        GroupResponse(
            id=str(g.id),
            name=g.name,
            description=g.description,
            organization_id=str(g.organization_id),
            is_active=g.is_active,
        )
        for g in groups
    ]

