"""PipelineDocumentRepository for pipeline_documents CRUD operations.

Provides database operations for the pipeline_documents table:
- Create document records with metadata (source URL, SHA256 hash, file path, size)
- Query by content_hash for deduplication
- Query by source_id for deduplication
- Query by task_id for document lookup

Follows the same patterns as PipelineTaskRepository in repo.py.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.pipeline_document import PipelineDocumentDB

logger = logging.getLogger(__name__)


class PipelineDocumentRepository:
    """Repository for pipeline document database operations.

    Manages metadata records for downloaded financial report PDFs.
    Each record tracks the source URL, content hash (SHA256), file path,
    and file size for deduplication and audit purposes.

    The caller controls commit/rollback via the session lifecycle.

    Args:
        session: Async database session for all operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Async database session for all operations.
        """
        self._session = session
        self._model = PipelineDocumentDB

    async def create_document(
        self,
        task_id: str,
        source_url: str | None = None,
        source_id: str | None = None,
        content_hash: str | None = None,
        file_path: str | None = None,
        file_size: int | None = None,
    ) -> PipelineDocumentDB:
        """Create a new pipeline document record.

        Args:
            task_id: Foreign key to the pipeline task.
            source_url: URL where the document was downloaded from.
            source_id: Announcement/source identifier for deduplication.
            content_hash: SHA256 hash of the document content.
            file_path: Local filesystem path where the file is stored.
            file_size: Size of the file in bytes.

        Returns:
            Created PipelineDocumentDB instance.
        """
        doc = PipelineDocumentDB(
            document_id=uuid4(),
            task_id=task_id,
            source_url=source_url,
            source_id=source_id,
            content_hash=content_hash,
            file_path=file_path,
            file_size=file_size,
            downloaded_at=datetime.now(timezone.utc),
        )
        self._session.add(doc)
        await self._session.flush()
        await self._session.refresh(doc)

        logger.info(
            "Created pipeline document",
            extra={
                "document_id": str(doc.document_id),
                "task_id": task_id,
                "source_id": source_id,
                "content_hash": content_hash,
            },
        )
        return doc

    async def get_by_content_hash(self, content_hash: str) -> PipelineDocumentDB | None:
        """Find a document by its SHA256 content hash.

        Used for deduplication: if a document with the same content hash
        already exists, the download can be skipped.

        Args:
            content_hash: SHA256 hex digest to search for.

        Returns:
            Matching PipelineDocumentDB or None if not found.
        """
        stmt = select(self._model).where(self._model.content_hash == content_hash)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_source_id(self, source_id: str) -> PipelineDocumentDB | None:
        """Find a document by its source announcement ID.

        Used for deduplication: if a document from the same announcement
        already exists, the download can be skipped.

        Args:
            source_id: Announcement/source identifier.

        Returns:
            Matching PipelineDocumentDB or None if not found.
        """
        stmt = select(self._model).where(self._model.source_id == source_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_task_id(self, task_id: str) -> PipelineDocumentDB | None:
        """Find a document by its associated pipeline task ID.

        Args:
            task_id: UUID of the pipeline task.

        Returns:
            Matching PipelineDocumentDB or None if not found.
        """
        stmt = select(self._model).where(self._model.task_id == task_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["PipelineDocumentRepository"]
