"""006_add_narrative_columns

Revision ID: 006
Revises: 3330cc06df7c
Create Date: 2026-04-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "3330cc06df7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable narrative TEXT column to analysis tables."""
    op.add_column(
        "valuation_results",
        sa.Column(
            "narrative",
            sa.Text(),
            nullable=True,
            comment="LLM-generated analysis narrative (JSON)",
        ),
    )
    op.add_column(
        "risk_scores",
        sa.Column(
            "narrative",
            sa.Text(),
            nullable=True,
            comment="LLM-generated analysis narrative (JSON)",
        ),
    )
    op.add_column(
        "yield_gaps",
        sa.Column(
            "narrative",
            sa.Text(),
            nullable=True,
            comment="LLM-generated analysis narrative (JSON)",
        ),
    )


def downgrade() -> None:
    """Remove narrative columns from analysis tables."""
    op.drop_column("yield_gaps", "narrative")
    op.drop_column("risk_scores", "narrative")
    op.drop_column("valuation_results", "narrative")
