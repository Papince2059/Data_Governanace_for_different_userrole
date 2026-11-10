"""
SQLAlchemy 2.x ORM models for the Enterprise Data Governance System.

All models:
  - Use UUID primary keys generated server-side by uuid_generate_v4().
  - Carry created_at / updated_at timestamps (updated_at auto-refreshed via
    an onupdate hook on the Python side; the migration adds a DB trigger too).
  - Live in the shared `Base` from connection.py.

pgvector must be installed in the target PostgreSQL instance:
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from src.infrastructure.database.connection import Base


# ---------------------------------------------------------------------------
# Python-level enums (also stored as PG native enums via SAEnum)
# ---------------------------------------------------------------------------


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ACTIVE = "active"
    FAILED = "failed"
    DELETED = "deleted"
    pending = "pending"
    processing = "processing"
    active = "active"
    failed = "failed"
    deleted = "deleted"


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AuditAction(str, enum.Enum):
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    access_granted = "access_granted"
    access_denied = "access_denied"
    permission_granted = "permission_granted"
    permission_revoked = "permission_revoked"
    document_uploaded = "document_uploaded"
    document_deleted = "document_deleted"
    login_success = "login_success"
    login_failed = "login_failed"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    admin = "admin"
    member = "member"


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class UUIDMixin:
    """Adds a UUID primary key with server-side default."""

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------


class Organization(UUIDMixin, TimestampMixin, Base):
    """Top-level tenant.  Every piece of data is scoped to an Organization."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    departments: Mapped[list["Department"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    folders: Mapped[list["Folder"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    groups: Mapped[list["Group"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_organizations_slug", "slug"),
        Index("ix_organizations_is_active", "is_active"),
    )


# ---------------------------------------------------------------------------
# Department
# ---------------------------------------------------------------------------


class Department(UUIDMixin, TimestampMixin, Base):
    """A logical department within an Organization."""

    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="departments")
    parent: Mapped[Optional["Department"]] = relationship(
        "Department", remote_side="Department.id", back_populates="children"
    )
    children: Mapped[list["Department"]] = relationship(
        "Department", back_populates="parent"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="department")
    users: Mapped[list["User"]] = relationship(back_populates="department")

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_departments_org_name"),
        Index("ix_departments_organization_id", "organization_id"),
        Index("ix_departments_parent_department_id", "parent_department_id"),
    )


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class User(UUIDMixin, TimestampMixin, Base):
    """An authenticated principal belonging to an Organization (tenant)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.MEMBER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Tenant FK
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")
    department: Mapped[Optional["Department"]] = relationship(back_populates="users")
    group_memberships: Mapped[list["UserGroup"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserGroup.user_id",
    )
    owned_documents: Mapped[list["Document"]] = relationship(
        back_populates="owner", foreign_keys="Document.owner_id"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuthorizationAuditLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        Index("ix_users_email", "email"),
        Index("ix_users_tenant_id", "tenant_id"),
        Index("ix_users_is_active", "is_active"),
    )


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


class Group(UUIDMixin, TimestampMixin, Base):
    """A named collection of Users used for bulk permission assignment."""

    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="groups")
    memberships: Mapped[list["UserGroup"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_groups_org_name"),
        Index("ix_groups_organization_id", "organization_id"),
    )


# ---------------------------------------------------------------------------
# UserGroup (association table with metadata)
# ---------------------------------------------------------------------------


class UserGroup(UUIDMixin, TimestampMixin, Base):
    """Many-to-many between User and Group with join metadata."""

    __tablename__ = "user_groups"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="group_memberships", foreign_keys=[user_id]
    )
    group: Mapped["Group"] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "group_id", name="uq_user_groups_membership"),
        Index("ix_user_groups_user_id", "user_id"),
        Index("ix_user_groups_group_id", "group_id"),
    )


# ---------------------------------------------------------------------------
# Folder
# ---------------------------------------------------------------------------


class Folder(UUIDMixin, TimestampMixin, Base):
    """Hierarchical folder / namespace for Documents."""

    __tablename__ = "folders"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
    )
    openfga_resource_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="e.g. 'folder:uuid'"
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="folders")
    parent: Mapped[Optional["Folder"]] = relationship(
        "Folder", remote_side="Folder.id", back_populates="children"
    )
    children: Mapped[list["Folder"]] = relationship(
        "Folder", back_populates="parent", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="folder")

    __table_args__ = (
        Index("ix_folders_organization_id", "organization_id"),
        Index("ix_folders_parent_folder_id", "parent_folder_id"),
    )


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class Document(UUIDMixin, TimestampMixin, Base):
    """A governed document asset belonging to a tenant."""

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="document_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DocumentStatus.PENDING,
    )
    openfga_resource_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="e.g. 'document:uuid'"
    )

    # Tenant / structural FKs
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    department: Mapped[Optional["Department"]] = relationship(
        back_populates="documents"
    )
    folder: Mapped[Optional["Folder"]] = relationship(back_populates="documents")
    owner: Mapped["User"] = relationship(
        back_populates="owned_documents", foreign_keys=[owner_id]
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    access_logs: Mapped[list["DocumentAccessLog"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_department_id", "department_id"),
        Index("ix_documents_folder_id", "folder_id"),
        Index("ix_documents_owner_id", "owner_id"),
        Index("ix_documents_status", "status"),
    )


# ---------------------------------------------------------------------------
# DocumentChunk
# ---------------------------------------------------------------------------


class DocumentChunk(UUIDMixin, TimestampMixin, Base):
    """A contiguous text segment extracted from a Document during ingestion."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")
    embedding: Mapped[Optional["DocumentEmbedding"]] = relationship(
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_doc_idx"
        ),
        Index("ix_document_chunks_document_id", "document_id"),
    )


