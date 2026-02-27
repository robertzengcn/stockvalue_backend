"""SQLAlchemy ORM model for DividendData entity."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class DividendDataDB(Base):
    """SQLAlchemy ORM model representing DividendData entity."""

    __tablename__ = "dividend_data"

    # Primary key
    dividend_id: Mapped[str] = mapped_column(
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

    # Dividend information
    ex_dividend_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Ex-dividend date",
    )

    dividend_per_share: Mapped[float] = mapped_column(
        Numeric(20, 4),
        nullable=False,
        comment="Dividend amount per share (CNY/HKD)",
    )

    dividend_frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Dividend frequency (ANNUAL, SEMI_ANNUAL, QUARTERLY, SPECIAL)",
    )

    fiscal_year: Mapped[int | None] = mapped_column(
        Numeric(4, 0),
        nullable=True,
        comment="Fiscal year of dividend payment",
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last update timestamp",
    )

    def __repr__(self) -> str:
        """Return string representation of DividendData."""
        return f"<DividendDataDB(dividend_id={self.dividend_id}, ticker={self.ticker}, ex_dividend_date={self.ex_dividend_date})>"
