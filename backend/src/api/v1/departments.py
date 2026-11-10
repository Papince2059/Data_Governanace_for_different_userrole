"""
Departments API.
Lists departments within the authenticated user's organization tenant.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth import get_current_user
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import Department, User

router = APIRouter(prefix="/departments", tags=["Departments"])


class DepartmentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    organization_id: str
    is_active: bool


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[DepartmentResponse]:
    """Retrieve all departments belonging to the current user's organization."""
    query = select(Department).where(
        Department.organization_id == current_user.tenant_id,
        Department.is_active == True,
    )
    result = await db.execute(query)
    depts = result.scalars().all()

    return [
        DepartmentResponse(
            id=str(d.id),
            name=d.name,
            description=d.description,
            organization_id=str(d.organization_id),
            is_active=d.is_active,
        )
        for d in depts
    ]

