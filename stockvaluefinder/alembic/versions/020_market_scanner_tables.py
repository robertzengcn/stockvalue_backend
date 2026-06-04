"""Create market scanner tables (index_constituents, market_scan_runs, market_scan_candidates, market_scan_rules).

Revision ID: 020
Revises: 019
Create Date: 2026-06-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: Union[str, Sequence[str], None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create 4 market scanner tables with indexes.

    Table creation order respects FK dependencies:
    1. index_constituents (no FK to scanner tables)
    2. market_scan_rules (no FK to scanner tables)
    3. market_scan_runs (standalone)
    4. market_scan_candidates (FK to market_scan_runs.run_id, FK to stocks.ticker)
    """

    # --- 1. index_constituents ---
    op.create_table(
        "index_constituents",
        sa.Column(
            "constituent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "index_code",
            sa.String(20),
            nullable=False,
            comment="Index pool identifier (e.g., CSI300, CSI500)",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            nullable=False,
            comment="Stock code (e.g., 600519.SH)",
        ),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            comment="Company name",
        ),
        sa.Column(
            "effective_date",
            sa.Date,
            nullable=False,
            comment="Date when constituent became active in index",
        ),
        sa.Column(
            "removed_date",
            sa.Date,
            nullable=True,
            comment="Date when constituent was removed from index",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="Whether constituent is currently in the index",
        ),
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="akshare",
            comment="Data source identifier",
        ),
        sa.Column(
            "source_raw",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Raw data from source",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last update timestamp (UTC)",
        ),
        sa.UniqueConstraint(
            "index_code",
            "ticker",
            "effective_date",
            name="uq_idx_ticker_date",
        ),
    )

    op.create_index(
        "ix_idx_const_code_active",
        "index_constituents",
        ["index_code", "is_active"],
    )
    op.create_index(
        "ix_idx_const_ticker_active",
        "index_constituents",
        ["ticker", "is_active"],
    )

    # --- 2. market_scan_rules ---
    op.create_table(
        "market_scan_rules",
        sa.Column(
            "rule_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "rule_name",
            sa.String(100),
            nullable=False,
            unique=True,
            comment="Human-readable rule name (unique)",
        ),
        sa.Column(
            "rule_type",
            sa.String(50),
            nullable=False,
            comment="Rule category (risk, valuation, yield, composite)",
        ),
        sa.Column(
            "description",
            sa.String(500),
            nullable=True,
            comment="Optional description of what this rule does",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="Whether this rule is currently active",
        ),
        sa.Column(
            "parameters",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
            comment="JSON rule parameters (thresholds, weights, etc.)",
        ),
        sa.Column(
            "priority",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Execution priority (lower runs first)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last update timestamp (UTC)",
        ),
    )

    op.create_index(
        "ix_scan_rules_type",
        "market_scan_rules",
        ["rule_type"],
    )

    # --- 3. market_scan_runs ---
    op.create_table(
        "market_scan_runs",
        sa.Column(
            "run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "index_codes",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="[]",
            comment="JSON array of index pool identifiers scanned",
        ),
        sa.Column(
            "scan_type",
            sa.String(20),
            nullable=False,
            server_default="daily",
            comment="Scan frequency (daily or weekly)",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Current lifecycle state",
        ),
        sa.Column(
            "rules_version",
            sa.String(20),
            nullable=False,
            server_default="v1",
            comment="Version of screening rules applied",
        ),
        sa.Column(
            "total_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Total number of stocks in scan pool",
        ),
        sa.Column(
            "screened_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Number of stocks passing coarse screen",
        ),
        sa.Column(
            "candidate_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Number of final candidates",
        ),
        sa.Column(
            "error_summary",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="JSON summary of errors encountered",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when processing began",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when processing completed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last update timestamp (UTC)",
        ),
    )

    op.create_index(
        "ix_scan_runs_status",
        "market_scan_runs",
        ["status"],
    )

    # --- 4. market_scan_candidates ---
    op.create_table(
        "market_scan_candidates",
        sa.Column(
            "candidate_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "run_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("market_scan_runs.run_id"),
            nullable=False,
            comment="FK to scan run",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            sa.ForeignKey("stocks.ticker"),
            nullable=False,
            comment="Stock code (FK to stocks)",
        ),
        sa.Column(
            "index_code",
            sa.String(20),
            nullable=False,
            comment="Index pool identifier",
        ),
        sa.Column(
            "passed",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="Whether stock passed all screening layers",
        ),
        sa.Column(
            "composite_score",
            sa.Float,
            nullable=False,
            server_default="0.0",
            comment="Overall ranking score (0-100)",
        ),
        sa.Column(
            "screening_snapshot",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
            comment="JSON snapshot of all screening results",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp (UTC)",
        ),
        sa.UniqueConstraint(
            "run_id",
            "ticker",
            name="uq_candidate_run_ticker",
        ),
    )

    op.create_index(
        "ix_scan_candidates_run_id",
        "market_scan_candidates",
        ["run_id"],
    )
    op.create_index(
        "ix_scan_candidates_ticker",
        "market_scan_candidates",
        ["ticker"],
    )


def downgrade() -> None:
    """Drop tables in reverse dependency order."""
    op.drop_index("ix_scan_candidates_ticker", table_name="market_scan_candidates")
    op.drop_index("ix_scan_candidates_run_id", table_name="market_scan_candidates")
    op.drop_table("market_scan_candidates")

    op.drop_index("ix_scan_runs_status", table_name="market_scan_runs")
    op.drop_table("market_scan_runs")

    op.drop_index("ix_scan_rules_type", table_name="market_scan_rules")
    op.drop_table("market_scan_rules")

    op.drop_index("ix_idx_const_ticker_active", table_name="index_constituents")
    op.drop_index("ix_idx_const_code_active", table_name="index_constituents")
    op.drop_table("index_constituents")
