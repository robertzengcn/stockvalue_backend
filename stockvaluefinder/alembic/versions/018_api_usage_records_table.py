"""Create api_usage_records table for per-user API usage tracking.

Revision ID: 018
Revises: 017
Create Date: 2026-05-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: Union[str, Sequence[str], None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_usage_records table with indexes for usage analytics queries."""
    op.create_table(
        "api_usage_records",
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
            "endpoint",
            sa.String(255),
            nullable=False,
            comment="API endpoint path",
        ),
        sa.Column(
            "call_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Number of successful calls",
        ),
        sa.Column(
            "error_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Number of error responses",
        ),
        sa.Column(
            "period_start",
            sa.DateTime(),
            nullable=False,
            comment="Start of the aggregation period",
        ),
        sa.Column(
            "period_end",
            sa.DateTime(),
            nullable=False,
            comment="End of the aggregation period",
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

    # Composite index for querying usage by user within a time period
    op.create_index(
        "ix_api_usage_records_user_period",
        "api_usage_records",
        ["user_id", "period_start"],
    )

    # Index for querying usage by endpoint (admin analytics)
    op.create_index(
        "ix_api_usage_records_endpoint",
        "api_usage_records",
        ["endpoint"],
    )


def downgrade() -> None:
    """Drop api_usage_records table."""
    op.drop_index("ix_api_usage_records_endpoint", table_name="api_usage_records")
    op.drop_index("ix_api_usage_records_user_period", table_name="api_usage_records")
    op.drop_table("api_usage_records")
