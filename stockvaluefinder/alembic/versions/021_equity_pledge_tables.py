"""Create equity pledge tables and add pledge columns to risk_scores.

Revision ID: 021
Revises: 020
Create Date: 2026-06-07

Creates:
- equity_pledge_snapshots: company-level pledge summary per stock/date/source
- equity_pledge_details: per-shareholder pledge detail records

Alters:
- risk_scores: add pledge_risk (JSONB), risk_level_breakdown (JSONB)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, Sequence[str], None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create equity pledge tables and add pledge columns to risk_scores.

    Table creation order:
    1. equity_pledge_snapshots (FK to stocks.ticker)
    2. equity_pledge_details (FK to stocks.ticker)
    Then ALTER risk_scores to add pledge columns.
    """

    # --- 1. equity_pledge_snapshots ---
    op.create_table(
        "equity_pledge_snapshots",
        sa.Column(
            "snapshot_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            sa.ForeignKey("stocks.ticker"),
            nullable=False,
            comment="Stock code (FK to stocks)",
        ),
        sa.Column(
            "latest_date",
            sa.Date,
            nullable=False,
            comment="Trade date of the pledge data",
        ),
        sa.Column(
            "stock_name",
            sa.String(100),
            nullable=True,
            comment="Company name at snapshot time",
        ),
        sa.Column(
            "company_pledge_ratio",
            sa.Float,
            nullable=True,
            comment="Company pledge ratio as percentage",
        ),
        sa.Column(
            "pledged_shares",
            sa.Numeric(24, 4),
            nullable=True,
            comment="Total pledged shares",
        ),
        sa.Column(
            "pledge_market_value",
            sa.Numeric(24, 4),
            nullable=True,
            comment="Market value of pledged shares",
        ),
        sa.Column(
            "pledge_count",
            sa.Integer,
            nullable=True,
            comment="Number of pledge transactions",
        ),
        sa.Column(
            "unrestricted_pledged_shares",
            sa.Numeric(24, 4),
            nullable=True,
            comment="Unrestricted shares pledged",
        ),
        sa.Column(
            "restricted_pledged_shares",
            sa.Numeric(24, 4),
            nullable=True,
            comment="Restricted shares pledged",
        ),
        sa.Column(
            "one_year_price_change",
            sa.Float,
            nullable=True,
            comment="One-year price change as percentage",
        ),
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            comment="Data source identifier (e.g., 'akshare')",
        ),
        sa.Column(
            "source_raw",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Raw API response for audit traceability (DB-04)",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when data was fetched from source",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp (UTC)",
        ),
        sa.UniqueConstraint(
            "ticker",
            "latest_date",
            "source",
            name="uq_pledge_snapshot_ticker_date_src",
        ),
    )

    op.create_index(
        "ix_pledge_snapshot_ticker",
        "equity_pledge_snapshots",
        ["ticker"],
    )

    # --- 2. equity_pledge_details ---
    op.create_table(
        "equity_pledge_details",
        sa.Column(
            "detail_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            sa.ForeignKey("stocks.ticker"),
            nullable=False,
            comment="Stock code (FK to stocks)",
        ),
        sa.Column(
            "holder_name",
            sa.String(200),
            nullable=False,
            comment="Shareholder name",
        ),
        sa.Column(
            "is_controlling_holder",
            sa.Boolean,
            nullable=False,
            comment="Whether this is the controlling shareholder",
        ),
        sa.Column(
            "pledge_amount",
            sa.Numeric(24, 4),
            nullable=True,
            comment="Number of shares pledged in this record",
        ),
        sa.Column(
            "pledged_to_holding_ratio",
            sa.Float,
            nullable=True,
            comment="Pledged / holding ratio as percentage",
        ),
        sa.Column(
            "pledged_to_total_share_ratio",
            sa.Float,
            nullable=True,
            comment="Pledged / total shares ratio as percentage",
        ),
        sa.Column(
            "pledgee",
            sa.String(200),
            nullable=True,
            comment="Pledgee institution name",
        ),
        sa.Column(
            "latest_price",
            sa.Float,
            nullable=True,
            comment="Latest stock price",
        ),
        sa.Column(
            "pledge_date_close_price",
            sa.Float,
            nullable=True,
            comment="Stock closing price on pledge date",
        ),
        sa.Column(
            "estimated_closeout_price",
            sa.Float,
            nullable=True,
            comment="Estimated forced-sell price",
        ),
        sa.Column(
            "start_date",
            sa.Date,
            nullable=True,
            comment="Pledge start date",
        ),
        sa.Column(
            "announcement_date",
            sa.Date,
            nullable=True,
            comment="Announcement date",
        ),
        sa.Column(
            "stock_name",
            sa.String(100),
            nullable=True,
            comment="Stock name",
        ),
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            comment="Data source identifier",
        ),
        sa.Column(
            "source_raw",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Raw API response for audit traceability (DB-04)",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when data was fetched from source",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp (UTC)",
        ),
    )

    op.create_index(
        "ix_pledge_detail_ticker_date",
        "equity_pledge_details",
        ["ticker", "announcement_date"],
    )
    op.create_index(
        "ix_pledge_detail_ticker_holder",
        "equity_pledge_details",
        ["ticker", "holder_name"],
    )

    # --- 3. Alter risk_scores: add pledge columns ---
    op.add_column(
        "risk_scores",
        sa.Column(
            "pledge_risk",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Pledge risk analysis result (JSON)",
        ),
    )
    op.add_column(
        "risk_scores",
        sa.Column(
            "risk_level_breakdown",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="Financial vs pledge risk merge breakdown",
        ),
    )


def downgrade() -> None:
    """Reverse: drop pledge columns from risk_scores, then drop pledge tables."""

    # Reverse risk_scores alterations
    op.drop_column("risk_scores", "risk_level_breakdown")
    op.drop_column("risk_scores", "pledge_risk")

    # Reverse equity_pledge_details
    op.drop_index("ix_pledge_detail_ticker_holder", table_name="equity_pledge_details")
    op.drop_index("ix_pledge_detail_ticker_date", table_name="equity_pledge_details")
    op.drop_table("equity_pledge_details")

    # Reverse equity_pledge_snapshots
    op.drop_index("ix_pledge_snapshot_ticker", table_name="equity_pledge_snapshots")
    op.drop_table("equity_pledge_snapshots")
