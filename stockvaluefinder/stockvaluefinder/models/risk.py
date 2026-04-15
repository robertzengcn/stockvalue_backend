"""Risk score domain models (Pydantic)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from stockvaluefinder.models.enums import RiskLevel


class IndexAuditDetail(BaseModel):
    """Audit trail for a single M-Score index calculation."""

    model_config = {"frozen": True}

    value: float = Field(..., description="Calculated index value")
    numerator: float = Field(..., description="Numerator used in calculation")
    denominator: float = Field(..., description="Denominator used in calculation")
    source_fields: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of internal field name to source field (e.g., {'accounts_receivable': 'ACCOUNTS_RECE (AKShare)'})",
    )
    non_calculable: bool = Field(
        default=False, description="True if this index could not be calculated"
    )
    reason: str | None = Field(default=None, description="Reason if non_calculable")


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
    audit_trail: dict[str, IndexAuditDetail] = Field(
        default_factory=dict,
        description="Per-index audit trail with intermediate values and source references",
    )


class FScoreData(BaseModel):
    """Piotroski F-Score component data."""

    model_config = {"frozen": True}

    positive_roa: bool = Field(..., description="ROA > 0")
    positive_cfo: bool = Field(..., description="Operating cash flow > 0")
    improving_roa: bool = Field(..., description="Current ROA > previous ROA")
    cfo_exceeds_roa: bool = Field(
        ..., description="Operating cash flow quality is strong"
    )
    lower_leverage: bool = Field(..., description="Leverage ratio declined YoY")
    higher_liquidity: bool = Field(..., description="Liquidity ratio improved YoY")
    no_new_shares: bool = Field(..., description="No significant share dilution YoY")
    improving_margin: bool = Field(..., description="Gross margin improved YoY")
    improving_turnover: bool = Field(..., description="Asset turnover improved YoY")


class RiskScoreBase(BaseModel):
    """Base RiskScore model with common fields."""

    ticker: str = Field(..., description="Stock code (foreign key)")
    report_id: UUID = Field(..., description="Reference to FinancialReport")
    risk_level: RiskLevel = Field(
        ..., description="Overall risk level (LOW, MEDIUM, HIGH, CRITICAL)"
    )


class RiskScoreCreate(RiskScoreBase):
    """Model for creating a new RiskScore."""

    score_id: UUID = Field(..., description="Unique identifier (primary key)")
    m_score: float = Field(..., ge=-10, le=10, description="Beneish M-Score value")
    mscore_data: MScoreData = Field(..., description="M-Score component data")
    f_score: int = Field(..., ge=0, le=9, description="Piotroski F-Score value")
    fscore_data: FScoreData = Field(..., description="F-Score component data")
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
    narrative: str | None = Field(None, description="LLM-generated narrative JSON")


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
    f_score: int = Field(..., ge=0, le=9, description="Piotroski F-Score value")
    fscore_data: FScoreData = Field(..., description="F-Score component data")
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

    @field_serializer("cash_amount", "debt_amount")
    def serialize_decimal(self, value: Decimal) -> float:
        """Serialize Decimal to float for JSON responses."""
        return float(value)


class RiskScoreInDB(RiskScore):
    """RiskScore model as stored in database (includes all fields)."""

    pass
