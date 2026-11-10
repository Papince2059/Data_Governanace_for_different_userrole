"""
Authentication API.
Provides login with JWT issuance and current user profile inspection.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.exceptions import AuthenticationError
from src.core.logging import get_logger
from src.core.security import (
    TokenData,
    create_access_token,
    verify_password,
    verify_token,
)
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import AuditAction, AuthorizationAuditLog, Department, User, UserRole

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
security_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    email: str
    full_name: str
    role: str
    is_admin: bool
    tenant_id: str
    department_id: Optional[str] = None
    department_name: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_admin: bool
    tenant_id: str
    department_id: Optional[str] = None
    department_name: Optional[str] = None


async def get_current_user_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> TokenData:
    """Extract and verify JWT token from Authorization header. Never trust arbitrary headers."""
    if not credentials:
        raise AuthenticationError("Missing or invalid Authorization header")
    return verify_token(credentials.credentials)


async def get_current_user(
    token_data: TokenData = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Fetch the authenticated user from the database based on verified JWT."""
    try:
        user_uuid = uuid.UUID(token_data.user_id)
        query = select(User).where(User.id == user_uuid, User.is_active == True)
    except ValueError:
        # Fallback for synthetic seeded user names if needed
        query = select(User).where(User.email == token_data.email, User.is_active == True)

    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("Authenticated user no longer exists or is inactive")

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Authenticate demo user credentials against PostgreSQL.
    Issues a cryptographically signed JWT with tenant isolation.
    """
    query = select(User).where(User.email == body.email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    request_id = getattr(request.state, "request_id", None)

    if not user or not verify_password(body.password, user.hashed_password):
        # Audit failed login
        audit = AuthorizationAuditLog(
            id=uuid.uuid4(),
            user_id=user.id if user else None,
            action=AuditAction.LOGIN_FAILED,
            resource_type="auth",
            resource_id="session",
            allowed=False,
            reason="Invalid email or password",
            request_id=request_id,
            tenant_id=user.tenant_id if user else None,
        )
        db.add(audit)
        await db.commit()
        raise AuthenticationError("Invalid email or password")

    if not user.is_active:
        raise AuthenticationError("User account is disabled")

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)

    # Fetch department name if applicable
    dept_name = None
    if user.department_id:
        dept_result = await db.execute(select(Department).where(Department.id == user.department_id))
        dept = dept_result.scalar_one_or_none()
        if dept:
            dept_name = dept.name

    # Audit successful login
    audit = AuthorizationAuditLog(
        id=uuid.uuid4(),
        user_id=user.id,
        action=AuditAction.LOGIN_SUCCESS,
        resource_type="auth",
        resource_id="session",
        allowed=True,
        reason="Successful authentication",
        request_id=request_id,
        tenant_id=user.tenant_id,
    )
    db.add(audit)
    await db.commit()

    settings = get_settings()
    is_admin = (user.role == UserRole.ADMIN)

    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": str(user.tenant_id),
        "is_admin": is_admin,
    }

    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(token_payload, expires_delta=expires_delta)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_admin=is_admin,
        tenant_id=str(user.tenant_id),
        department_id=str(user.department_id) if user.department_id else None,
        department_name=dept_name,
    )


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserProfile:
    """Return the profile of the authenticated user identified by JWT."""
    dept_name = None
    if current_user.department_id:
        dept_result = await db.execute(select(Department).where(Department.id == current_user.department_id))
        dept = dept_result.scalar_one_or_none()
        if dept:
            dept_name = dept.name

    return UserProfile(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        is_admin=(current_user.role == UserRole.ADMIN),
        tenant_id=str(current_user.tenant_id),
        department_id=str(current_user.department_id) if current_user.department_id else None,
        department_name=dept_name,
    )

