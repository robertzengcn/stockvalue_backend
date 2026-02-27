"""SQLAlchemy ORM model for YieldGap entity."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class YieldGapDB(Base):
    """SQLAlchemy ORM model representing YieldGap entity."""

    __tablename__ = "yield_gaps"

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

    # Price information
    cost_basis: Mapped[float] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        comment="Purchase price per share",
    )

    current_price: Mapped[float] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        comment="Current market price per share",
    )

    # Dividend yield
    gross_dividend_yield: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Gross dividend yield (before tax)",
    )

    net_dividend_yield: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Net dividend yield (after tax)",
    )

    # Risk-free rates
    risk_free_bond_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="10-year treasury bond rate",
    )

    risk_free_deposit_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="3-year large deposit rate",
    )

    # Analysis result
    yield_gap: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Yield gap: net_yield - max(bond, deposit)",
    )

    recommendation: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Investment recommendation (ATTRACTIVE, NEUTRAL, UNATTRACTIVE)",
    )

    market: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Market (A_SHARE or HK_SHARE)",
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
        """Return string representation of YieldGap."""
        return f"<YieldGapDB(analysis_id={self.analysis_id}, ticker={self.ticker}, yield_gap={self.yield_gap})>"
