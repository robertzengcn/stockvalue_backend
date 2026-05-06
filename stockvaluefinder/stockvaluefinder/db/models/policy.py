"""SQLAlchemy ORM model for policy documents.

Stores metadata for uploaded policy PDF documents used by the
Policy Resonance Engine for semantic matching against stock
business descriptions.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class PolicyDocumentDB(Base):
    """SQLAlchemy ORM model for policy documents (D-10, D-12).

    Stores upload metadata for policy PDF documents including title,
    policy type, issuing body, effective date, and industry tags.
    Supports the Policy Resonance Engine's document management.

    Attributes:
        document_id: UUID primary key.
        title: Policy document title.
        policy_type: Type of policy (industry/fiscal/monetary/trade).
        issuing_body: Government body that issued the policy.
        effective_date: Date the policy takes effect, or None.
        industry_tags: JSONB list of industry tags.
        file_path: Server-side file path to the stored PDF.
        page_count: Number of pages in the PDF.
        chunk_count: Number of chunks generated from the PDF.
        upload_date: Timestamp when the document was uploaded.
        created_at: Record creation timestamp.
        updated_at: Record last-update timestamp.
    """

    __tablename__ = "policy_documents"

    # Primary key
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique document identifier",
    )

    # Policy metadata (D-10)
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Policy document title",
    )

    policy_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of policy (industry/fiscal/monetary/trade)",
    )

    issuing_body: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Government body that issued the policy",
    )

    effective_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date the policy takes effect",
    )

    industry_tags: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Industry tags relevant to this policy",
    )

    # File storage info
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Server-side file path to the stored PDF",
    )

    page_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of pages in the PDF",
    )

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of chunks generated from the PDF",
    )

    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the document was uploaded",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Record creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp",
    )

    def __repr__(self) -> str:
        """Return string representation of PolicyDocumentDB."""
        return (
            f"<PolicyDocumentDB("
            f"document_id={self.document_id}, "
            f"title={self.title!r}, "
            f"policy_type={self.policy_type!r})>"
        )
