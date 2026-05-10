"""Add deleted_at column to users table for soft delete.

Revision ID: 016
Revises: 015
Create Date: 2026-05-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, Sequence[str], None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deleted_at column for soft delete support."""
    op.add_column(
        "users",
        sa.Column(
            "deleted_at",
            sa.DateTime(),
            nullable=True,
            comment="Soft delete timestamp (null = active)",
        ),
    )


def downgrade() -> None:
    """Remove deleted_at column."""
    op.drop_column("users", "deleted_at")
