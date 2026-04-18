"""Add documents table

Revision ID: 008
Revises: 007
Create Date: 2026-04-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documents table for RAG pipeline document metadata."""
    op.create_table(
        "documents",
        sa.Column(
            "document_id",
            sa.String(36),
            primary_key=True,
            nullable=False,
            comment="Unique document identifier (UUID string)",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            nullable=False,
            index=True,
            comment="Linked stock ticker (FK to stocks)",
        ),
        sa.Column(
            "file_name",
            sa.String(500),
            nullable=False,
            comment="Original file name",
        ),
        sa.Column(
            "file_path",
            sa.String(1000),
            nullable=False,
            comment="Storage path for the PDF file",
        ),
        sa.Column(
            "page_count",
            sa.Integer(),
            nullable=False,
            comment="Number of pages in the PDF",
        ),
        sa.Column(
            "processing_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Processing status: pending, processing, completed, failed",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Document metadata (year, report_type, company_name, filing_date)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            comment="Last update timestamp",
        ),
        comment="Uploaded PDF document metadata for RAG pipeline",
    )


def downgrade() -> None:
    """Drop documents table."""
    op.drop_table("documents")
