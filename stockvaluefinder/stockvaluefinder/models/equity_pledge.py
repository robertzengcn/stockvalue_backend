"""Equity pledge domain models (Pydantic)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import DataFreshness, RiskLevel


class EquityPledgeDataQuality(BaseModel):
    """Quality metadata for equity pledge data fetch."""

    model_config = {"frozen": True}

    source: str | None = Field(None, description="Data source name (e.g., 'akshare')")
    latest_date: date | None = Field(None, description="Latest available trade date")
    fetched_at: datetime | None = Field(
        None, description="Timestamp when data was fetched"
    )
    freshness: DataFreshness = Field(..., description="Data freshness classification")
    warnings: list[str] = Field(
        default_factory=list, description="Data quality warnings"
    )


class EquityPledgeSnapshot(BaseModel):
    """Company-level equity pledge summary for a single stock."""

    model_config = {"frozen": True}

    ticker: str = Field(..., description="Stock code (e.g., '600519.SH')")
    latest_date: date | None = Field(None, description="Trade date of the pledge data")
    company_pledge_ratio: float | None = Field(
        None,
        description="Company pledge ratio as percentage (e.g., 35.5 means 35.5%)",
    )
    pledged_shares: Decimal | None = Field(None, description="Total pledged shares")
    pledge_market_value: Decimal | None = Field(
        None, description="Market value of pledged shares"
    )
    pledge_count: int | None = Field(None, description="Number of pledge transactions")
    unrestricted_pledged_shares: Decimal | None = Field(
        None, description="Unrestricted shares pledged"
    )
    restricted_pledged_shares: Decimal | None = Field(
        None, description="Restricted shares pledged"
    )
    one_year_price_change: float | None = Field(
        None, description="One-year price change as percentage"
    )
    industry: str | None = Field(None, description="Industry classification")
    data_quality: EquityPledgeDataQuality = Field(
        ..., description="Data quality metadata"
    )


class EquityPledgeDetail(BaseModel):
    """Important shareholder pledge detail record."""

    model_config = {"frozen": True}

    ticker: str = Field(..., description="Stock code (e.g., '600519.SH')")
    stock_name: str | None = Field(None, description="Stock name")
    holder_name: str = Field(..., description="Shareholder name")
    is_controlling_holder: bool = Field(
        False, description="Whether this is the controlling shareholder"
    )
    pledge_amount: Decimal | None = Field(
        None, description="Number of shares pledged in this record"
    )
    pledged_to_holding_ratio: float | None = Field(
        None, description="Pledged / holding ratio as percentage"
    )
    pledged_to_total_share_ratio: float | None = Field(
        None, description="Pledged / total shares ratio as percentage"
    )
    pledgee: str | None = Field(None, description="Pledgee institution")
    latest_price: float | None = Field(None, description="Latest stock price")
    pledge_date_close_price: float | None = Field(
        None, description="Stock closing price on pledge date"
    )
    estimated_closeout_price: float | None = Field(
        None, description="Estimated forced-sell price"
    )
    start_date: date | None = Field(None, description="Pledge start date")
    announcement_date: date | None = Field(None, description="Announcement date")
    source: str = Field(..., description="Data source identifier")


# ---------------------------------------------------------------------------
# Pledge risk result models (Phase 30)
# ---------------------------------------------------------------------------


class PledgeRiskGrade(BaseModel):
    """Base grading result shared across pledge risk dimensions."""

    model_config = {"frozen": True}

    risk_level: RiskLevel = Field(..., description="Risk level for this dimension")
    notes: list[str] = Field(
        default_factory=list,
        description="Additional context notes for borderline ranges",
    )


class CompanyPledgeRisk(BaseModel):
    """Company overall pledge ratio risk grading result (RISK-01)."""

    model_config = {"frozen": True}

    risk_level: RiskLevel = Field(..., description="Company pledge risk level")
    company_pledge_ratio: float | None = Field(
        None, description="Company pledge ratio as percentage"
    )
    notes: list[str] = Field(
        default_factory=list, description="Additional context notes"
    )


class HolderPledgeRisk(BaseModel):
    """Controlling shareholder pledge risk grading result (RISK-02, RISK-08)."""

    model_config = {"frozen": True}

    risk_level: RiskLevel = Field(..., description="Holder pledge risk level")
    pledged_to_holding_ratio: float | None = Field(
        None, description="Pledged to holding ratio as percentage"
    )
    holder_name: str | None = Field(None, description="Controlling shareholder name")
    controlling_holder: bool = Field(
        False, description="Whether a controlling holder was identified"
    )
    notes: list[str] = Field(
        default_factory=list, description="Additional context notes"
    )


class CloseoutRisk(BaseModel):
    """Closeout safety margin risk grading result (RISK-03)."""

    model_config = {"frozen": True}

    risk_level: RiskLevel = Field(..., description="Closeout risk level")
    safety_margin: float | None = Field(
        None, description="Safety margin as percentage above closeout price"
    )
    latest_price: float | None = Field(None, description="Latest stock price")
    estimated_closeout_price: float | None = Field(
        None, description="Estimated forced-sell price"
    )
    notes: list[str] = Field(
        default_factory=list, description="Additional context notes"
    )


class RiskLevelBreakdown(BaseModel):
    """Breakdown showing how financial and pledge risk were merged (RISK-05)."""

    model_config = {"frozen": True}

    financial_risk_level: RiskLevel = Field(
        ..., description="Financial risk level from RiskAnalyzer"
    )
    pledge_risk_level: RiskLevel | None = Field(
        None, description="Pledge risk level (None when pledge data unavailable)"
    )
    final_risk_level: RiskLevel = Field(
        ..., description="Final merged risk level (pledge can only upgrade)"
    )
    merge_reason: str | None = Field(
        None, description="Explanation when pledge upgrades the overall level"
    )


class PledgeRiskResult(BaseModel):
    """Complete pledge risk analysis result for a single stock.

    Consumed by Phase 31 for persistence and API integration.
    """

    model_config = {"frozen": True}

    supported: bool = Field(
        True, description="False for HK tickers where pledge data is unavailable"
    )
    company_risk: CompanyPledgeRisk | None = Field(
        None, description="Company pledge ratio risk grading"
    )
    holder_risk: HolderPledgeRisk | None = Field(
        None, description="Controlling shareholder pledge risk grading"
    )
    closeout_risk: CloseoutRisk | None = Field(
        None, description="Closeout safety margin risk grading"
    )
    combination_upgrades: list[str] = Field(
        default_factory=list,
        description="Triggered combination upgrade rule descriptions",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Structured warning messages for each triggered condition",
    )
    data_quality: EquityPledgeDataQuality = Field(
        ..., description="Data quality metadata"
    )
    risk_level_breakdown: RiskLevelBreakdown = Field(
        ..., description="Financial vs pledge risk merge breakdown"
    )
