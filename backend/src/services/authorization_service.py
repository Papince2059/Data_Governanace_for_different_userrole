"""
Authorization Service — the ONLY way permission checks happen in this application.
All routes and services MUST use this service. Never call OpenFGA directly from routes.
Implements fail-closed security.
"""
from typing import Optional

from src.infrastructure.openfga.client import OpenFGAClient
from src.core.exceptions import AuthorizationServiceUnavailableError, AuthorizationError
from src.core.logging import get_logger

logger = get_logger(__name__)


UUID_TO_USERNAME = {
    "33333333-3333-3333-3333-333333333301": "alice",
    "33333333-3333-3333-3333-333333333302": "helen",
    "33333333-3333-3333-3333-333333333303": "bob",
    "33333333-3333-3333-3333-333333333304": "frank",
    "33333333-3333-3333-3333-333333333305": "charlie",
    "33333333-3333-3333-3333-333333333306": "sara",
    "33333333-3333-3333-3333-333333333307": "david",
    "33333333-3333-3333-3333-333333333308": "irene",
    "33333333-3333-3333-3333-333333333399": "admin",
}


def resolve_user_subject(user_id: str) -> str:
    cleaned = user_id.replace("user:", "")
    username = UUID_TO_USERNAME.get(cleaned, cleaned)
    if "@" in username:
        username = username.split("@")[0]
    return username


