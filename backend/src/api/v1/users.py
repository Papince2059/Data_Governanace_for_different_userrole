"""
Users API.
Provides user listing and user detail endpoints with tenant isolation and role restrictions.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth import get_current_user
from src.core.exceptions import AuthorizationError, NotFoundError
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import Department, User, UserRole

router = APIRouter(prefix="/users", tags=["Users"])


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    department_id: Optional[str] = None
    tenant_id: str
    created_at: str


@router.get("", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[UserResponse]:
    """List users belonging to the current tenant."""
    query = select(User).where(User.tenant_id == current_user.tenant_id)
    result = await db.execute(query)
    users = result.scalars().all()

    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            is_active=u.is_active,
            department_id=str(u.department_id) if u.department_id else None,
            tenant_id=str(u.tenant_id),
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in users
    ]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Fetch details for a specific user. Requires admin role or requesting user's own profile."""
    if current_user.role != UserRole.ADMIN and str(current_user.id) != user_id:
        raise AuthorizationError("Access denied: You can only view your own user profile")

    try:
        user_uuid = uuid.UUID(user_id)
        query = select(User).where(User.id == user_uuid, User.tenant_id == current_user.tenant_id)
    except ValueError:
        query = select(User).where(User.email == user_id, User.tenant_id == current_user.tenant_id)

    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("user", user_id)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        department_id=str(user.department_id) if user.department_id else None,
        tenant_id=str(user.tenant_id),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )

