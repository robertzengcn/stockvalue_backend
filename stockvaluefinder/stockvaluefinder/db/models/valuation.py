"""SQLAlchemy ORM model for ValuationResult entity."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class ValuationResultDB(Base):
    """SQLAlchemy ORM model representing ValuationResult entity."""

    __tablename__ = "valuation_results"

    # Primary key
    valuation_id: Mapped[str] = mapped_column(
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

    # Valuation results
    current_price: Mapped[float] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        comment="Current market price per share",
    )

    intrinsic_value: Mapped[float] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        comment="Calculated intrinsic value per share",
    )

    wacc: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Weighted average cost of capital",
    )

    margin_of_safety: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Margin of safety (intrinsic - price) / price",
    )

    valuation_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Valuation level (UNDERVALUED, FAIR_VALUE, OVERVALUED)",
    )

    # DCF parameters (stored as JSONB for flexibility)
    dcf_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="DCF parameters used in calculation",
    )

    # Audit trail (full calculation details)
    audit_trail: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Full calculation audit trail",
    )

    # Metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        default=datetime.utcnow,
        comment="Calculation timestamp",
    )

    def __repr__(self) -> str:
        """Return string representation of ValuationResult."""
        return f"<ValuationResultDB(valuation_id={self.valuation_id}, ticker={self.ticker}, valuation_level={self.valuation_level})>"
