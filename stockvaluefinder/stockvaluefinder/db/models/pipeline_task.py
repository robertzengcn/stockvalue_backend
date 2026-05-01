"""SQLAlchemy ORM model for PipelineTask entity."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class PipelineTaskDB(Base):
    """SQLAlchemy ORM model representing a pipeline task.

    Tracks the state machine for processing a financial report through
    the pipeline stages: PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE/FAILED.

    Attributes:
        task_id: UUID primary key.
        ticker: Stock ticker (FK to stocks.ticker).
        business_key: Unique deduplication key (ticker:fiscal_year:report_type).
        state: Current state in the pipeline state machine.
        current_stage: Description of the current processing stage.
        retry_count: Number of times this task has been retried.
        max_retries: Maximum allowed retries before permanent failure.
        error_message: Last error message if the task failed.
        result_summary: JSONB summary of processing results.
        created_at: Task creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "pipeline_tasks"

    # Primary key
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique task identifier",
    )

    # Foreign key to stocks
    ticker: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.ticker"),
        nullable=False,
        index=True,
        comment="Stock ticker (FK to stocks)",
    )

    # Deduplication key
    business_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Unique business key for deduplication (ticker:fiscal_year:report_type)",
    )

    # State machine
    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Current pipeline state (pending, downloading, parsing, analyzing, done, failed)",
    )

    current_stage: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Description of the current processing stage",
    )

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )

    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum allowed retries",
    )

    # Error information
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message if task failed",
    )

    # Results
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON summary of processing results",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Task creation timestamp (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of PipelineTask."""
        return (
            f"<PipelineTaskDB(task_id={self.task_id}, "
            f"ticker={self.ticker}, state={self.state})>"
        )
