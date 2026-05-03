"""SQLAlchemy ORM model for ROIC analysis results."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class ROICResultDB(Base):
    """SQLAlchemy ORM model representing ROIC-WACC spread analysis results.

    Stores the output of ROIC, WACC, and spread calculations for a given
    stock and fiscal year. Supports upsert by (ticker, fiscal_year) to
    allow re-calculation without duplicate records.
    """

    __tablename__ = "roic_results"

    # Primary key
    analysis_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    # Foreign keys
    ticker: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.ticker"),
        nullable=False,
        index=True,
        comment="Stock code (foreign key)",
    )

    fiscal_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Fiscal year of analysis",
    )

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),
        comment="Calculation timestamp (UTC)",
    )

    # ROIC core metrics
    roic: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="ROIC value (None if negative invested capital)",
    )

    negative_invested_capital: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if invested capital is negative (ROIC meaningless)",
    )

    nopat: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Net Operating Profit After Tax",
    )

    invested_capital: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Invested capital (equity + debt - cash)",
    )

    # WACC
    wacc: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Weighted Average Cost of Capital",
    )

    wacc_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="WACC component breakdown (risk_free_rate, beta, erp, etc.)",
    )

    # Spread
    spread: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="ROIC - WACC spread (None if ROIC is None)",
    )

    spread_classification: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Spread classification (e.g. strong_moat, value_creator)",
    )

    # Trend data
    moat_trend: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Moat trend analysis with multi-year ROIC data",
    )

    # Metadata
    is_financial_sector: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if stock is in financial sector (different NOPAT formula)",
    )

    audit_trail: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Audit trail with source data and calculation steps",
    )

    def __repr__(self) -> str:
        """Return string representation of ROICResult."""
        return (
            f"<ROICResultDB(analysis_id={self.analysis_id}, "
            f"ticker={self.ticker}, fiscal_year={self.fiscal_year})>"
        )
