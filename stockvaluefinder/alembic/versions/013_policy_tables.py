"""Add policy_documents table and stocks.business_description column.

Revision ID: 013
Revises: 012
Create Date: 2026-05-06

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, Sequence[str], None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create policy_documents table and add business_description to stocks."""
    # Add business_description column to stocks table
    op.add_column(
        "stocks",
        sa.Column(
            "business_description",
            sa.Text(),
            nullable=True,
            comment="Stock business description from AKShare stock_profile_cninfo",
        ),
    )

    # Create policy_documents table
    op.create_table(
        "policy_documents",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Unique document identifier",
        ),
        sa.Column(
            "title",
            sa.String(500),
            nullable=False,
            comment="Policy document title",
        ),
        sa.Column(
            "policy_type",
            sa.String(50),
            nullable=False,
            comment="Type of policy (industry/fiscal/monetary/trade)",
        ),
        sa.Column(
            "issuing_body",
            sa.String(200),
            nullable=False,
            comment="Government body that issued the policy",
        ),
        sa.Column(
            "effective_date",
            sa.Date(),
            nullable=True,
            comment="Date the policy takes effect",
        ),
        sa.Column(
            "industry_tags",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
            comment="Industry tags relevant to this policy",
        ),
        sa.Column(
            "file_path",
            sa.String(500),
            nullable=False,
            comment="Server-side file path to the stored PDF",
        ),
        sa.Column(
            "page_count",
            sa.Integer(),
            nullable=False,
            comment="Number of pages in the PDF",
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of chunks generated from the PDF",
        ),
        sa.Column(
            "upload_date",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp when the document was uploaded",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Last update timestamp",
        ),
        comment="Policy documents for the Policy Resonance Engine",
    )

    # Indexes for common query patterns
    op.create_index(
        "ix_policy_documents_document_id",
        "policy_documents",
        ["document_id"],
    )
    op.create_index(
        "ix_policy_documents_policy_type",
        "policy_documents",
        ["policy_type"],
    )
    op.create_index(
        "ix_policy_documents_issuing_body",
        "policy_documents",
        ["issuing_body"],
    )
    op.create_index(
        "ix_policy_documents_upload_date",
        "policy_documents",
        ["upload_date"],
    )


def downgrade() -> None:
    """Drop policy_documents table and remove business_description from stocks."""
    op.drop_table("policy_documents")
    op.drop_column("stocks", "business_description")