# ---------------------------------------------------------------------------
# DocumentEmbedding
# ---------------------------------------------------------------------------


class DocumentEmbedding(UUIDMixin, TimestampMixin, Base):
    """
    Vector embedding for a DocumentChunk.

    The HNSW index on the embedding column is created in the Alembic migration
    using:
        CREATE INDEX ix_document_embeddings_embedding_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """

    __tablename__ = "document_embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # Vector(384) matches EMBEDDING_DIMENSION in settings
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),
        nullable=False,
        comment="384-dim cosine embedding; HNSW index created in migration",
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    chunk: Mapped["DocumentChunk"] = relationship(back_populates="embedding")

    __table_args__ = (
        Index("ix_document_embeddings_chunk_id", "chunk_id"),
        # HNSW index is added raw in the migration because SQLAlchemy cannot
        # express the WITH (m=16, ef_construction=64) clause declaratively.
    )


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class Conversation(UUIDMixin, TimestampMixin, Base):
    """A chat session between a User and the RAG assistant."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conversations_user_id", "user_id"),
        Index("ix_conversations_tenant_id", "tenant_id"),
    )


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class Message(UUIDMixin, TimestampMixin, Base):
    """A single turn (human or assistant) within a Conversation."""

    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="'user' or 'assistant'"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_ids: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True, comment="UUIDs of DocumentChunks used for RAG context"
    )
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
    )


# ---------------------------------------------------------------------------
# IngestionJob
# ---------------------------------------------------------------------------


class IngestionJob(UUIDMixin, TimestampMixin, Base):
    """Tracks the asynchronous processing pipeline for a Document."""

    __tablename__ = "ingestion_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[IngestionStatus] = mapped_column(
        SAEnum(IngestionStatus, name="ingestion_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=IngestionStatus.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Completion percentage 0-100",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="ingestion_jobs")
    events: Mapped[list["IngestionEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_ingestion_jobs_document_id", "document_id"),
        Index("ix_ingestion_jobs_status", "status"),
    )


# ---------------------------------------------------------------------------
# IngestionEvent
# ---------------------------------------------------------------------------


class IngestionEvent(UUIDMixin, TimestampMixin, Base):
    """Append-only event log for each step of an IngestionJob pipeline."""

    __tablename__ = "ingestion_events"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    job: Mapped["IngestionJob"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_ingestion_events_job_id", "job_id"),
    )


# ---------------------------------------------------------------------------
# AuthorizationAuditLog
# ---------------------------------------------------------------------------


class AuthorizationAuditLog(UUIDMixin, TimestampMixin, Base):
    """
    Immutable audit trail for every authorization decision.

    Written by the OpenFGA middleware; never updated or deleted.
    """

    __tablename__ = "authorization_audit_logs"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("ix_auth_audit_logs_user_id", "user_id"),
        Index("ix_auth_audit_logs_tenant_id", "tenant_id"),
        Index("ix_auth_audit_logs_action", "action"),
        Index("ix_auth_audit_logs_allowed", "allowed"),
        Index("ix_auth_audit_logs_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# DocumentAccessLog
# ---------------------------------------------------------------------------


class DocumentAccessLog(UUIDMixin, TimestampMixin, Base):
    """Per-document fine-grained access log (read, search, download …)."""

    __tablename__ = "document_access_logs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    access_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g. 'read', 'search', 'download', 'delete'",
    )
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="access_logs")

    __table_args__ = (
        Index("ix_document_access_logs_document_id", "document_id"),
        Index("ix_document_access_logs_user_id", "user_id"),
        Index("ix_document_access_logs_tenant_id", "tenant_id"),
        Index("ix_document_access_logs_created_at", "created_at"),
    )
