"""Repository for Document data access."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.document import DocumentDB
from stockvaluefinder.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[DocumentDB, Any, Any]):
    """Repository for Document data access with domain-specific queries.

    Provides CRUD operations for document metadata, including queries
    by ticker, document_id, and processing status.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize DocumentRepository with DocumentDB model.

        Args:
            session: Async database session
        """
        super().__init__(DocumentDB, session)

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentDB]:
        """Get all documents for a specific stock ticker.

        Args:
            ticker: Stock ticker symbol (e.g., '600519.SH')
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of DocumentDB instances ordered by created_at descending
        """
        result = await self.session.execute(
            select(DocumentDB)
            .where(DocumentDB.ticker == ticker.upper())
            .order_by(DocumentDB.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_document_id(self, document_id: str) -> DocumentDB | None:
        """Get a document by its unique identifier.

        Args:
            document_id: UUID string of the document

        Returns:
            DocumentDB instance if found, None otherwise
        """
        result = await self.session.execute(
            select(DocumentDB).where(DocumentDB.document_id == document_id)
        )
        return result.scalars().first()

    async def get_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentDB]:
        """Get all documents with a specific processing status.

        Args:
            status: Processing status to filter by
                    (pending, processing, completed, failed)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of DocumentDB instances with matching status
        """
        result = await self.session.execute(
            select(DocumentDB)
            .where(DocumentDB.processing_status == status)
            .order_by(DocumentDB.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create_document(
        self,
        ticker: str,
        file_name: str,
        file_path: str,
        page_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentDB:
        """Create a new document record with explicit parameters.

        Args:
            ticker: Stock ticker this document belongs to
            file_name: Original uploaded file name
            file_path: Storage path for the PDF file
            page_count: Number of pages in the PDF
            metadata: Optional document metadata dict

        Returns:
            Created DocumentDB instance
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        document = DocumentDB(
            document_id=str(uuid4()),
            ticker=ticker.upper(),
            file_name=file_name,
            file_path=file_path,
            page_count=page_count,
            processing_status="pending",
            metadata_=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def update_status(
        self,
        document_id: str,
        status: str,
    ) -> DocumentDB | None:
        """Update the processing status of a document.

        Args:
            document_id: UUID string of the document to update
            status: New processing status
                    (pending, processing, completed, failed)

        Returns:
            Updated DocumentDB instance if found, None otherwise
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.execute(
            update(DocumentDB)
            .where(DocumentDB.document_id == document_id)
            .values(processing_status=status, updated_at=now)
        )
        return await self.get_by_document_id(document_id)

    async def update_metadata(
        self,
        document_id: str,
        metadata: dict[str, Any],
    ) -> DocumentDB | None:
        """Update the metadata JSONB field of a document.

        Args:
            document_id: UUID string of the document to update
            metadata: New metadata dict to replace existing metadata

        Returns:
            Updated DocumentDB instance if found, None otherwise
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.execute(
            update(DocumentDB)
            .where(DocumentDB.document_id == document_id)
            .values(metadata_=metadata, updated_at=now)
        )
        return await self.get_by_document_id(document_id)
