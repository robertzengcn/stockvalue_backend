"""005_convert_calculated_at_to_timestamptz

Revision ID: 3330cc06df7c
Revises: 004
Create Date: 2026-03-31 12:47:03.566450

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3330cc06df7c"
down_revision: Union[str, Sequence[str], None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert calculated_at columns from TIMESTAMP to TIMESTAMPTZ."""
    op.alter_column(
        "valuation_results",
        "calculated_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using="calculated_at::timestamptz",
    )
    op.alter_column(
        "risk_scores",
        "calculated_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using="calculated_at::timestamptz",
    )
    op.alter_column(
        "yield_gaps",
        "calculated_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using="calculated_at::timestamptz",
    )


def downgrade() -> None:
    """Revert calculated_at columns to TIMESTAMP WITHOUT TIME ZONE."""
    op.alter_column(
        "valuation_results",
        "calculated_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="calculated_at::timestamp",
    )
    op.alter_column(
        "risk_scores",
        "calculated_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="calculated_at::timestamp",
    )
    op.alter_column(
        "yield_gaps",
        "calculated_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="calculated_at::timestamp",
    )
