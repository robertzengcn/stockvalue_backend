"""Add watchlist, watcher_state, and pending_disclosures tables

Revision ID: 010
Revises: 009
Create Date: 2026-05-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, Sequence[str], None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create watchlist, watcher_state, and pending_disclosures tables."""
    # Create watchlist first (no dependencies)
    op.create_table(
        "watchlist",
        sa.Column(
            "ticker",
            sa.String(20),
            primary_key=True,
            nullable=False,
            comment="Stock ticker (PK, e.g. 600519.SH)",
        ),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            comment="Stock name or company name",
        ),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when added to watchlist (UTC)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether the stock is actively being monitored",
        ),
        comment="User-configured stock watchlist for disclosure monitoring",
    )

    # Create watcher_state second (no dependencies)
    op.create_table(
        "watcher_state",
        sa.Column(
            "watcher_id",
            sa.String(50),
            primary_key=True,
            nullable=False,
            comment="Watcher instance identifier",
        ),
        sa.Column(
            "last_poll_time",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of the most recent poll cycle (UTC)",
        ),
        sa.Column(
            "last_akshare_success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether the last AKShare poll succeeded",
        ),
        sa.Column(
            "last_cninfo_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether CNInfo fallback was used in the last poll",
        ),
        sa.Column(
            "polls_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total number of poll cycles completed",
        ),
        sa.Column(
            "errors_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total number of errors encountered",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp of last state update (UTC)",
        ),
        comment="Watcher operational state for observability",
    )

    # Create pending_disclosures third (staging table)
    op.create_table(
        "pending_disclosures",
        sa.Column(
            "disclosure_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique disclosure identifier",
        ),
        sa.Column(
            "poll_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
            comment="UUID linking disclosures from the same poll cycle",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            nullable=False,
            comment="Stock ticker (e.g. 600519.SH)",
        ),
        sa.Column(
            "stock_name",
            sa.String(100),
            nullable=True,
            comment="Stock name or company name",
        ),
        sa.Column(
            "report_type",
            sa.String(20),
            nullable=False,
            comment="Report type: annual, semi_annual, q1, q3",
        ),
        sa.Column(
            "fiscal_year",
            sa.Integer(),
            nullable=False,
            comment="Fiscal year of the report",
        ),
        sa.Column(
            "disclosure_date",
            sa.Date(),
            nullable=True,
            comment="Actual disclosure date (if disclosed)",
        ),
        sa.Column(
            "first_appointment",
            sa.Date(),
            nullable=True,
            comment="First appointment date from disclosure schedule",
        ),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            comment="Data source: akshare or cninfo",
        ),
        sa.Column(
            "source_raw",
            postgresql.JSONB(),
            nullable=True,
            comment="Raw source data for debugging/audit",
        ),
        sa.Column(
            "processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            index=True,
            comment="Whether this disclosure has been processed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Record creation timestamp (UTC)",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when the record was processed (UTC)",
        ),
        comment="Staging table for disclosure data awaiting processing",
    )


def downgrade() -> None:
    """Drop tables in reverse order (pending_disclosures, watcher_state, watchlist)."""
    op.drop_table("pending_disclosures")
    op.drop_table("watcher_state")
    op.drop_table("watchlist")
