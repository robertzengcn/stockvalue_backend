"""SQLAlchemy ORM model for Stock entity."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class StockDB(Base):
    """SQLAlchemy ORM model representing Stock entity."""

    __tablename__ = "stocks"

    # Primary key
    ticker: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        index=True,
        comment="Stock code (e.g., '600519.SH', '0700.HK')",
    )

    # Company information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Company name",
    )

    market: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Market enum (A_SHARE, HK_SHARE)",
    )

    industry: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Industry sector",
    )

    list_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Listing date",
    )

    # Timestamps
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
        """Return string representation of Stock."""
        return f"<Stock(ticker={self.ticker}, name={self.name}, market={self.market})>"
