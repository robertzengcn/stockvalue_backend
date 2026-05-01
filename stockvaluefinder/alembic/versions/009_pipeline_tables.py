"""Add pipeline_tasks and pipeline_documents tables

Revision ID: 009
Revises: 008
Create Date: 2026-05-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, Sequence[str], None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pipeline_tasks and pipeline_documents tables."""
    # Create pipeline_tasks first (no FK dependency on pipeline_documents)
    op.create_table(
        "pipeline_tasks",
        sa.Column(
            "task_id",
            sa.String(36),
            primary_key=True,
            nullable=False,
            comment="Unique task identifier",
        ),
        sa.Column(
            "ticker",
            sa.String(20),
            sa.ForeignKey("stocks.ticker"),
            nullable=False,
            index=True,
            comment="Stock ticker (FK to stocks)",
        ),
        sa.Column(
            "business_key",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="Unique business key for deduplication",
        ),
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
            comment="Current pipeline state",
        ),
        sa.Column(
            "current_stage",
            sa.String(50),
            nullable=True,
            comment="Description of the current processing stage",
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of retry attempts",
        ),
        sa.Column(
            "max_retries",
            sa.Integer(),
            nullable=False,
            server_default="3",
            comment="Maximum allowed retries",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Last error message if task failed",
        ),
        sa.Column(
            "result_summary",
            postgresql.JSONB(),
            nullable=True,
            comment="JSON summary of processing results",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Task creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Last update timestamp (UTC)",
        ),
        comment="Pipeline task state machine tracking",
    )

    # Create pipeline_documents second (FK to pipeline_tasks)
    op.create_table(
        "pipeline_documents",
        sa.Column(
            "document_id",
            sa.String(36),
            primary_key=True,
            nullable=False,
            comment="Unique document identifier",
        ),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("pipeline_tasks.task_id"),
            nullable=False,
            index=True,
            comment="Foreign key to pipeline task",
        ),
        sa.Column(
            "source_url",
            sa.Text(),
            nullable=True,
            comment="URL where the document was downloaded from",
        ),
        sa.Column(
            "source_id",
            sa.String(255),
            nullable=True,
            index=True,
            comment="Announcement/source identifier for deduplication",
        ),
        sa.Column(
            "content_hash",
            sa.String(64),
            nullable=True,
            index=True,
            comment="SHA256 hash of the document content",
        ),
        sa.Column(
            "file_path",
            sa.Text(),
            nullable=True,
            comment="Local filesystem path where the file is stored",
        ),
        sa.Column(
            "file_size",
            sa.BigInteger(),
            nullable=True,
            comment="Size of the file in bytes",
        ),
        sa.Column(
            "downloaded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when the document was downloaded",
        ),
        comment="Pipeline document metadata for downloaded reports",
    )


def downgrade() -> None:
    """Drop pipeline_documents first (FK dependency), then pipeline_tasks."""
    op.drop_table("pipeline_documents")
    op.drop_table("pipeline_tasks")
