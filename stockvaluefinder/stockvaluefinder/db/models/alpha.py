"""SQLAlchemy ORM model for Alpha composite score results."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class AlphaScoreDB(Base):
    """SQLAlchemy ORM model for Alpha composite score results.

    Stores the output of Alpha composite score analysis, which aggregates
    four forward-looking analysis dimensions (ROIC-WACC, Capital Allocation,
    Policy Resonance, Moat Trend) with fixed transparent weights (40/30/20/10).

    Supports upsert by (ticker, fiscal_year) via AlphaScoreRepository.
    """

    __tablename__ = "alpha_scores"

    # Primary key
    analysis_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    # Foreign key to stocks
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

    # Four normalized component scores
    roic_wacc_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="ROIC-WACC normalized score (0-100)",
    )

    roic_wacc_raw: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Original ROIC-WACC spread value",
    )

    capex_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Capital Allocation normalized score (0-100)",
    )

    capex_raw_grade: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        comment="Original capital allocation grade (A/B/C/D)",
    )

    policy_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Policy resonance score (0-100)",
    )

    policy_raw_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Original policy resonance score",
    )

    moat_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Moat trend normalized score (0-100)",
    )

    moat_raw_trend: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Original MoatTrend enum value",
    )

    # Composite score
    alpha_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Composite Alpha score (0-100)",
    )

    weights_used: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Weight configuration used",
    )

    dcf_adjustment_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="DCF adjustment details from policy resonance",
    )

    # Audit trail
    audit_trail: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Full audit trail",
    )

    def __repr__(self) -> str:
        """Return string representation of AlphaScoreDB."""
        return (
            f"<AlphaScoreDB("
            f"analysis_id={self.analysis_id}, "
            f"ticker={self.ticker}, fiscal_year={self.fiscal_year})>"
        )
