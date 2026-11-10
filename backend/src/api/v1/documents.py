"""
Documents API.
Endpoints for uploading, listing, viewing, and deleting governed enterprise documents.
Pre-retrieval ACL filtering enforces that users only see documents permitted by OpenFGA.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth import get_current_user
from src.api.v1.permissions import get_auth_service, get_fga_client
from src.core.exceptions import AuthorizationError, DocumentIngestionError, NotFoundError
from src.core.logging import get_logger
from src.infrastructure.database.connection import get_db_session
from src.infrastructure.database.models import Document, DocumentStatus, IngestionJob, IngestionStatus, User, UserRole
from src.infrastructure.embeddings.local_embedder import LocalEmbedder
from src.infrastructure.openfga.client import OpenFGAClient
from src.ingestion.pipeline import IngestionPipeline
from src.services.authorization_service import AuthorizationService
from src.services.document_service import DocumentService

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

embedder_instance = LocalEmbedder()


class DocumentResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    file_type: str
    file_size_bytes: Optional[int] = None
    status: str
    department_id: Optional[str] = None
    folder_id: Optional[str] = None
    owner_id: str
    created_at: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    job_id: str
    title: str
    status: str
    message: str


def get_document_service(
    db: AsyncSession = Depends(get_db_session),
    auth_service: AuthorizationService = Depends(get_auth_service),
) -> DocumentService:
    return DocumentService(db=db, auth_service=auth_service)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    viewer_group: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    fga_client: OpenFGAClient = Depends(get_fga_client),
) -> DocumentUploadResponse:
    """
    Upload a document for ingestion.
    Spawns background job that parses, chunks, embeds, and records OpenFGA permissions.
    """
    content = await file.read()
    if not content:
        raise DocumentIngestionError("Uploaded file is empty.")

    doc_uuid = uuid.uuid4()
    job_uuid = uuid.uuid4()

    # Determine department and folder IDs
    dept_uuid = uuid.UUID(department_id) if department_id and _is_uuid(department_id) else current_user.department_id
    fld_uuid = uuid.UUID(folder_id) if folder_id and _is_uuid(folder_id) else None

    # Determine file type
    file_ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "txt"

    # Create document record with pending status
    doc = Document(
        id=doc_uuid,
        title=title,
        description=description,
        file_path="",  # Filled in by pipeline
        file_type=file_ext,
        file_size_bytes=len(content),
        status=DocumentStatus.PENDING,
        tenant_id=current_user.tenant_id,
        department_id=dept_uuid,
        folder_id=fld_uuid,
        owner_id=current_user.id,
        openfga_resource_id=f"document:{doc_uuid}",
    )
    db.add(doc)

    # Create ingestion job
    job = IngestionJob(
        id=job_uuid,
        document_id=doc_uuid,
        status=IngestionStatus.PENDING,
        progress=0,
    )
    db.add(job)
    await db.commit()

    # Define background execution task
    async def run_pipeline():
        from src.infrastructure.database.connection import get_db_session
        async for session in get_db_session():
            pipeline = IngestionPipeline(
                db=session,
                embedder=embedder_instance,
                fga_client=fga_client,
            )
            try:
                await pipeline.ingest_document(
                    job_id=str(job_uuid),
                    document_id=str(doc_uuid),
                    content=content,
                    filename=file.filename or f"doc_{doc_uuid}.{file_ext}",
                    department_id=str(dept_uuid) if dept_uuid else None,
                    folder_id=str(fld_uuid) if fld_uuid else None,
                    owner_id=str(current_user.id),
                    tenant_id=str(current_user.tenant_id),
                    viewer_group=viewer_group,
                )
            except Exception as e:
                logger.error("background_ingestion_failed", doc_id=str(doc_uuid), error=str(e))
            break

    background_tasks.add_task(run_pipeline)

    return DocumentUploadResponse(
        document_id=str(doc_uuid),
        job_id=str(job_uuid),
        title=title,
        status="pending",
        message="Document accepted for asynchronous ingestion. Follow events at /ingestion/jobs/{job_id}/events",
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    department_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    """
    List only documents the current authenticated user is authorized to read.
    Enforces Pre-Retrieval ACL via OpenFGA ListObjects.
    """
    docs = await doc_service.list_accessible_documents(
        user_id=str(current_user.id),
        tenant_id=str(current_user.tenant_id),
        department_id=department_id,
    )

    return [
        DocumentResponse(
            id=str(d.id),
            title=d.title,
            description=d.description,
            file_type=d.file_type,
            file_size_bytes=d.file_size_bytes,
            status=d.status.value if hasattr(d.status, "value") else str(d.status),
            department_id=str(d.department_id) if d.department_id else None,
            folder_id=str(d.folder_id) if d.folder_id else None,
            owner_id=str(d.owner_id),
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    request: Request,
    document_id: str,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    """
    Retrieve document metadata.
    Enforces OpenFGA check: unauthorized access returns 403 Forbidden.
    """
    request_id = getattr(request.state, "request_id", None)
    doc = await doc_service.get_document_by_id(
        document_id=document_id,
        user_id=str(current_user.id),
        tenant_id=str(current_user.tenant_id),
        request_id=request_id,
    )

    return DocumentResponse(
        id=str(doc.id),
        title=doc.title,
        description=doc.description,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        department_id=str(doc.department_id) if doc.department_id else None,
        folder_id=str(doc.folder_id) if doc.folder_id else None,
        owner_id=str(doc.owner_id),
        created_at=doc.created_at.isoformat() if doc.created_at else "",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentService = Depends(get_document_service),
) -> None:
    """Delete a document. Requires document owner or administrator role."""
    await doc_service.delete_document(
        document_id=document_id,
        user_id=str(current_user.id),
        is_admin=(current_user.role == UserRole.ADMIN),
    )


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except (ValueError, TypeError):
        return False

