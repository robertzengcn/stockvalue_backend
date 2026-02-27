"""Initial schema migration

Revision ID: 001
Revises:
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create stocks table
    op.create_table(
        'stocks',
        sa.Column('ticker', sa.String(20), primary_key=True, comment='Stock code (e.g., 600519.SH, 0700.HK)'),
        sa.Column('name', sa.String(255), nullable=False, comment='Company name'),
        sa.Column('market', sa.String(20), nullable=False, comment='Market enum (A_SHARE, HK_SHARE)'),
        sa.Column('industry', sa.String(100), nullable=False, comment='Industry sector'),
        sa.Column('list_date', sa.Date(), nullable=False, comment='Listing date'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='Record creation timestamp'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='Last update timestamp'),
        sa.Index('ix_stocks_market', 'market'),
        sa.Index('ix_stocks_industry', 'industry'),
        comment='Stock basic information for A-shares and Hong Kong stocks',
    )

    # Create rate_data table
    op.create_table(
        'rate_data',
        sa.Column('rate_id', sa.String(36), primary_key=True, comment='Unique identifier'),
        sa.Column('rate_date', sa.Date(), nullable=False, unique=True, comment='Date of rate'),
        sa.Column('ten_year_treasury', sa.Float(), nullable=False, comment='10-year government bond yield'),
        sa.Column('three_year_deposit', sa.Float(), nullable=False, comment='3-year large deposit rate'),
        sa.Column('one_year_deposit', sa.Float(), nullable=False, comment='1-year deposit rate'),
        sa.Column('benchmark_rate', sa.Float(), nullable=False, comment='Central bank benchmark rate'),
        sa.Column('rate_source', sa.String(100), nullable=False, comment='Source of data (PBOC, HKMA, etc.)'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='Record creation timestamp'),
        sa.Index('ix_rate_data_rate_date', 'rate_date'),
        comment='Market interest rate data for yield comparison',
    )


def downgrade() -> None:
    """Drop initial database schema."""
    op.drop_table('rate_data')
    op.drop_table('stocks')
