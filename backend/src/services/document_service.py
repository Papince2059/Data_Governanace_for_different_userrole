"""
Document Service — Business logic for document access, listing, and management.
Enforces OpenFGA authorization and logs all access attempts to document_access_logs.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthorizationError, NotFoundError
from src.core.logging import get_logger
from src.infrastructure.database.models import Document, DocumentAccessLog
from src.services.authorization_service import AuthorizationService

logger = get_logger(__name__)


class DocumentService:
    """
    Manages document queries with OpenFGA permission enforcement.
    """

    def __init__(
        self,
        db: AsyncSession,
        auth_service: AuthorizationService,
    ) -> None:
        self.db = db
        self.auth_service = auth_service

    async def list_accessible_documents(
        self,
        user_id: str,
        tenant_id: str,
        department_id: Optional[str] = None,
    ) -> list[Document]:
        """
        List all documents the user is authorized to read under OpenFGA.
        Pre-retrieval ACL: calls OpenFGA ListObjects, then queries DB.
        """
        # Step 1: Query OpenFGA for authorized document IDs
        authorized_ids = await self.auth_service.get_accessible_document_ids(user_id)
        if not authorized_ids:
            return []

        # Convert to clean IDs
        clean_ids = [d.replace("document:", "") for d in authorized_ids]

        # Step 2: Query database for matching active documents in the tenant
        query = select(Document).where(
            (Document.id.in_([uuid.UUID(x) for x in clean_ids if self._is_valid_uuid(x)]) |
             Document.openfga_resource_id.in_([f"document:{x}" for x in clean_ids])),
            Document.status == "active",
        )

        if tenant_id and self._is_valid_uuid(tenant_id):
            query = query.where(Document.tenant_id == uuid.UUID(tenant_id))

        if department_id and self._is_valid_uuid(department_id):
            query = query.where(Document.department_id == uuid.UUID(department_id))

        result = await self.db.execute(query)
        docs = list(result.scalars().all())
        return docs

    async def get_document_by_id(
        self,
        document_id: str,
        user_id: str,
        tenant_id: str,
        request_id: Optional[str] = None,
    ) -> Document:
        """
        Fetch a document by ID with OpenFGA authorization check.
        Logs access to document_access_logs.
        """
        # Check authorization first
        allowed = await self.auth_service.can_read_document(user_id, document_id)

        # Audit access attempt
        try:
            if self._is_valid_uuid(document_id) and self._is_valid_uuid(tenant_id):
                audit = DocumentAccessLog(
                    id=uuid.uuid4(),
                    document_id=uuid.UUID(document_id),
                    user_id=uuid.UUID(user_id) if self._is_valid_uuid(user_id) else None,
                    access_type="read",
                    allowed=allowed,
                    request_id=request_id,
                    tenant_id=uuid.UUID(tenant_id),
                )
                self.db.add(audit)
                await self.db.commit()
        except Exception as e:
            logger.warning("access_log_failed", error=str(e))

        if not allowed:
            raise AuthorizationError(
                message=f"Access denied: User {user_id} does not have permission to view document {document_id}",
                resource=f"document:{document_id}",
                action="read",
            )

        # Query document
        query = select(Document).where(
            (Document.id == uuid.UUID(document_id) if self._is_valid_uuid(document_id) else False) |
            (Document.openfga_resource_id == f"document:{document_id}")
        )
        result = await self.db.execute(query)
        doc = result.scalar_one_or_none()

        if not doc:
            raise NotFoundError("document", document_id)

        return doc

    async def delete_document(
        self,
        document_id: str,
        user_id: str,
        is_admin: bool,
    ) -> None:
        """
        Delete a document (only owner or admin can delete).
        """
        query = select(Document).where(
            (Document.id == uuid.UUID(document_id) if self._is_valid_uuid(document_id) else False) |
            (Document.openfga_resource_id == f"document:{document_id}")
        )
        result = await self.db.execute(query)
        doc = result.scalar_one_or_none()

        if not doc:
            raise NotFoundError("document", document_id)

        # Check write or admin permission
        if not is_admin and str(doc.owner_id) != user_id:
            can_write = await self.auth_service.can_write_document(user_id, document_id)
            if not can_write:
                raise AuthorizationError(
                    message="You do not have permission to delete this document",
                    resource=f"document:{document_id}",
                    action="delete",
                )

        doc.status = "deleted"
        await self.db.commit()

        # Remove from OpenFGA
        try:
            await self.auth_service.revoke_document_permission(f"user:{user_id}", "owner", document_id)
        except Exception as e:
            logger.warning("openfga_cleanup_error", error=str(e))

    @staticmethod
    def _is_valid_uuid(val: str) -> bool:
        try:
            uuid.UUID(val)
            return True
        except (ValueError, TypeError):
            return False

