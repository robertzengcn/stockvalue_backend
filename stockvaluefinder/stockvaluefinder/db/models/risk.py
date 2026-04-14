"""SQLAlchemy ORM model for RiskScore entity."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class RiskScoreDB(Base):
    """SQLAlchemy ORM model representing RiskScore entity."""

    __tablename__ = "risk_scores"

    # Primary key
    score_id: Mapped[str] = mapped_column(
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

    report_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_reports.report_id"),
        nullable=False,
        unique=True,
        comment="Reference to FinancialReport",
    )

    # Risk assessment
    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Overall risk level (LOW, MEDIUM, HIGH, CRITICAL)",
    )

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc),
        comment="Calculation timestamp (UTC)",
    )

    # Beneish M-Score
    m_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Beneish M-Score value",
    )

    mscore_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="M-Score component data (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA)",
    )

    # Piotroski F-Score
    f_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Piotroski F-Score value (0-9)",
    )

    fscore_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="F-Score component data (9 binary signals)",
    )

    # 存贷双高
    存贷双高: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="High cash + high debt flag",
    )

    cash_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Cash and equivalents for 存贷双高 calculation",
    )

    debt_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Interest-bearing debt for 存贷双高 calculation",
    )

    cash_growth_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="YoY cash growth rate",
    )

    debt_growth_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="YoY debt growth rate",
    )

    # Goodwill risk
    goodwill_ratio: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Goodwill / Equity ratio (0-1)",
    )

    goodwill_excessive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if goodwill_ratio > 30%",
    )

    # Cash flow divergence
    profit_cash_divergence: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if net_income grew but OCF declined",
    )

    profit_growth: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="YoY profit growth rate",
    )

    ocf_growth: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="YoY operating cash flow growth rate",
    )

    # Red flags
    red_flags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of warning messages",
    )

    # LLM narrative (nullable - null when LLM unavailable)
    narrative: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="LLM-generated analysis narrative (JSON)",
    )

    def __repr__(self) -> str:
        """Return string representation of RiskScore."""
        return f"<RiskScoreDB(score_id={self.score_id}, ticker={self.ticker}, risk_level={self.risk_level})>"
