"""SQLAlchemy ORM model for ApiUsageRecord entity.

Stores aggregated API usage data per user per endpoint for a given
time period. This table receives periodic flushes from Redis Hash
counters managed by UsageTracker.
"""

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class ApiUsageRecordDB(Base):
    """SQLAlchemy ORM model for API usage tracking records.

    Each row represents aggregated usage for a single user + endpoint
    over a specific time period (e.g., daily or hourly). Periodic jobs
    flush Redis counters into this table for long-term persistence.

    Attributes:
        id: UUID primary key
        user_id: Foreign key to users.id
        endpoint: API endpoint path (e.g., /api/v1/analyze/risk)
        call_count: Number of successful calls in this period
        error_count: Number of error responses in this period
        period_start: Start of the aggregation period
        period_end: End of the aggregation period
        created_at: Record creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "api_usage_records"

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

    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="API endpoint path",
    )

    call_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of successful calls",
    )

    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of error responses",
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="Start of the aggregation period",
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="End of the aggregation period",
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

    __table_args__ = (
        sa.Index("ix_api_usage_records_user_period", "user_id", "period_start"),
        sa.Index("ix_api_usage_records_endpoint", "endpoint"),
    )

    def __repr__(self) -> str:
        """Return string representation of ApiUsageRecordDB."""
        return (
            f"<ApiUsageRecordDB(user_id={self.user_id}, "
            f"endpoint={self.endpoint}, period={self.period_start})>"
        )
