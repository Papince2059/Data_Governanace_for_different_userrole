"""
Permissions Management API — Zanzibar-inspired ReBAC with OpenFGA.
Enforces administrative controls: only administrators can grant or revoke permissions.
All grant, revoke, and check operations are audited.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth import get_current_user
from src.core.config import get_settings
from src.core.exceptions import AuthorizationError
from src.core.logging import get_logger
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import AuditAction, AuthorizationAuditLog, User, UserRole
from src.infrastructure.openfga.client import OpenFGAClient
from src.services.authorization_service import AuthorizationService

logger = get_logger(__name__)
router = APIRouter(prefix="/permissions", tags=["Permissions"])


def get_fga_client() -> OpenFGAClient:
    settings = get_settings()
    return OpenFGAClient(
        api_url=settings.OPENFGA_API_URL,
        store_id=settings.OPENFGA_STORE_ID,
        auth_model_id=settings.OPENFGA_AUTH_MODEL_ID,
        timeout=settings.OPENFGA_TIMEOUT_SECONDS,
    )


def get_auth_service(fga_client: OpenFGAClient = Depends(get_fga_client)) -> AuthorizationService:
    return AuthorizationService(fga_client=fga_client)


class CheckPermissionRequest(BaseModel):
    user_id: str
    relation: str = Field(description="e.g. can_read, can_write, viewer, editor")
    resource_type: str = Field(description="e.g. document, folder, department")
    resource_id: str


class PermissionCheckResponse(BaseModel):
    allowed: bool
    user: str
    relation: str
    object: str


class GrantRevokeRequest(BaseModel):
    user_or_group: str = Field(
        description="OpenFGA subject, e.g. 'user:uuid', 'user:alice', 'group:hr#member', 'department:hr#member'"
    )
    relation: str = Field(description="e.g. viewer, editor, owner, member")
    resource_type: str = Field(description="e.g. document, folder, department")
    resource_id: str


class AccessibleResourcesResponse(BaseModel):
    user_id: str
    resource_type: str
    authorized_ids: list[str]
    count: int


@router.post("/check", response_model=PermissionCheckResponse)
async def check_permission(
    request: Request,
    body: CheckPermissionRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthorizationService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> PermissionCheckResponse:
    """
    Evaluate an authorization check using the Zanzibar permission graph in OpenFGA.
    Audited to authorization_audit_logs.
    """
    # Format OpenFGA identifiers
    user_str = body.user_id if body.user_id.startswith("user:") else f"user:{body.user_id}"
    obj_str = (
        body.resource_id
        if ":" in body.resource_id
        else f"{body.resource_type}:{body.resource_id}"
    )

    allowed = await auth_service.fga.check(
        user=user_str,
        relation=body.relation,
        object=obj_str,
    )

    # Audit log
    request_id = getattr(request.state, "request_id", None)
    audit = AuthorizationAuditLog(
        id=uuid.uuid4(),
        user_id=current_user.id,
        action=AuditAction.ACCESS_GRANTED if allowed else AuditAction.ACCESS_DENIED,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        allowed=allowed,
        reason=f"Permission check: {user_str} {body.relation} {obj_str}",
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )
    db.add(audit)
    await db.commit()

    return PermissionCheckResponse(
        allowed=allowed,
        user=user_str,
        relation=body.relation,
        object=obj_str,
    )


@router.post("/grant", status_code=status.HTTP_204_NO_CONTENT)
async def grant_permission(
    request: Request,
    body: GrantRevokeRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthorizationService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    ADMIN ONLY: Grant a permission tuple in the Zanzibar permission graph.
    Ordinary users cannot invoke this endpoint.
    """
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Administrative privileges required to grant permissions")

    obj_str = (
        body.resource_id
        if ":" in body.resource_id
        else f"{body.resource_type}:{body.resource_id}"
    )

    await auth_service.fga.write_tuple(
        user=body.user_or_group,
        relation=body.relation,
        object=obj_str,
    )

    # Audit log
    request_id = getattr(request.state, "request_id", None)
    audit = AuthorizationAuditLog(
        id=uuid.uuid4(),
        user_id=current_user.id,
        action=AuditAction.PERMISSION_GRANTED,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        allowed=True,
        reason=f"Granted: {body.user_or_group} -> {body.relation} -> {obj_str}",
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )
    db.add(audit)
    await db.commit()
    logger.info("permission_granted_by_admin", admin_id=str(current_user.id), tuple=(body.user_or_group, body.relation, obj_str))


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    request: Request,
    body: GrantRevokeRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthorizationService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """
    ADMIN ONLY: Revoke a permission tuple from the Zanzibar permission graph.
    Takes effect immediately on all subsequent requests (no stale cache).
    """
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Administrative privileges required to revoke permissions")

    obj_str = (
        body.resource_id
        if ":" in body.resource_id
        else f"{body.resource_type}:{body.resource_id}"
    )

    await auth_service.fga.delete_tuple(
        user=body.user_or_group,
        relation=body.relation,
        object=obj_str,
    )

    # Audit log
    request_id = getattr(request.state, "request_id", None)
    audit = AuthorizationAuditLog(
        id=uuid.uuid4(),
        user_id=current_user.id,
        action=AuditAction.PERMISSION_REVOKED,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        allowed=True,
        reason=f"Revoked: {body.user_or_group} -> {body.relation} -> {obj_str}",
        request_id=request_id,
        tenant_id=current_user.tenant_id,
    )
    db.add(audit)
    await db.commit()
    logger.info("permission_revoked_by_admin", admin_id=str(current_user.id), tuple=(body.user_or_group, body.relation, obj_str))


@router.get("/resources", response_model=AccessibleResourcesResponse)
async def list_accessible_resources(
    user_id: Optional[str] = None,
    resource_type: str = "document",
    current_user: User = Depends(get_current_user),
    auth_service: AuthorizationService = Depends(get_auth_service),
) -> AccessibleResourcesResponse:
    """
    Return all resources of a given type accessible by a user via OpenFGA ListObjects.
    Used for pre-retrieval ACL auditing and testing.
    """
    # Non-admins can only check their own accessible resources
    target_user_id = user_id or str(current_user.id)
    allowed_ids = {str(current_user.id), current_user.email, current_user.email.split("@")[0]}
    if current_user.role != UserRole.ADMIN and target_user_id not in allowed_ids:
        raise AuthorizationError("You may only view your own accessible resources")

    accessible = await auth_service.get_accessible_document_ids(target_user_id)

    return AccessibleResourcesResponse(
        user_id=target_user_id,
        resource_type=resource_type,
        authorized_ids=accessible,
        count=len(accessible),
    )

