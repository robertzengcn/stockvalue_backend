"""Add capital_allocation_scores table for capital allocation scorecard.

Revision ID: 012
Revises: 011
Create Date: 2026-05-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, Sequence[str], None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create capital_allocation_scores table for capital allocation scorecard."""
    op.create_table(
        "capital_allocation_scores",
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
            comment="Stock code (foreign key)",
        ),
        sa.Column(
            "fiscal_year",
            sa.Integer(),
            nullable=False,
            comment="Fiscal year of analysis",
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Calculation timestamp (UTC)",
        ),
        # Dimension results stored as JSONB
        sa.Column(
            "buyback_yield_data",
            postgresql.JSONB(),
            nullable=False,
            comment="Buyback yield dimension result",
        ),
        sa.Column(
            "dividend_stability_data",
            postgresql.JSONB(),
            nullable=False,
            comment="Dividend stability dimension result",
        ),
        sa.Column(
            "expansion_discipline_data",
            postgresql.JSONB(),
            nullable=False,
            comment="Expansion discipline dimension result",
        ),
        # Combined scorecard
        sa.Column(
            "overall_grade",
            sa.String(1),
            nullable=False,
            comment="Overall capital allocation grade (A/B/C/D)",
        ),
        sa.Column(
            "weighting",
            postgresql.JSONB(),
            nullable=False,
            comment="Weighting used for score calculation",
        ),
        # Audit trail
        sa.Column(
            "audit_trail",
            postgresql.JSONB(),
            nullable=False,
            comment="Full audit trail with source data and calculation steps",
        ),
        comment="Capital allocation scorecard results per stock per fiscal year",
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_capital_allocation_scores_ticker",
        "capital_allocation_scores",
        ["ticker"],
    )
    op.create_index(
        "ix_capital_allocation_scores_fiscal_year",
        "capital_allocation_scores",
        ["fiscal_year"],
    )
    op.create_index(
        "ix_capital_allocation_scores_calculated_at",
        "capital_allocation_scores",
        ["calculated_at"],
    )

    # Unique constraint on (ticker, fiscal_year) to support upsert
    op.create_unique_constraint(
        "uq_capital_allocation_scores_ticker_fiscal_year",
        "capital_allocation_scores",
        ["ticker", "fiscal_year"],
    )


def downgrade() -> None:
    """Drop capital_allocation_scores table."""
    op.drop_table("capital_allocation_scores")
