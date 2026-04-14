"""007_add_fscore_to_risk_scores

Revision ID: 007
Revises: 006
Create Date: 2026-04-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, Sequence[str], None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Piotroski F-Score columns to risk_scores table."""
    op.add_column(
        "risk_scores",
        sa.Column(
            "f_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Piotroski F-Score value (0-9)",
        ),
    )
    op.add_column(
        "risk_scores",
        sa.Column(
            "fscore_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                "'{\"positive_roa\": false, \"positive_cfo\": false, "
                "\"improving_roa\": false, \"cfo_exceeds_roa\": false, "
                "\"lower_leverage\": false, \"higher_liquidity\": false, "
                "\"no_new_shares\": false, \"improving_margin\": false, "
                "\"improving_turnover\": false}'::jsonb"
            ),
            comment="F-Score component data (9 binary signals)",
        ),
    )
    op.alter_column("risk_scores", "f_score", server_default=None)
    op.alter_column("risk_scores", "fscore_data", server_default=None)


def downgrade() -> None:
    """Remove Piotroski F-Score columns from risk_scores table."""
    op.drop_column("risk_scores", "fscore_data")
    op.drop_column("risk_scores", "f_score")
