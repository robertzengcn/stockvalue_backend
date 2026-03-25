"""Add valuation_results table

Revision ID: 004
Revises: 003
Create Date: 2026-02-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create valuation_results table."""
    op.create_table(
        "valuation_results",
        sa.Column(
            "valuation_id",
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
            "current_price",
            sa.Numeric(20, 4),
            nullable=False,
            comment="Current market price per share",
        ),
        sa.Column(
            "intrinsic_value",
            sa.Numeric(20, 4),
            nullable=False,
            comment="Calculated intrinsic value per share",
        ),
        sa.Column(
            "wacc",
            sa.Float(),
            nullable=False,
            comment="Weighted average cost of capital",
        ),
        sa.Column(
            "margin_of_safety",
            sa.Float(),
            nullable=False,
            comment="Margin of safety (intrinsic - price) / price",
        ),
        sa.Column(
            "valuation_level",
            sa.String(20),
            nullable=False,
            index=True,
            comment="Valuation level (UNDERVERLUED, FAIR_VALUE, OVERVALUED)",
        ),
        sa.Column(
            "dcf_params",
            postgresql.JSONB(),
            nullable=False,
            comment="DCF parameters used in calculation",
        ),
        sa.Column(
            "audit_trail",
            postgresql.JSONB(),
            nullable=False,
            comment="Full calculation audit trail",
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(),
            nullable=False,
            index=True,
            comment="Calculation timestamp",
        ),
        comment="DCF valuation analysis results",
    )


def downgrade() -> None:
    """Drop valuation_results table."""
    op.drop_table("valuation_results")
