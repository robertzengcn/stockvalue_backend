"""SQLAlchemy ORM model for FinancialReport entity."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Date, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class FinancialReportDB(Base):
    """SQLAlchemy ORM model representing FinancialReport entity."""

    __tablename__ = "financial_reports"

    # Primary key
    report_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    # Foreign key to Stock
    ticker: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.ticker"),
        nullable=False,
        index=True,
        comment="Stock code (foreign key)",
    )

    # Report metadata
    period: Mapped[str] = mapped_column(
        Date,
        nullable=False,
        comment="Reporting period",
    )

    report_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Report type (ANNUAL, QUARTERLY)",
    )

    fiscal_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Fiscal year",
    )

    fiscal_quarter: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Fiscal quarter (1-4, None for annual)",
    )

    # Income statement
    revenue: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Total revenue",
    )

    net_income: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Net profit",
    )

    operating_cash_flow: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Operating cash flow",
    )

    gross_margin: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Gross margin percentage (0-100)",
    )

    # Balance sheet
    assets_total: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Total assets",
    )

    liabilities_total: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Total liabilities",
    )

    equity_total: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Total equity",
    )

    accounts_receivable: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Accounts receivable",
    )

    inventory: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Inventory",
    )

    fixed_assets: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Fixed assets",
    )

    goodwill: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Goodwill",
    )

    cash_and_equivalents: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Cash and cash equivalents",
    )

    interest_bearing_debt: Mapped[float] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        comment="Interest-bearing debt",
    )

    # Metadata
    report_source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Source of data",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last update timestamp",
    )

    def __repr__(self) -> str:
        """Return string representation of FinancialReport."""
        return f"<FinancialReportDB(report_id={self.report_id}, ticker={self.ticker}, period={self.period})>"
