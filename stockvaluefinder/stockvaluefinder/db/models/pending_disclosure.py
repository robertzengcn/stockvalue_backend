"""SQLAlchemy ORM model for PendingDisclosure entity."""

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class PendingDisclosureDB(Base):
    """SQLAlchemy ORM model representing a staged disclosure awaiting processing.

    The pending_disclosures table acts as a staging area between polling
    and processing. The cron job writes raw disclosure data here, and a
    separate worker job reads from this table to detect new vs. amended
    reports and enqueue download jobs (D-11).

    Attributes:
        disclosure_id: UUID primary key.
        poll_id: UUID linking disclosures from the same poll cycle.
        ticker: Stock ticker (e.g., '600519.SH').
        stock_name: Stock name or company name (optional).
        report_type: Type of report ('annual', 'semi_annual', 'q1', 'q3').
        fiscal_year: Fiscal year of the report.
        disclosure_date: Actual disclosure date (if available).
        first_appointment: First appointment date from disclosure schedule.
        source: Data source ('akshare' or 'cninfo').
        source_raw: Raw source data for debugging/audit.
        processed: Whether this disclosure has been processed.
        created_at: Timestamp when the record was created.
        processed_at: Timestamp when the record was processed.
    """

    __tablename__ = "pending_disclosures"

    disclosure_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique disclosure identifier",
    )

    poll_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="UUID linking disclosures from the same poll cycle",
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Stock ticker (e.g. 600519.SH)",
    )

    stock_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Stock name or company name",
    )

    report_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Report type: annual, semi_annual, q1, q3",
    )

    fiscal_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Fiscal year of the report",
    )

    disclosure_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Actual disclosure date (if disclosed)",
    )

    first_appointment: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="First appointment date from disclosure schedule",
    )

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Data source: akshare or cninfo",
    )

    source_raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw source data for debugging/audit",
    )

    processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether this disclosure has been processed",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Record creation timestamp (UTC)",
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the record was processed (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of PendingDisclosureDB."""
        return (
            f"<PendingDisclosureDB(disclosure_id={self.disclosure_id}, "
            f"ticker={self.ticker}, report_type={self.report_type})>"
        )
