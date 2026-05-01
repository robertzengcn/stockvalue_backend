"""SQLAlchemy ORM model for PipelineDocument entity."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class PipelineDocumentDB(Base):
    """SQLAlchemy ORM model representing a pipeline document.

    Stores metadata about downloaded financial report documents.
    Document records persist across task retries to avoid re-downloading.

    Attributes:
        document_id: UUID primary key.
        task_id: Foreign key to the pipeline task.
        source_url: URL where the document was downloaded from.
        source_id: Announcement/source identifier for deduplication.
        content_hash: SHA256 hash of the document content.
        file_path: Local filesystem path where the file is stored.
        file_size: Size of the file in bytes.
        downloaded_at: Timestamp when the document was downloaded.
    """

    __tablename__ = "pipeline_documents"

    # Primary key
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique document identifier",
    )

    # Foreign key to pipeline tasks
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_tasks.task_id"),
        nullable=False,
        index=True,
        comment="Foreign key to pipeline task",
    )

    # Source information
    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="URL where the document was downloaded from",
    )

    source_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Announcement/source identifier for deduplication",
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA256 hash of the document content",
    )

    # File information
    file_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Local filesystem path where the file is stored",
    )

    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Size of the file in bytes",
    )

    downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the document was downloaded",
    )

    def __repr__(self) -> str:
        """Return string representation of PipelineDocument."""
        return (
            f"<PipelineDocumentDB(document_id={self.document_id}, "
            f"task_id={self.task_id})>"
        )
