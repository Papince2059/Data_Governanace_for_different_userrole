"""
Document Ingestion Pipeline.
Handles validation, extraction, chunking, embedding, OpenFGA permission registration,
and pgvector indexing with event streaming.
"""
from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.exceptions import DocumentIngestionError
from src.core.logging import get_logger
from src.infrastructure.embeddings.local_embedder import LocalEmbedder
from src.infrastructure.openfga.client import OpenFGAClient
from src.ingestion.chunker import DocumentChunker

logger = get_logger(__name__)


class IngestionPipeline:
    """
    Executes the multi-stage document ingestion workflow.
    Guarantees that OpenFGA relationship tuples are committed BEFORE marking document active.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedder: LocalEmbedder,
        fga_client: OpenFGAClient,
        chunker: Optional[DocumentChunker] = None,
    ) -> None:
        self.db = db
        self.embedder = embedder
        self.fga = fga_client
        self.chunker = chunker or DocumentChunker()
        self.settings = get_settings()

    async def ingest_document(
        self,
        job_id: str,
        document_id: str,
        content: bytes,
        filename: str,
        department_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        viewer_group: Optional[str] = None,
    ) -> None:
        """Run full ingestion pipeline with event logging."""

        async def emit_event(status: str, progress: int, event_type: str, msg: str, data: dict):
            # Update job status and progress
            await self.db.execute(
                text("""
                    UPDATE ingestion_jobs
                    SET status = :status::ingestion_status, progress = :progress, updated_at = NOW()
                    WHERE id = :job_id::uuid
                """),
                {"status": status, "progress": progress, "job_id": job_id},
            )
            # Insert event
            await self.db.execute(
                text("""
                    INSERT INTO ingestion_events (id, job_id, event_type, message, metadata, created_at, updated_at)
                    VALUES (uuid_generate_v4(), :job_id::uuid, :event_type, :message, CAST(:meta AS jsonb), NOW(), NOW())
                """),
                {
                    "job_id": job_id,
                    "event_type": event_type,
                    "message": msg,
                    "meta": json.dumps(data),
                },
            )
            await self.db.commit()

        try:
            # Stage 1: Ingestion Started
            await emit_event("processing", 5, "ingestion.started", "Ingestion started", {"document_id": document_id})

            # Stage 2: Validate file format and size
            self._validate_file(content, filename)
            await emit_event("processing", 15, "document.validated", "Format and size validated", {"filename": filename})

            # Stage 3: Extract textual content
            text_content = self._extract_text(content, filename)
            if not text_content.strip():
                raise DocumentIngestionError("Document contains no readable text content.")
            await emit_event(
                "processing",
                30,
                "document.extracted",
                f"Extracted {len(text_content)} characters",
                {"char_count": len(text_content)},
            )

            # Stage 4: Store file locally
            file_path = await self._store_file_locally(content, filename, document_id)
            await self.db.execute(
                text("""
                    UPDATE documents
                    SET file_path = :file_path, file_size_bytes = :size, status = 'processing'::document_status, updated_at = NOW()
                    WHERE id = :doc_id::uuid
                """),
                {"file_path": file_path, "size": len(content), "doc_id": document_id},
            )
            await self.db.commit()

            # Stage 5: Chunk document
            chunks = self.chunker.chunk_text(text_content)
            await emit_event(
                "processing",
                45,
                "document.chunked",
                f"Generated {len(chunks)} text chunks",
                {"chunk_count": len(chunks)},
            )

            # Stage 6: Persist chunks into PostgreSQL
            created_chunk_items = []
            for chunk in chunks:
                chunk_uuid = str(uuid.uuid4())
                meta = {"word_count": chunk.word_count, "start_char": chunk.start_char, "end_char": chunk.end_char}
                await self.db.execute(
                    text("""
                        INSERT INTO document_chunks (id, document_id, chunk_index, content, chunk_metadata, created_at, updated_at)
                        VALUES (:id::uuid, :doc_id::uuid, :idx, :content, CAST(:meta AS jsonb), NOW(), NOW())
                    """),
                    {
                        "id": chunk_uuid,
                        "doc_id": document_id,
                        "idx": chunk.chunk_index,
                        "content": chunk.content,
                        "meta": json.dumps(meta),
                    },
                )
                created_chunk_items.append((chunk_uuid, chunk.content))
            await self.db.commit()

            # Stage 7: Generate embeddings locally
            raw_texts = [item[1] for item in created_chunk_items]
            embeddings = await self.embedder.aembed_batch(raw_texts)
            await emit_event(
                "processing",
                70,
                "embeddings.generated",
                f"Generated {len(embeddings)} vector embeddings",
                {"embedding_count": len(embeddings)},
            )

            # Stage 8: Store embeddings in pgvector
            model_name = self.settings.EMBEDDING_MODEL
            for (chunk_uuid, _), emb in zip(created_chunk_items, embeddings):
                emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                await self.db.execute(
                    text("""
                        INSERT INTO document_embeddings (id, chunk_id, embedding, model_name, created_at, updated_at)
                        VALUES (uuid_generate_v4(), :chunk_id::uuid, CAST(:emb AS vector), :model, NOW(), NOW())
                        ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding, updated_at = NOW()
                    """),
                    {"chunk_id": chunk_uuid, "emb": emb_str, "model": model_name},
                )
            await self.db.commit()

            # Stage 9: Register OpenFGA relationship tuples (BEFORE document is made active)
            doc_obj = f"document:{document_id}"

            # Owner relationship
            if owner_id:
                await self.fga.write_tuple(
                    user=f"user:{owner_id}",
                    relation="owner",
                    object=doc_obj,
                )

            # Department or Group access
            if viewer_group:
                await self.fga.write_tuple(
                    user=f"group:{viewer_group}#member",
                    relation="viewer",
                    object=doc_obj,
                )

            if folder_id:
                await self.fga.write_tuple(
                    user=f"folder:{folder_id}",
                    relation="parent_folder",
                    object=doc_obj,
                )

            if department_id:
                await self.fga.write_tuple(
                    user=f"department:{department_id}",
                    relation="parent_department",
                    object=doc_obj,
                )

            await emit_event(
                "processing",
                90,
                "permissions.created",
                "OpenFGA permission relationships established",
                {"document_id": document_id},
            )

            # Stage 10: Mark document ACTIVE and indexed
            await self.db.execute(
                text("""
                    UPDATE documents
                    SET status = 'active'::document_status, openfga_resource_id = :fga_id, updated_at = NOW()
                    WHERE id = :doc_id::uuid
                """),
                {"fga_id": doc_obj, "doc_id": document_id},
            )
            await self.db.commit()

            await emit_event(
                "processing",
                95,
                "document.indexed",
                "Document marked active and searchable",
                {"document_id": document_id},
            )

            # Stage 11: Ingestion Completed
            await emit_event(
                "completed",
                100,
                "ingestion.completed",
                "Document ingestion finished successfully",
                {"document_id": document_id, "chunks": len(chunks)},
            )
            logger.info("document_ingested_successfully", document_id=document_id, chunks=len(chunks))

        except Exception as e:
            logger.error("ingestion_pipeline_failed", document_id=document_id, error=str(e))
            await self.db.execute(
                text("""
                    UPDATE ingestion_jobs
                    SET status = 'failed'::ingestion_status, error_message = :err, updated_at = NOW()
                    WHERE id = :job_id::uuid
                """),
                {"err": str(e), "job_id": job_id},
            )
            await self.db.execute(
                text("""
                    INSERT INTO ingestion_events (id, job_id, event_type, message, metadata, created_at, updated_at)
                    VALUES (uuid_generate_v4(), :job_id::uuid, 'ingestion.failed', :msg, CAST(:meta AS jsonb), NOW(), NOW())
                """),
                {
                    "job_id": job_id,
                    "msg": str(e),
                    "meta": json.dumps({"error": str(e)[:300]}),
                },
            )
            # Mark document as failed
            await self.db.execute(
                text("""
                    UPDATE documents
                    SET status = 'failed'::document_status, updated_at = NOW()
                    WHERE id = :doc_id::uuid
                """),
                {"doc_id": document_id},
            )
            await self.db.commit()
            raise

    def _validate_file(self, content: bytes, filename: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in {".txt", ".pdf", ".docx"}:
            raise DocumentIngestionError(f"Unsupported file extension: {ext}. Allowed: .txt, .pdf, .docx")
        max_bytes = self.settings.document_max_size_bytes
        if len(content) > max_bytes:
            raise DocumentIngestionError(f"File exceeds maximum size of {self.settings.DOCUMENT_MAX_SIZE_MB}MB.")

    def _extract_text(self, content: bytes, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext == ".txt":
            return content.decode("utf-8", errors="replace")
        elif ext == ".pdf":
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                pages = [page.extract_text() or "" for page in reader.pages]
                return "\n\n".join(pages)
            except Exception as e:
                raise DocumentIngestionError(f"Failed to extract PDF content: {e}")
        elif ext == ".docx":
            try:
                import docx
                doc = docx.Document(io.BytesIO(content))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return "\n\n".join(paragraphs)
            except Exception as e:
                raise DocumentIngestionError(f"Failed to extract DOCX content: {e}")
        raise DocumentIngestionError(f"Unhandled file extension: {ext}")

    async def _store_file_locally(self, content: bytes, filename: str, document_id: str) -> str:
        upload_dir = Path(self.settings.DOCUMENT_UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = Path(filename).name
        target_path = upload_dir / document_id / safe_filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(target_path, "wb") as f:
            await f.write(content)
        return str(target_path)