class AuthorizationService:
    def __init__(self, fga_client: OpenFGAClient):
        self.fga = fga_client

    async def can_read_document(self, user_id: str, document_id: str) -> bool:
        """Check if user can read a specific document. Fail closed."""
        u_subj = resolve_user_subject(user_id)
        return await self.fga.check(
            user=f"user:{u_subj}",
            relation="can_read",
            object=f"document:{document_id}",
        )

    async def can_write_document(self, user_id: str, document_id: str) -> bool:
        """Check if user can write to a specific document. Fail closed."""
        u_subj = resolve_user_subject(user_id)
        return await self.fga.check(
            user=f"user:{u_subj}",
            relation="can_write",
            object=f"document:{document_id}",
        )

    async def get_accessible_document_ids(self, user_id: str) -> list[str]:
        """
        Get ALL document IDs the user can read via OpenFGA ListObjects.
        This is used for pre-retrieval ACL filtering.
        Returns empty list if OpenFGA unavailable (fail closed).
        Never returns all documents as fallback.
        """
        u_subj = resolve_user_subject(user_id)
        objects = await self.fga.list_objects(
            user=f"user:{u_subj}",
            relation="can_read",
            object_type="document",
        )
        # Strip the "document:" prefix, return only the UUID/ID parts
        return [obj.replace("document:", "") for obj in objects]

    async def require_document_read(self, user_id: str, document_id: str) -> None:
        """Raise AuthorizationError if user cannot read document."""
        allowed = await self.can_read_document(user_id, document_id)
        if not allowed:
            raise AuthorizationError(
                message=f"User {user_id} is not authorized to read document {document_id}",
                resource=f"document:{document_id}",
                action="read",
            )

    async def require_document_write(self, user_id: str, document_id: str) -> None:
        """Raise AuthorizationError if user cannot write to document."""
        allowed = await self.can_write_document(user_id, document_id)
        if not allowed:
            raise AuthorizationError(
                message=f"User {user_id} is not authorized to write document {document_id}",
                resource=f"document:{document_id}",
                action="write",
            )

    async def grant_document_permission(self, user_or_group: str, relation: str, document_id: str) -> None:
        """Grant a permission. user_or_group can be 'user:xyz' or 'group:xyz#member'."""
        await self.fga.write_tuple(
            user=user_or_group,
            relation=relation,
            object=f"document:{document_id}",
        )
        logger.info(
            "document_permission_granted",
            subject=user_or_group,
            relation=relation,
            document_id=document_id,
        )

    async def revoke_document_permission(self, user_or_group: str, relation: str, document_id: str) -> None:
        """Revoke a permission."""
        await self.fga.delete_tuple(
            user=user_or_group,
            relation=relation,
            object=f"document:{document_id}",
        )
        logger.info(
            "document_permission_revoked",
            subject=user_or_group,
            relation=relation,
            document_id=document_id,
        )

    async def grant_folder_permission(self, user_or_group: str, relation: str, folder_id: str) -> None:
        """Grant a permission on a folder."""
        await self.fga.write_tuple(
            user=user_or_group,
            relation=relation,
            object=f"folder:{folder_id}",
        )
        logger.info(
            "folder_permission_granted",
            subject=user_or_group,
            relation=relation,
            folder_id=folder_id,
        )

    async def revoke_folder_permission(self, user_or_group: str, relation: str, folder_id: str) -> None:
        """Revoke a permission on a folder."""
        await self.fga.delete_tuple(
            user=user_or_group,
            relation=relation,
            object=f"folder:{folder_id}",
        )
        logger.info(
            "folder_permission_revoked",
            subject=user_or_group,
            relation=relation,
            folder_id=folder_id,
        )

    async def add_user_to_group(self, user_id: str, group_id: str) -> None:
        """Add a user to a group by writing a member tuple."""
        await self.fga.write_tuple(
            user=f"user:{user_id}",
            relation="member",
            object=f"group:{group_id}",
        )
        logger.info("user_added_to_group", user_id=user_id, group_id=group_id)

    async def remove_user_from_group(self, user_id: str, group_id: str) -> None:
        """Remove a user from a group by deleting the member tuple."""
        await self.fga.delete_tuple(
            user=f"user:{user_id}",
            relation="member",
            object=f"group:{group_id}",
        )
        logger.info("user_removed_from_group", user_id=user_id, group_id=group_id)

    async def add_group_to_department(self, group_id: str, department_id: str) -> None:
        """Add a group's members to a department."""
        await self.fga.write_tuple(
            user=f"group:{group_id}#member",
            relation="member",
            object=f"department:{department_id}",
        )
        logger.info("group_added_to_department", group_id=group_id, department_id=department_id)

    async def remove_group_from_department(self, group_id: str, department_id: str) -> None:
        """Remove a group's members from a department."""
        await self.fga.delete_tuple(
            user=f"group:{group_id}#member",
            relation="member",
            object=f"department:{department_id}",
        )
        logger.info("group_removed_from_department", group_id=group_id, department_id=department_id)

    async def is_admin(self, user_id: str, tenant_id: str) -> bool:
        """Check if user is an organization admin."""
        return await self.fga.check(
            user=f"user:{user_id}",
            relation="admin",
            object=f"organization:{tenant_id}",
        )

    async def is_department_member(self, user_id: str, department_id: str) -> bool:
        """Check if user is a member of a department."""
        return await self.fga.check(
            user=f"user:{user_id}",
            relation="member",
            object=f"department:{department_id}",
        )

    async def can_view_folder(self, user_id: str, folder_id: str) -> bool:
        """Check if user can view a folder."""
        return await self.fga.check(
            user=f"user:{user_id}",
            relation="can_read",
            object=f"folder:{folder_id}",
        )

    async def can_edit_folder(self, user_id: str, folder_id: str) -> bool:
        """Check if user can edit a folder."""
        return await self.fga.check(
            user=f"user:{user_id}",
            relation="can_write",
            object=f"folder:{folder_id}",
        )

    async def get_accessible_folder_ids(self, user_id: str) -> list[str]:
        """
        Get all folder IDs the user can read via OpenFGA ListObjects.
        Returns empty list if OpenFGA unavailable (fail closed).
        """
        objects = await self.fga.list_objects(
            user=f"user:{user_id}",
            relation="can_read",
            object_type="folder",
        )
        return [obj.replace("folder:", "") for obj in objects]
