"""SQLAlchemy ORM model for WatcherState entity."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class WatcherStateDB(Base):
    """SQLAlchemy ORM model representing the watcher's operational state.

    Tracks the last poll time, success/failure status of data sources,
    and cumulative poll/error counts for observability. Updated each
    poll cycle by the watcher cron function.

    Attributes:
        watcher_id: Unique identifier for the watcher instance (default 'default').
        last_poll_time: Timestamp of the most recent poll cycle.
        last_akshare_success: Whether the last AKShare poll succeeded.
        last_cninfo_fallback: Whether CNInfo fallback was used.
        polls_count: Total number of poll cycles completed.
        errors_count: Total number of errors encountered.
        updated_at: Timestamp of the last state update.
    """

    __tablename__ = "watcher_state"

    watcher_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        default="default",
        comment="Watcher instance identifier",
    )

    last_poll_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the most recent poll cycle (UTC)",
    )

    last_akshare_success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the last AKShare poll succeeded",
    )

    last_cninfo_fallback: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether CNInfo fallback was used in the last poll",
    )

    polls_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of poll cycles completed",
    )

    errors_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of errors encountered",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Timestamp of last state update (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of WatcherStateDB."""
        return (
            f"<WatcherStateDB(watcher_id={self.watcher_id}, "
            f"polls_count={self.polls_count})>"
        )
