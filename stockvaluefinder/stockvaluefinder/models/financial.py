"""Financial report domain models (Pydantic)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ValidationInfo

from stockvaluefinder.models.enums import ReportType


class FinancialReportBase(BaseModel):
    """Base FinancialReport model with common fields."""

    period: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Reporting period (e.g., '2024-03-31')",
    )
    report_type: ReportType = Field(..., description="Report type (ANNUAL, QUARTERLY)")
    revenue: Decimal = Field(..., ge=0, description="Total revenue (元)")
    net_income: Decimal = Field(..., ge=0, description="Net profit (元)")
    operating_cash_flow: Decimal = Field(..., description="Operating cash flow (元)")
    gross_margin: float = Field(
        ..., ge=0, le=100, description="Gross margin percentage (0-100)"
    )
    assets_total: Decimal = Field(..., ge=0, description="Total assets (元)")
    liabilities_total: Decimal = Field(..., ge=0, description="Total liabilities (元)")
    equity_total: Decimal = Field(..., ge=0, description="Total equity (元)")
    accounts_receivable: Decimal = Field(
        ..., ge=0, description="Accounts receivable (元)"
    )
    inventory: Decimal = Field(..., ge=0, description="Inventory (元)")
    fixed_assets: Decimal = Field(..., ge=0, description="Fixed assets (元)")
    goodwill: Decimal = Field(..., ge=0, description="Goodwill (元)")
    cash_and_equivalents: Decimal = Field(
        ..., ge=0, description="Cash and cash equivalents (元)"
    )
    interest_bearing_debt: Decimal = Field(
        ..., ge=0, description="Interest-bearing debt (元)"
    )
    report_source: str = Field(
        ..., min_length=1, description="Source of data (Tushare/AKShare/PDF)"
    )
    fiscal_year: int = Field(..., ge=1990, le=2100, description="Fiscal year")


class FinancialReportCreate(FinancialReportBase):
    """Model for creating a new FinancialReport."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )
    fiscal_quarter: int | None = Field(
        None, ge=1, le=4, description="Fiscal quarter (1-4, None for annual)"
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        """Normalize ticker to uppercase."""
        return v.upper()

    @field_validator("fiscal_quarter")
    @classmethod
    def validate_quarter_consistency(
        cls, v: int | None, info: ValidationInfo
    ) -> int | None:
        """Ensure fiscal_quarter is consistent with report_type."""
        if info.data.get("report_type") == ReportType.QUARTERLY and v is None:
            raise ValueError("fiscal_quarter is required for quarterly reports")
        if info.data.get("report_type") == ReportType.ANNUAL and v is not None:
            raise ValueError("fiscal_quarter should be None for annual reports")
        return v


class FinancialReportUpdate(BaseModel):
    """Model for updating a FinancialReport (all fields optional)."""

    revenue: Decimal | None = Field(None, ge=0)
    net_income: Decimal | None = Field(None, ge=0)
    operating_cash_flow: Decimal | None = None
    gross_margin: float | None = Field(None, ge=0, le=100)
    assets_total: Decimal | None = Field(None, ge=0)
    liabilities_total: Decimal | None = Field(None, ge=0)
    equity_total: Decimal | None = Field(None, ge=0)
    accounts_receivable: Decimal | None = Field(None, ge=0)
    inventory: Decimal | None = Field(None, ge=0)
    fixed_assets: Decimal | None = Field(None, ge=0)
    goodwill: Decimal | None = Field(None, ge=0)
    cash_and_equivalents: Decimal | None = Field(None, ge=0)
    interest_bearing_debt: Decimal | None = Field(None, ge=0)
    report_source: str | None = Field(None, min_length=1)


class FinancialReport(FinancialReportBase):
    """Complete FinancialReport model with all fields including timestamps."""

    model_config = {"frozen": True}

    report_id: UUID = Field(..., description="Unique identifier (primary key)")
    ticker: str = Field(..., description="Stock code (foreign key)")
    fiscal_quarter: int | None = Field(
        None, ge=1, le=4, description="Fiscal quarter (1-4, None for annual)"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class FinancialReportInDB(FinancialReport):
    """FinancialReport model as stored in database (includes all fields)."""

    pass
