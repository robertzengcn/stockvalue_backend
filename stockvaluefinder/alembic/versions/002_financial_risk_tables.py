"""Add financial reports and risk scores tables

Revision ID: 002
Revises: 001
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create financial_reports and risk_scores tables."""
    # Create financial_reports table
    op.create_table(
        'financial_reports',
        sa.Column('report_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, comment='Unique identifier'),
        sa.Column('ticker', sa.String(20), sa.ForeignKey('stocks.ticker'), nullable=False, index=True, comment='Stock code (foreign key)'),
        sa.Column('period', sa.Date(), nullable=False, comment='Reporting period'),
        sa.Column('report_type', sa.String(20), nullable=False, comment='Report type (ANNUAL, QUARTERLY)'),
        sa.Column('fiscal_year', sa.Integer(), nullable=False, index=True, comment='Fiscal year'),
        sa.Column('fiscal_quarter', sa.Integer(), nullable=True, comment='Fiscal quarter (1-4, None for annual)'),

        # Income statement
        sa.Column('revenue', sa.Numeric(20, 2), nullable=False, comment='Total revenue'),
        sa.Column('net_income', sa.Numeric(20, 2), nullable=False, comment='Net profit'),
        sa.Column('operating_cash_flow', sa.Numeric(20, 2), nullable=False, comment='Operating cash flow'),
        sa.Column('gross_margin', sa.Float(), nullable=False, comment='Gross margin percentage (0-100)'),

        # Balance sheet
        sa.Column('assets_total', sa.Numeric(20, 2), nullable=False, comment='Total assets'),
        sa.Column('liabilities_total', sa.Numeric(20, 2), nullable=False, comment='Total liabilities'),
        sa.Column('equity_total', sa.Numeric(20, 2), nullable=False, comment='Total equity'),
        sa.Column('accounts_receivable', sa.Numeric(20, 2), nullable=False, comment='Accounts receivable'),
        sa.Column('inventory', sa.Numeric(20, 2), nullable=False, comment='Inventory'),
        sa.Column('fixed_assets', sa.Numeric(20, 2), nullable=False, comment='Fixed assets'),
        sa.Column('goodwill', sa.Numeric(20, 2), nullable=False, comment='Goodwill'),
        sa.Column('cash_and_equivalents', sa.Numeric(20, 2), nullable=False, comment='Cash and cash equivalents'),
        sa.Column('interest_bearing_debt', sa.Numeric(20, 2), nullable=False, comment='Interest-bearing debt'),

        # Metadata
        sa.Column('report_source', sa.String(100), nullable=False, comment='Source of data'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='Record creation timestamp'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='Last update timestamp'),

        sa.UniqueConstraint('ticker', 'period', name='uq_financial_reports_ticker_period'),
        comment='Financial report data for risk analysis',
    )

    # Create risk_scores table
    op.create_table(
        'risk_scores',
        sa.Column('score_id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, comment='Unique identifier'),
        sa.Column('ticker', sa.String(20), sa.ForeignKey('stocks.ticker'), nullable=False, index=True, comment='Stock code (foreign key)'),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('financial_reports.report_id'), nullable=False, unique=True, comment='Reference to FinancialReport'),

        # Risk assessment
        sa.Column('risk_level', sa.String(20), nullable=False, index=True, comment='Overall risk level (LOW, MEDIUM, HIGH, CRITICAL)'),
        sa.Column('calculated_at', sa.DateTime(), nullable=False, index=True, comment='Calculation timestamp'),

        # Beneish M-Score
        sa.Column('m_score', sa.Float(), nullable=False, comment='Beneish M-Score value'),
        sa.Column('mscore_data', postgresql.JSONB(), nullable=False, comment='M-Score component data (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA)'),

        # 存贷双高
        sa.Column('存贷双高', sa.Boolean(), nullable=False, default=False, comment='High cash + high debt flag'),
        sa.Column('cash_amount', sa.Numeric(20, 2), nullable=False, comment='Cash and equivalents for 存贷双高 calculation'),
        sa.Column('debt_amount', sa.Numeric(20, 2), nullable=False, comment='Interest-bearing debt for 存贷双高 calculation'),
        sa.Column('cash_growth_rate', sa.Float(), nullable=False, comment='YoY cash growth rate'),
        sa.Column('debt_growth_rate', sa.Float(), nullable=False, comment='YoY debt growth rate'),

        # Goodwill risk
        sa.Column('goodwill_ratio', sa.Float(), nullable=False, comment='Goodwill / Equity ratio (0-1)'),
        sa.Column('goodwill_excessive', sa.Boolean(), nullable=False, default=False, comment='True if goodwill_ratio > 30%'),

        # Cash flow divergence
        sa.Column('profit_cash_divergence', sa.Boolean(), nullable=False, default=False, comment='True if net_income grew but OCF declined'),
        sa.Column('profit_growth', sa.Float(), nullable=False, comment='YoY profit growth rate'),
        sa.Column('ocf_growth', sa.Float(), nullable=False, comment='YoY operating cash flow growth rate'),

        # Red flags
        sa.Column('red_flags', postgresql.JSONB(), nullable=False, default=list, comment='List of warning messages'),

        comment='Risk assessment results for financial fraud detection',
    )


def downgrade() -> None:
    """Drop financial_reports and risk_scores tables."""
    op.drop_table('risk_scores')
    op.drop_table('financial_reports')
