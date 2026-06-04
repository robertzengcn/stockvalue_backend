"""SQLAlchemy ORM model for IndexConstituent entity."""

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class IndexConstituentDB(Base):
    """SQLAlchemy ORM model representing an index constituent.

    Tracks which stocks belong to which index (CSI 300, CSI 500) at any
    given point in time. Supports historical change tracking via
    effective_date and removed_date fields.

    Note: No FK to stocks.ticker because constituent sync may run before
    stock records exist in the database.

    Attributes:
        constituent_id: UUID primary key.
        index_code: Index pool identifier (e.g., CSI300, CSI500).
        ticker: Stock code (e.g., 600519.SH). No FK to stocks.ticker.
        name: Company name.
        effective_date: Date when this constituent became active in the index.
        removed_date: Date when this constituent was removed (None if still active).
        is_active: Whether this constituent is currently in the index.
        source: Data source identifier (e.g., akshare).
        source_raw: Raw data from source (JSONB).
        created_at: Record creation timestamp (UTC).
        updated_at: Record last-update timestamp (UTC).
    """

    __tablename__ = "index_constituents"

    __table_args__ = (
        UniqueConstraint(
            "index_code",
            "ticker",
            "effective_date",
            name="uq_idx_ticker_date",
        ),
        Index("ix_idx_const_code_active", "index_code", "is_active"),
        Index("ix_idx_const_ticker_active", "ticker", "is_active"),
    )

    constituent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    index_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Index pool identifier (e.g., CSI300, CSI500)",
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Stock code (e.g., 600519.SH)",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Company name",
    )

    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date when constituent became active in index",
    )

    removed_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date when constituent was removed from index",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Whether constituent is currently in the index",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="akshare",
        comment="Data source identifier",
    )

    source_raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw data from source",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Record creation timestamp (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of IndexConstituentDB."""
        return (
            f"<IndexConstituentDB("
            f"constituent_id={self.constituent_id}, "
            f"index_code={self.index_code}, ticker={self.ticker})>"
        )
