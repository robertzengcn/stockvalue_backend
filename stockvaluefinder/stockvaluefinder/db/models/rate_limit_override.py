"""SQLAlchemy ORM model for rate_limit_overrides table.

Stores per-user rate limit overrides set by admins. Each user can have
at most one override (enforced by unique constraint on user_id).
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class RateLimitOverrideDB(Base):
    """SQLAlchemy ORM model for per-user rate limit overrides.

    Attributes:
        id: Unique identifier (UUID)
        user_id: Foreign key to users.id (unique, one override per user)
        limit: Maximum requests per window
        window_seconds: Window duration in seconds
        created_at: Record creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "rate_limit_overrides"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
        comment="Foreign key to users.id (one override per user)",
    )

    limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum requests per window",
    )

    window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Window duration in seconds",
    )

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
        """Return string representation of RateLimitOverrideDB."""
        return (
            f"<RateLimitOverrideDB("
            f"user_id={self.user_id}, "
            f"limit={self.limit}, "
            f"window_seconds={self.window_seconds}"
            f")>"
        )
