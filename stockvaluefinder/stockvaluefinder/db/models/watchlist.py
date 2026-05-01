"""SQLAlchemy ORM model for Watchlist entity."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class WatchlistDB(Base):
    """SQLAlchemy ORM model representing a stock in the user's watchlist.

    Tracks which stocks the user wants to monitor for new financial
    report disclosures. The watchlist is empty by default and must be
    populated explicitly via API (D-14).

    Attributes:
        ticker: Stock ticker, primary key (e.g., '600519.SH').
        name: Stock name or company name.
        added_at: Timestamp when the stock was added to the watchlist.
        is_active: Whether the stock is actively being monitored.
    """

    __tablename__ = "watchlist"

    ticker: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        comment="Stock ticker (PK, e.g. 600519.SH)",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Stock name or company name",
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when added to watchlist (UTC)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether the stock is actively being monitored",
    )

    def __repr__(self) -> str:
        """Return string representation of WatchlistDB."""
        return f"<WatchlistDB(ticker={self.ticker}, name={self.name})>"
