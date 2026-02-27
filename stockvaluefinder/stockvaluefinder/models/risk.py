"""Risk score domain models (Pydantic)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import RiskLevel


class MScoreData(BaseModel):
    """Beneish M-Score component data."""

    model_config = {"frozen": True}

    dsri: float = Field(..., description="Days' Sales in Receivables Index")
    gmi: float = Field(..., description="Gross Margin Index")
    aqi: float = Field(..., description="Asset Quality Index")
    sgi: float = Field(..., description="Sales Growth Index")
    depi: float = Field(..., description="Depreciation Index")
    sgai: float = Field(..., description="SG&A Expense Index")
    lvgi: float = Field(..., description="Leverage Index")
    tata: float = Field(..., description="Total Accruals to Total Assets")


class RiskScoreBase(BaseModel):
    """Base RiskScore model with common fields."""

    ticker: str = Field(..., description="Stock code (foreign key)")
    report_id: UUID = Field(..., description="Reference to FinancialReport")
    risk_level: RiskLevel = Field(
        ..., description="Overall risk level (LOW, MEDIUM, HIGH, CRITICAL)"
    )


class RiskScoreCreate(RiskScoreBase):
    """Model for creating a new RiskScore."""

    m_score: float = Field(..., ge=-10, le=10, description="Beneish M-Score value")
    mscore_data: MScoreData = Field(..., description="M-Score component data")
    存贷双高: bool = Field(..., description="High cash + high debt flag")
    cash_amount: Decimal = Field(..., ge=0, description="Cash and equivalents")
    debt_amount: Decimal = Field(..., ge=0, description="Interest-bearing debt")
    cash_growth_rate: float = Field(..., description="YoY cash growth rate")
    debt_growth_rate: float = Field(..., description="YoY debt growth rate")
    goodwill_ratio: float = Field(
        ..., ge=0, le=1, description="Goodwill / Equity ratio"
    )
    goodwill_excessive: bool = Field(..., description="True if goodwill_ratio > 30%")
    profit_cash_divergence: bool = Field(
        ..., description="True if net_income grew but OCF declined"
    )
    profit_growth: float = Field(..., description="YoY profit growth rate")
    ocf_growth: float = Field(..., description="YoY operating cash flow growth rate")
    red_flags: list[str] = Field(
        default_factory=list, description="List of warning messages"
    )


class RiskScoreUpdate(BaseModel):
    """Model for updating a RiskScore (all fields optional)."""

    risk_level: RiskLevel | None = None
    red_flags: list[str] | None = None


class RiskScore(RiskScoreBase):
    """Complete RiskScore model with all fields including timestamps."""

    model_config = {"frozen": True}

    score_id: UUID = Field(..., description="Unique identifier (primary key)")
    calculated_at: datetime = Field(..., description="Calculation timestamp")
    m_score: float = Field(..., ge=-10, le=10, description="Beneish M-Score value")
    mscore_data: MScoreData = Field(..., description="M-Score component data")
    存贷双高: bool = Field(..., description="High cash + high debt flag")
    cash_amount: Decimal = Field(..., ge=0, description="Cash and equivalents")
    debt_amount: Decimal = Field(..., ge=0, description="Interest-bearing debt")
    cash_growth_rate: float = Field(..., description="YoY cash growth rate")
    debt_growth_rate: float = Field(..., description="YoY debt growth rate")
    goodwill_ratio: float = Field(
        ..., ge=0, le=1, description="Goodwill / Equity ratio"
    )
    goodwill_excessive: bool = Field(..., description="True if goodwill_ratio > 30%")
    profit_cash_divergence: bool = Field(
        ..., description="True if net_income grew but OCF declined"
    )
    profit_growth: float = Field(..., description="YoY profit growth rate")
    ocf_growth: float = Field(..., description="YoY operating cash flow growth rate")
    red_flags: list[str] = Field(
        default_factory=list, description="List of warning messages"
    )


class RiskScoreInDB(RiskScore):
    """RiskScore model as stored in database (includes all fields)."""

    pass
