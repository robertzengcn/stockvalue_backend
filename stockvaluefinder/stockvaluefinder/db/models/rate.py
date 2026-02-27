"""SQLAlchemy ORM model for RateData entity."""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class RateDataDB(Base):
    """SQLAlchemy ORM model representing RateData entity."""

    __tablename__ = "rate_data"

    # Primary key
    rate_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="Unique identifier",
    )

    # Rate data
    rate_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="Date of rate",
    )

    ten_year_treasury: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="10-year government bond yield",
    )

    three_year_deposit: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="3-year large deposit rate",
    )

    one_year_deposit: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="1-year deposit rate",
    )

    benchmark_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Central bank benchmark rate",
    )

    rate_source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Source of data (PBOC, HKMA, etc.)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )

    def __repr__(self) -> str:
        """Return string representation of RateData."""
        return f"<RateDataDB(rate_id={self.rate_id}, rate_date={self.rate_date})>"
