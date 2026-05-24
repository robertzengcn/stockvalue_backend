"""Create user_stock_access table for per-user stock access control.

Revision ID: 017
Revises: 016
Create Date: 2026-05-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: Union[str, Sequence[str], None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_stock_access table with FK to users and unique constraint."""
    op.create_table(
        "user_stock_access",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            comment="Unique identifier",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
            comment="Foreign key to users.id",
        ),
        sa.Column(
            "ticker",
            sa.String(12),
            nullable=False,
            comment="Permitted stock ticker (e.g., 600519.SH)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp",
        ),
        sa.UniqueConstraint(
            "user_id",
            "ticker",
            name="uq_user_stock_access_user_ticker",
        ),
    )


def downgrade() -> None:
    """Drop user_stock_access table."""
    op.drop_table("user_stock_access")
