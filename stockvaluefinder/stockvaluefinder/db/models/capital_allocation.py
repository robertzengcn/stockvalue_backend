"""SQLAlchemy ORM model for capital allocation scorecard results."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class CapitalAllocationScoreDB(Base):
    """SQLAlchemy ORM model for capital allocation scorecard results.

    Stores the output of capital allocation analysis (buyback yield,
    dividend stability, expansion discipline) for a given stock and
    fiscal year. Supports upsert by (ticker, fiscal_year).
    """

    __tablename__ = "capital_allocation_scores"

    # Primary key
    analysis_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    # Foreign key
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

    # Dimension results stored as JSONB
    buyback_yield_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Buyback yield dimension result",
    )

    dividend_stability_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Dividend stability dimension result",
    )

    expansion_discipline_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Expansion discipline dimension result",
    )

    # Combined scorecard
    overall_grade: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        comment="Overall capital allocation grade (A/B/C/D)",
    )

    weighting: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Weighting used for score calculation",
    )

    # Audit trail
    audit_trail: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Full audit trail with source data and calculation steps",
    )

    def __repr__(self) -> str:
        """Return string representation of CapitalAllocationScoreDB."""
        return (
            f"<CapitalAllocationScoreDB("
            f"analysis_id={self.analysis_id}, "
            f"ticker={self.ticker}, fiscal_year={self.fiscal_year})>"
        )
