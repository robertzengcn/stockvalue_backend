"""Add alpha_scores table for composite Alpha score persistence.

Revision ID: 014
Revises: 013
Create Date: 2026-05-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, Sequence[str], None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create alpha_scores table with all component scores and composite."""
    op.create_table(
        "alpha_scores",
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
        # Four normalized component scores
        sa.Column(
            "roic_wacc_score",
            sa.Float(),
            nullable=False,
            comment="ROIC-WACC normalized score (0-100)",
        ),
        sa.Column(
            "roic_wacc_raw",
            sa.Float(),
            nullable=True,
            comment="Original ROIC-WACC spread value",
        ),
        sa.Column(
            "capex_score",
            sa.Float(),
            nullable=False,
            comment="Capital Allocation normalized score (0-100)",
        ),
        sa.Column(
            "capex_raw_grade",
            sa.String(1),
            nullable=False,
            comment="Original capital allocation grade (A/B/C/D)",
        ),
        sa.Column(
            "policy_score",
            sa.Float(),
            nullable=False,
            comment="Policy resonance score (0-100)",
        ),
        sa.Column(
            "policy_raw_score",
            sa.Float(),
            nullable=False,
            comment="Original policy resonance score",
        ),
        sa.Column(
            "moat_score",
            sa.Float(),
            nullable=False,
            comment="Moat trend normalized score (0-100)",
        ),
        sa.Column(
            "moat_raw_trend",
            sa.String(50),
            nullable=True,
            comment="Original MoatTrend enum value",
        ),
        # Composite score
        sa.Column(
            "alpha_score",
            sa.Float(),
            nullable=False,
            comment="Composite Alpha score (0-100)",
        ),
        sa.Column(
            "weights_used",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
            comment="Weight configuration used",
        ),
        sa.Column(
            "dcf_adjustment_summary",
            postgresql.JSONB(),
            nullable=True,
            comment="DCF adjustment details from policy resonance",
        ),
        # Audit trail
        sa.Column(
            "audit_trail",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
            comment="Full audit trail",
        ),
        comment="Composite Alpha score analysis results",
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_alpha_scores_ticker",
        "alpha_scores",
        ["ticker"],
    )
    op.create_index(
        "ix_alpha_scores_fiscal_year",
        "alpha_scores",
        ["fiscal_year"],
    )
    op.create_index(
        "ix_alpha_scores_calculated_at",
        "alpha_scores",
        ["calculated_at"],
    )


def downgrade() -> None:
    """Drop alpha_scores table."""
    op.drop_table("alpha_scores")
