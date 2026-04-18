"""SQLAlchemy ORM model for Document entity."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class DocumentDB(Base):
    """SQLAlchemy ORM model for uploaded documents.

    Stores metadata about PDF documents (annual reports) uploaded
    for RAG processing. File content is stored on disk; this model
    tracks the storage path and processing status.
    """

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="Unique document identifier (UUID string)",
    )
    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Linked stock ticker (FK to stocks)",
    )
    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original file name",
    )
    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Storage path for the PDF file",
    )
    page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of pages in the PDF",
    )
    processing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="Processing status: pending, processing, completed, failed",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        comment="Document metadata (year, report_type, company_name, filing_date)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last update timestamp",
    )

    def __repr__(self) -> str:
        """Return string representation of Document."""
        return (
            f"<DocumentDB(document_id={self.document_id}, "
            f"ticker={self.ticker}, status={self.processing_status})>"
        )
