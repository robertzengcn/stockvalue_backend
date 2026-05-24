"""SQLAlchemy ORM model for UserStockAccess entity."""

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class UserStockAccessDB(Base):
    """SQLAlchemy ORM model for per-user stock access control entries.

    Each row represents a ticker that a user is explicitly allowed to access.
    When a user has NO rows in this table, they can access ALL stocks (ACCL-03
    default open). When they have at least one row, access is restricted to
    only those tickers.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to users.id (stored as String)
        ticker: Permitted stock ticker (e.g., "600519.SH")
        created_at: Record creation timestamp
    """

    __tablename__ = "user_stock_access"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="Foreign key to users.id",
    )

    ticker: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        comment="Permitted stock ticker (e.g., 600519.SH)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "user_id",
            "ticker",
            name="uq_user_stock_access_user_ticker",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of UserStockAccessDB."""
        return f"<UserStockAccessDB(user_id={self.user_id}, ticker={self.ticker})>"
