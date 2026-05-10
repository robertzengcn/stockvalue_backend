"""Add users table for authentication.

Revision ID: 015
Revises: 014
Create Date: 2026-05-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, Sequence[str], None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users table with authentication and RBAC fields."""
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique identifier",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="User email address (unique)",
        ),
        sa.Column(
            "password_hash",
            sa.String(255),
            nullable=False,
            comment="bcrypt password hash",
        ),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            server_default="user",
            comment="User role (admin/user)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
            comment="Whether user account is active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            comment="Last update timestamp",
        ),
        comment="User accounts for authentication",
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
    )
    op.create_index(
        "ix_users_role",
        "users",
        ["role"],
    )


def downgrade() -> None:
    """Drop users table."""
    op.drop_table("users")
