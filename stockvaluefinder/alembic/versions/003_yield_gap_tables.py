"""Add dividend_data and yield_gaps tables

Revision ID: 003
Revises: 002
Create Date: 2026-02-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create dividend_data and yield_gaps tables."""
    # Create dividend_data table
    op.create_table(
        "dividend_data",
        sa.Column(
            "dividend_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            sa.ForeignKey("stocks.ticker"),
            nullable=False,
            index=True,
            comment="Stock code (foreign key)",
        ),
        sa.Column(
            "ex_dividend_date",
            sa.Date(),
            nullable=False,
            index=True,
            comment="Ex-dividend date",
        ),
        sa.Column(
            "dividend_per_share",
            sa.Numeric(20, 4),
            nullable=False,
            comment="Dividend amount per share (CNY/HKD)",
        ),
        sa.Column(
            "dividend_frequency",
            sa.String(20),
            nullable=False,
            comment="Dividend frequency (ANNUAL, SEMI_ANNUAL, QUARTERLY, SPECIAL)",
        ),
        sa.Column(
            "fiscal_year",
            sa.Numeric(4, 0),
            nullable=True,
            comment="Fiscal year of dividend payment",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, comment="Last update timestamp"
        ),
        comment="Dividend payment data for yield analysis",
    )

    # Create yield_gaps table
    op.create_table(
        "yield_gaps",
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            sa.ForeignKey("stocks.ticker"),
            nullable=False,
            index=True,
            comment="Stock code (foreign key)",
        ),
        sa.Column(
            "cost_basis",
            sa.Numeric(20, 4),
            nullable=False,
            comment="Purchase price per share",
        ),
        sa.Column(
            "current_price",
            sa.Numeric(20, 4),
            nullable=False,
            comment="Current market price per share",
        ),
        sa.Column(
            "gross_dividend_yield",
            sa.Float(),
            nullable=False,
            comment="Gross dividend yield (before tax)",
        ),
        sa.Column(
            "net_dividend_yield",
            sa.Float(),
            nullable=False,
            comment="Net dividend yield (after tax)",
        ),
        sa.Column(
            "risk_free_bond_rate",
            sa.Float(),
            nullable=False,
            comment="10-year treasury bond rate",
        ),
        sa.Column(
            "risk_free_deposit_rate",
            sa.Float(),
            nullable=False,
            comment="3-year large deposit rate",
        ),
        sa.Column(
            "yield_gap",
            sa.Float(),
            nullable=False,
            comment="Yield gap: net_yield - max(bond, deposit)",
        ),
        sa.Column(
            "recommendation",
            sa.String(20),
            nullable=False,
            index=True,
            comment="Investment recommendation (ATTRACTIVE, NEUTRAL, UNATTRACTIVE)",
        ),
        sa.Column(
            "market",
            sa.String(20),
            nullable=False,
            comment="Market (A_SHARE or HK_SHARE)",
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(),
            nullable=False,
            index=True,
            comment="Calculation timestamp",
        ),
        comment="Yield gap analysis results for dividend stocks",
    )


def downgrade() -> None:
    """Drop dividend_data and yield_gaps tables."""
    op.drop_table("yield_gaps")
    op.drop_table("dividend_data")
