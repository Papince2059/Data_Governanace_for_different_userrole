"""Initial schema – creates all tables, indexes, and extensions.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic
revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ------------------------------------------------------------------
    # PostgreSQL extensions
    # ------------------------------------------------------------------
    op.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    op.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # ------------------------------------------------------------------
    # Enum types (idempotent creation)
    # ------------------------------------------------------------------
    op.execute(text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                CREATE TYPE user_role AS ENUM ('admin', 'member');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
                CREATE TYPE document_status AS ENUM ('pending', 'processing', 'active', 'failed', 'deleted');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ingestion_status') THEN
                CREATE TYPE ingestion_status AS ENUM ('pending', 'processing', 'completed', 'failed');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_action') THEN
                CREATE TYPE audit_action AS ENUM (
                    'access_granted', 'access_denied', 'permission_granted', 'permission_revoked',
                    'document_uploaded', 'document_deleted', 'login_success', 'login_failed'
                );
            END IF;
        END $$;
    """))

    # ------------------------------------------------------------------
    # organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("settings", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_is_active", "organizations", ["is_active"])

    # ------------------------------------------------------------------
    # departments
    # ------------------------------------------------------------------
    op.create_table(
        "departments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("organization_id", "name", name="uq_departments_org_name"),
    )
    op.create_index(
        "ix_departments_organization_id", "departments", ["organization_id"]
    )
    op.create_index(
        "ix_departments_parent_department_id",
        "departments",
        ["parent_department_id"],
    )

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "member", name="user_role", create_type=False),
            nullable=False,
            server_default="member",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # ------------------------------------------------------------------
    # groups
    # ------------------------------------------------------------------
    op.create_table(
        "groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("organization_id", "name", name="uq_groups_org_name"),
    )
    op.create_index("ix_groups_organization_id", "groups", ["organization_id"])

    # ------------------------------------------------------------------
    # user_groups
    # ------------------------------------------------------------------
    op.create_table(
        "user_groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "added_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_groups_membership"),
    )
    op.create_index("ix_user_groups_user_id", "user_groups", ["user_id"])
    op.create_index("ix_user_groups_group_id", "user_groups", ["group_id"])

    # ------------------------------------------------------------------
    # folders
    # ------------------------------------------------------------------
    op.create_table(
        "folders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("openfga_resource_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_folders_organization_id", "folders", ["organization_id"])
    op.create_index("ix_folders_parent_folder_id", "folders", ["parent_folder_id"])

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "active",
                "failed",
                "deleted",
                name="document_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("openfga_resource_id", sa.String(255), nullable=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_department_id", "documents", ["department_id"])
    op.create_index("ix_documents_folder_id", "documents", ["folder_id"])
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_documents_status", "documents", ["status"])

    # ------------------------------------------------------------------
    # document_chunks
    # ------------------------------------------------------------------
    op.create_table(
        "document_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB, nullable=True),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_doc_idx"
        ),
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )

    # ------------------------------------------------------------------
    # document_embeddings  (pgvector)
    # ------------------------------------------------------------------
    op.create_table(
        "document_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # The vector column type is provided by pgvector; we use sa.Text as a
        # placeholder type descriptor and override it with a raw DDL string.
        sa.Column(
            "embedding",
            sa.Text,
            nullable=False,
            comment="384-dim float vector; actual type overridden below",
        ),
        sa.Column("model_name", sa.String(255), nullable=False),
    )

    # Alter the embedding column to use the proper vector(384) type now that
    # the vector extension is available.
    op.execute(
        text(
            "ALTER TABLE document_embeddings "
            "ALTER COLUMN embedding TYPE vector(384) "
            "USING embedding::vector(384)"
        )
    )

    op.create_index(
        "ix_document_embeddings_chunk_id", "document_embeddings", ["chunk_id"]
    )

    # HNSW index for approximate nearest-neighbour cosine search
    op.execute(
        text(
            """
            CREATE INDEX ix_document_embeddings_embedding_hnsw
            ON document_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        )
    )

    # ------------------------------------------------------------------
    # conversations
    # ------------------------------------------------------------------
    op.create_table(
        "conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])

    # ------------------------------------------------------------------
    # messages
    # ------------------------------------------------------------------
    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("source_chunk_ids", postgresql.JSONB, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
    )
    op.create_index(
        "ix_messages_conversation_id", "messages", ["conversation_id"]
    )

    # ------------------------------------------------------------------
    # ingestion_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "ingestion_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="ingestion_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "progress",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Completion percentage 0-100",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])

    # ------------------------------------------------------------------
    # ingestion_events
    # ------------------------------------------------------------------
    op.create_table(
        "ingestion_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingestion_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_ingestion_events_job_id", "ingestion_events", ["job_id"])

    # ------------------------------------------------------------------
    # authorization_audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "authorization_audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action",
            sa.Enum(
                "access_granted",
                "access_denied",
                "permission_granted",
                "permission_revoked",
                "document_uploaded",
                "document_deleted",
                "login_success",
                "login_failed",
                name="audit_action",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("allowed", sa.Boolean, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_auth_audit_logs_user_id", "authorization_audit_logs", ["user_id"]
    )
    op.create_index(
        "ix_auth_audit_logs_tenant_id", "authorization_audit_logs", ["tenant_id"]
    )
    op.create_index(
        "ix_auth_audit_logs_action", "authorization_audit_logs", ["action"]
    )
    op.create_index(
        "ix_auth_audit_logs_allowed", "authorization_audit_logs", ["allowed"]
    )
    op.create_index(
        "ix_auth_audit_logs_created_at", "authorization_audit_logs", ["created_at"]
    )

    # ------------------------------------------------------------------
    # document_access_logs
    # ------------------------------------------------------------------
    op.create_table(
        "document_access_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=text("uuid_generate_v4()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("access_type", sa.String(50), nullable=False),
        sa.Column("allowed", sa.Boolean, nullable=False),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index(
        "ix_document_access_logs_document_id", "document_access_logs", ["document_id"]
    )
    op.create_index(
        "ix_document_access_logs_user_id", "document_access_logs", ["user_id"]
    )
    op.create_index(
        "ix_document_access_logs_tenant_id", "document_access_logs", ["tenant_id"]
    )
    op.create_index(
        "ix_document_access_logs_created_at", "document_access_logs", ["created_at"]
    )

    # ------------------------------------------------------------------
    # updated_at auto-refresh trigger (applied to every table)
    # ------------------------------------------------------------------
    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    _tables_with_updated_at = [
        "organizations",
        "departments",
        "users",
        "groups",
        "user_groups",
        "folders",
        "documents",
        "document_chunks",
        "document_embeddings",
        "conversations",
        "messages",
        "ingestion_jobs",
        "ingestion_events",
        "authorization_audit_logs",
        "document_access_logs",
    ]
    for tbl in _tables_with_updated_at:
        op.execute(
            text(
                f"""
                CREATE TRIGGER trg_{tbl}_updated_at
                BEFORE UPDATE ON {tbl}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
                """
            )
        )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("document_access_logs")
    op.drop_table("authorization_audit_logs")
    op.drop_table("ingestion_events")
    op.drop_table("ingestion_jobs")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("document_embeddings")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("folders")
    op.drop_table("user_groups")
    op.drop_table("groups")
    op.drop_table("users")
    op.drop_table("departments")
    op.drop_table("organizations")

    # Drop trigger function
    op.execute(text("DROP FUNCTION IF EXISTS set_updated_at CASCADE"))

    # Drop enum types
    op.execute(text("DROP TYPE IF EXISTS audit_action"))
    op.execute(text("DROP TYPE IF EXISTS ingestion_status"))
    op.execute(text("DROP TYPE IF EXISTS document_status"))
    op.execute(text("DROP TYPE IF EXISTS user_role"))
