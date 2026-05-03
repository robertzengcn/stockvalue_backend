"""Add roic_results table for ROIC-WACC spread analysis.

Revision ID: 011
Revises: 010
Create Date: 2026-05-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, Sequence[str], None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create roic_results table for ROIC-WACC spread analysis."""
    op.create_table(
        "roic_results",
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
        # ROIC core metrics
        sa.Column(
            "roic",
            sa.Float(),
            nullable=True,
            comment="ROIC value (None if negative invested capital)",
        ),
        sa.Column(
            "negative_invested_capital",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if invested capital is negative (ROIC meaningless)",
        ),
        sa.Column(
            "nopat",
            sa.Float(),
            nullable=True,
            comment="Net Operating Profit After Tax",
        ),
        sa.Column(
            "invested_capital",
            sa.Float(),
            nullable=True,
            comment="Invested capital (equity + debt - cash)",
        ),
        # WACC
        sa.Column(
            "wacc",
            sa.Float(),
            nullable=False,
            comment="Weighted Average Cost of Capital",
        ),
        sa.Column(
            "wacc_breakdown",
            postgresql.JSONB(),
            nullable=False,
            comment="WACC component breakdown (risk_free_rate, beta, erp, etc.)",
        ),
        # Spread
        sa.Column(
            "spread",
            sa.Float(),
            nullable=True,
            comment="ROIC - WACC spread (None if ROIC is None)",
        ),
        sa.Column(
            "spread_classification",
            sa.String(30),
            nullable=False,
            comment="Spread classification (e.g. strong_moat, value_creator)",
        ),
        # Trend data
        sa.Column(
            "moat_trend",
            postgresql.JSONB(),
            nullable=True,
            comment="Moat trend analysis with multi-year ROIC data",
        ),
        # Metadata
        sa.Column(
            "is_financial_sector",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True if stock is in financial sector (different NOPAT formula)",
        ),
        sa.Column(
            "audit_trail",
            postgresql.JSONB(),
            nullable=False,
            comment="Audit trail with source data and calculation steps",
        ),
        comment="ROIC-WACC spread analysis results per stock per fiscal year",
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_roic_results_ticker",
        "roic_results",
        ["ticker"],
    )
    op.create_index(
        "ix_roic_results_fiscal_year",
        "roic_results",
        ["fiscal_year"],
    )
    op.create_index(
        "ix_roic_results_calculated_at",
        "roic_results",
        ["calculated_at"],
    )

    # Unique constraint on (ticker, fiscal_year) to support upsert
    op.create_unique_constraint(
        "uq_roic_results_ticker_fiscal_year",
        "roic_results",
        ["ticker", "fiscal_year"],
    )


def downgrade() -> None:
    """Drop roic_results table."""
    op.drop_table("roic_results")
