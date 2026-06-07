"""SQLAlchemy ORM models for equity pledge tables.

Two tables:
- equity_pledge_snapshots: company-level pledge summary per stock/date/source
- equity_pledge_details: per-shareholder pledge detail records
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from stockvaluefinder.db.base import Base


class EquityPledgeSnapshotDB(Base):
    """SQLAlchemy ORM model for company-level equity pledge summary.

    Stores aggregate pledge data for a single stock on a given trade date,
    uniquely keyed by (ticker, latest_date, source) to support multi-source
    data collection.

    Attributes:
        snapshot_id: UUID primary key.
        ticker: Stock code (FK to stocks.ticker).
        latest_date: Trade date of the pledge data.
        stock_name: Company name at snapshot time.
        company_pledge_ratio: Company pledge ratio as percentage.
        pledged_shares: Total pledged shares.
        pledge_market_value: Market value of pledged shares.
        pledge_count: Number of pledge transactions.
        unrestricted_pledged_shares: Unrestricted shares pledged.
        restricted_pledged_shares: Restricted shares pledged.
        one_year_price_change: One-year price change as percentage.
        source: Data source identifier (e.g., 'akshare').
        source_raw: Raw API response for audit traceability (DB-04).
        fetched_at: Timestamp when data was fetched from source.
        created_at: Record creation timestamp (server-side default).
    """

    __tablename__ = "equity_pledge_snapshots"

    __table_args__ = (
        UniqueConstraint(
            "ticker",
            "latest_date",
            "source",
            name="uq_pledge_snapshot_ticker_date_src",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.ticker"),
        nullable=False,
        index=True,
        comment="Stock code (FK to stocks)",
    )

    latest_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Trade date of the pledge data",
    )

    stock_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Company name at snapshot time",
    )

    company_pledge_ratio: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Company pledge ratio as percentage",
    )

    pledged_shares: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4),
        nullable=True,
        comment="Total pledged shares",
    )

    pledge_market_value: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4),
        nullable=True,
        comment="Market value of pledged shares",
    )

    pledge_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of pledge transactions",
    )

    unrestricted_pledged_shares: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4),
        nullable=True,
        comment="Unrestricted shares pledged",
    )

    restricted_pledged_shares: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4),
        nullable=True,
        comment="Restricted shares pledged",
    )

    one_year_price_change: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="One-year price change as percentage",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Data source identifier (e.g., 'akshare')",
    )

    source_raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw API response for audit traceability (DB-04)",
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when data was fetched from source",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of EquityPledgeSnapshotDB."""
        return (
            f"<EquityPledgeSnapshotDB("
            f"snapshot_id={self.snapshot_id}, "
            f"ticker={self.ticker}, "
            f"latest_date={self.latest_date})>"
        )


class EquityPledgeDetailDB(Base):
    """SQLAlchemy ORM model for per-shareholder pledge detail records.

    Stores individual pledge records for important shareholders, including
    controlling shareholders. Supports closeout risk analysis with
    price-related fields.

    Attributes:
        detail_id: UUID primary key.
        ticker: Stock code (FK to stocks.ticker).
        holder_name: Shareholder name.
        is_controlling_holder: Whether this is the controlling shareholder.
        pledge_amount: Number of shares pledged in this record.
        pledged_to_holding_ratio: Pledged / holding ratio as percentage.
        pledged_to_total_share_ratio: Pledged / total shares ratio as percentage.
        pledgee: Pledgee institution name.
        latest_price: Latest stock price.
        pledge_date_close_price: Stock closing price on pledge date.
        estimated_closeout_price: Estimated forced-sell price.
        start_date: Pledge start date.
        announcement_date: Announcement date.
        stock_name: Stock name.
        source: Data source identifier.
        source_raw: Raw API response for audit traceability (DB-04).
        fetched_at: Timestamp when data was fetched from source.
        created_at: Record creation timestamp (server-side default).
    """

    __tablename__ = "equity_pledge_details"

    __table_args__ = (
        Index(
            "ix_pledge_detail_ticker_date",
            "ticker",
            "announcement_date",
        ),
        Index(
            "ix_pledge_detail_ticker_holder",
            "ticker",
            "holder_name",
        ),
    )

    detail_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.ticker"),
        nullable=False,
        index=True,
        comment="Stock code (FK to stocks)",
    )

    holder_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Shareholder name",
    )

    is_controlling_holder: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the controlling shareholder",
    )

    pledge_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 4),
        nullable=True,
        comment="Number of shares pledged in this record",
    )

    pledged_to_holding_ratio: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Pledged / holding ratio as percentage",
    )

    pledged_to_total_share_ratio: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Pledged / total shares ratio as percentage",
    )

    pledgee: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Pledgee institution name",
    )

    latest_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Latest stock price",
    )

    pledge_date_close_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Stock closing price on pledge date",
    )

    estimated_closeout_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated forced-sell price",
    )

    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Pledge start date",
    )

    announcement_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Announcement date",
    )

    stock_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Stock name",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Data source identifier",
    )

    source_raw: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw API response for audit traceability (DB-04)",
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when data was fetched from source",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of EquityPledgeDetailDB."""
        return (
            f"<EquityPledgeDetailDB("
            f"detail_id={self.detail_id}, "
            f"ticker={self.ticker}, "
            f"holder_name={self.holder_name})>"
        )
