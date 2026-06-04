"""SQLAlchemy ORM models for Market Scan entities.

Contains three ORM models:
    - MarketScanRunDB: Scan run lifecycle tracking (state machine)
    - MarketScanCandidateDB: Per-stock screening results
    - MarketScanRuleDB: Screening rule definitions
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class MarketScanRunDB(Base):
    """SQLAlchemy ORM model representing a market scan run.

    Tracks the scan run lifecycle through states:
    pending -> running -> completed / partial_failed

    Attributes:
        run_id: UUID primary key.
        index_codes: JSONB array of index pool identifiers scanned.
        scan_type: Scan frequency (daily or weekly).
        status: Current lifecycle state.
        rules_version: Version of screening rules applied.
        total_count: Total number of stocks in scan pool.
        screened_count: Number of stocks passing coarse screen.
        candidate_count: Number of final candidates.
        error_summary: JSONB summary of errors (if any).
        started_at: Timestamp when processing began.
        completed_at: Timestamp when processing completed.
        created_at: Record creation timestamp (UTC).
        updated_at: Record last-update timestamp (UTC).
    """

    __tablename__ = "market_scan_runs"

    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    index_codes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON array of index pool identifiers scanned",
    )

    scan_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="daily",
        comment="Scan frequency (daily or weekly)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Current lifecycle state (pending, running, completed, partial_failed)",
    )

    rules_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="v1",
        comment="Version of screening rules applied",
    )

    total_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of stocks in scan pool",
    )

    screened_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of stocks passing coarse screen",
    )

    candidate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of final candidates",
    )

    error_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON summary of errors encountered during scan",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when processing began",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when processing completed",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Record creation timestamp (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of MarketScanRunDB."""
        return (
            f"<MarketScanRunDB(run_id={self.run_id}, "
            f"status={self.status}, scan_type={self.scan_type})>"
        )


class MarketScanCandidateDB(Base):
    """SQLAlchemy ORM model representing a scan candidate.

    Each row represents a single stock evaluation within a scan run,
    with pass/fail result and composite score.

    Attributes:
        candidate_id: UUID primary key.
        run_id: FK to market_scan_runs.run_id.
        ticker: FK to stocks.ticker.
        index_code: Index pool where this stock was found.
        passed: Whether this stock passed all screening layers.
        composite_score: Overall ranking score.
        screening_snapshot: JSONB snapshot of all screening results.
        created_at: Record creation timestamp (UTC).
    """

    __tablename__ = "market_scan_candidates"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "ticker",
            name="uq_candidate_run_ticker",
        ),
    )

    candidate_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("market_scan_runs.run_id"),
        nullable=False,
        index=True,
        comment="FK to scan run",
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.ticker"),
        nullable=False,
        index=True,
        comment="Stock code (FK to stocks)",
    )

    index_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Index pool identifier",
    )

    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether stock passed all screening layers",
    )

    composite_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Overall ranking score (0-100)",
    )

    screening_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON snapshot of all screening results",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Record creation timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of MarketScanCandidateDB."""
        return (
            f"<MarketScanCandidateDB(candidate_id={self.candidate_id}, "
            f"run_id={self.run_id}, ticker={self.ticker})>"
        )


class MarketScanRuleDB(Base):
    """SQLAlchemy ORM model representing a screening rule definition.

    Reference data table storing configurable screening rules with
    parameters stored as JSONB for flexibility.

    Attributes:
        rule_id: UUID primary key.
        rule_name: Human-readable unique rule name.
        rule_type: Rule category (e.g., risk, valuation, yield, composite).
        description: Optional description of what this rule does.
        is_active: Whether this rule is currently active.
        parameters: JSONB rule parameters (thresholds, weights, etc.).
        priority: Execution priority (lower = runs first).
        created_at: Record creation timestamp (UTC).
        updated_at: Record last-update timestamp (UTC).
    """

    __tablename__ = "market_scan_rules"

    rule_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Human-readable rule name (unique)",
    )

    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Rule category (risk, valuation, yield, composite)",
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional description of what this rule does",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this rule is currently active",
    )

    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON rule parameters (thresholds, weights, etc.)",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Execution priority (lower runs first)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Record creation timestamp (UTC)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp (UTC)",
    )

    def __repr__(self) -> str:
        """Return string representation of MarketScanRuleDB."""
        return (
            f"<MarketScanRuleDB(rule_id={self.rule_id}, "
            f"rule_name={self.rule_name}, rule_type={self.rule_type})>"
        )
