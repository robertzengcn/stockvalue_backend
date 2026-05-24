"""Create rate_limit_overrides table for per-user rate limit overrides.

Revision ID: 019
Revises: 018
Create Date: 2026-05-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: Union[str, Sequence[str], None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create rate_limit_overrides table with unique constraint on user_id."""
    op.create_table(
        "rate_limit_overrides",
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
            unique=True,
            comment="Foreign key to users.id (one override per user)",
        ),
        sa.Column(
            "limit",
            sa.Integer(),
            nullable=False,
            comment="Maximum requests per window",
        ),
        sa.Column(
            "window_seconds",
            sa.Integer(),
            nullable=False,
            comment="Window duration in seconds",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last update timestamp",
        ),
    )

    # Index for fast lookup of override by user_id
    op.create_index(
        "ix_rate_limit_overrides_user_id",
        "rate_limit_overrides",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop rate_limit_overrides table."""
    op.drop_index("ix_rate_limit_overrides_user_id", table_name="rate_limit_overrides")
    op.drop_table("rate_limit_overrides")
