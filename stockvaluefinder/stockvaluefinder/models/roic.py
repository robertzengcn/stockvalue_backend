"""ROIC-WACC spread analysis domain models (Pydantic)."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SpreadClassification(str, Enum):
    """ROIC-WACC spread classification."""

    VALUE_CREATING = "Value Creating"
    VALUE_DESTROYING = "Value Destroying"
    INSUFFICIENT_DATA = "Insufficient Data"


class MoatTrend(str, Enum):
    """Competitive moat trend classification."""

    COMPETITIVE_ADVANTAGE = "Competitive Advantage"
    DETERIORATING = "Deteriorating"
    STABLE = "Stable"
    INSUFFICIENT_DATA = "Insufficient Data"


class WACCBreakdown(BaseModel):
    """Detailed WACC calculation breakdown."""

    ke: float = Field(..., description="Cost of equity (CAPM)")
    kd: float | None = Field(None, description="Pre-tax cost of debt")
    equity_weight: float = Field(..., description="Weight of equity in capital structure")
    debt_weight: float = Field(..., description="Weight of debt in capital structure")
    de_ratio: float | None = Field(None, description="Debt-to-equity ratio")
    tax_rate: float | None = Field(None, description="Corporate tax rate")
    wacc: float = Field(..., description="Final WACC value")

    model_config = {"frozen": True}


class MoatTrendResult(BaseModel):
    """Result of moat trend analysis using linear regression."""

    trend: MoatTrend = Field(..., description="Detected moat trend")
    slope: float | None = Field(None, description="Regression slope (per year)")
    p_value: float | None = Field(None, description="Statistical significance")
    data_points: int = Field(..., description="Number of valid data points used")

    model_config = {"frozen": True}


class ROICAnalysisRequest(BaseModel):
    """Request model for ROIC analysis."""

    ticker: str = Field(..., pattern=r"^\d{6}\.(SH|SZ|HK)$")
    year: int | None = Field(None, ge=2000, le=2099)

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
                {"ticker": "601398.SH", "year": 2023},
            ]
        }


class ROICAnalysisResult(BaseModel):
    """Complete ROIC analysis result with all computed metrics."""

    ticker: str = Field(..., description="Stock code")
    fiscal_year: int = Field(..., description="Fiscal year of analysis")
    roic: float | None = Field(None, description="Return on Invested Capital")
    negative_invested_capital: bool = Field(
        False, description="True if invested capital is negative"
    )
    nopat: float | None = Field(None, description="Net Operating Profit After Tax")
    invested_capital: float | None = Field(None, description="Total invested capital")
    wacc_breakdown: WACCBreakdown = Field(..., description="WACC calculation details")
    spread: float | None = Field(None, description="ROIC - WACC spread")
    spread_classification: SpreadClassification = Field(
        ..., description="Value creating/destroying classification"
    )
    moat_trend: MoatTrendResult | None = Field(
        None, description="Multi-year moat trend analysis"
    )
    is_financial_sector: bool = Field(
        False, description="True if stock is in financial sector"
    )
    audit_trail: dict[str, Any] = Field(
        default_factory=dict, description="Calculation audit trail"
    )
    calculated_at: datetime = Field(..., description="Timestamp of calculation")

    model_config = {"frozen": True}


class ROICResultCreate(BaseModel):
    """Model for creating a ROIC result in the database."""

    analysis_id: UUID
    ticker: str
    fiscal_year: int
    roic: float | None
    negative_invested_capital: bool
    nopat: float | None
    invested_capital: float | None
    wacc: float
    wacc_breakdown: dict[str, Any]
    spread: float | None
    spread_classification: str
    moat_trend: dict[str, Any] | None
    is_financial_sector: bool
    audit_trail: dict[str, Any]


class ROICResultUpdate(BaseModel):
    """Model for updating a ROIC result."""

    roic: float | None = None
    spread: float | None = None
    spread_classification: str | None = None
    audit_trail: dict[str, Any] | None = None
