"""Capital allocation scorecard domain models (Pydantic).

This module defines all Pydantic models for the capital allocation scorecard,
which evaluates how well management deploys shareholder capital across three
dimensions: buyback yield, dividend stability, and expansion discipline.

Each dimension independently rated A/B/C/D, then averaged with equal weights
(1/3 each) to produce a combined scorecard grade.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CapitalAllocationGrade(str, Enum):
    """Capital allocation scorecard letter grade (D-07)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class DividendTrend(str, Enum):
    """Dividend per unit stability trend classification (D-04)."""

    GROWTH = "Growth"
    DECLINE = "Decline"
    STABLE = "Stable"
    INSUFFICIENT_DATA = "Insufficient Data"


class BuybackYieldResult(BaseModel):
    """Result of buyback yield dimension analysis (CAPEX-01).

    Attributes:
        buyback_yield: Yield as decimal (e.g. 0.02 = 2%), None when no data.
        repurchase_amount: Actual repurchase amount in CNY.
        market_cap: Market cap used for calculation.
        data_quality: "COMPLETE" or "INCOMPLETE" (in-progress programs).
        grade: A/B/C/D grade for this dimension.
    """

    buyback_yield: float | None = Field(
        None, description="Buyback yield as decimal (0.02 = 2%)"
    )
    repurchase_amount: float | None = Field(
        None, description="Actual repurchase amount in CNY"
    )
    market_cap: float | None = Field(
        None, description="Market cap used for yield calculation"
    )
    data_quality: str = Field(
        ..., description="COMPLETE or INCOMPLETE for in-progress programs"
    )
    grade: CapitalAllocationGrade = Field(
        ..., description="A/B/C/D grade for buyback yield dimension"
    )

    model_config = {"frozen": True}


class DividendStabilityResult(BaseModel):
    """Result of dividend stability dimension analysis (CAPEX-02).

    Attributes:
        classification: GROWTH/DECLINE/STABLE/INSUFFICIENT_DATA.
        slope: Linear regression slope from scipy linregress.
        p_value: Statistical significance of the trend.
        data_points: Number of valid DPU data points used.
        dpu_values: Actual dividend per unit values used.
        grade: A/B/C/D grade for this dimension.
    """

    classification: DividendTrend = Field(..., description="DPU trend classification")
    slope: float | None = Field(None, description="Linear regression slope")
    p_value: float | None = Field(
        None, description="Statistical significance (p-value)"
    )
    data_points: int = Field(..., description="Number of valid DPU data points used")
    dpu_values: list[float] = Field(
        ..., description="Actual DPU values used in regression"
    )
    grade: CapitalAllocationGrade = Field(
        ..., description="A/B/C/D grade for dividend stability dimension"
    )

    model_config = {"frozen": True}


class ExpansionDisciplineResult(BaseModel):
    """Result of expansion discipline dimension analysis (CAPEX-03).

    Attributes:
        alert: True if blind expansion detected (ROIC < WACC AND CapEx surge).
        roic_wacc_spread: ROIC - WACC spread from Phase 9.
        capex_yoy_growth: Year-over-year CapEx growth rate.
        capex_current: Current year capital expenditure.
        capex_previous: Previous year capital expenditure.
        reason: Explanation when no alert (e.g. "insufficient_data").
        grade: A/B/C/D grade for this dimension.
    """

    alert: bool = Field(..., description="True if blind expansion detected")
    roic_wacc_spread: float | None = Field(None, description="ROIC - WACC spread")
    capex_yoy_growth: float | None = Field(
        None, description="Year-over-year CapEx growth rate"
    )
    capex_current: float | None = Field(
        None, description="Current year capital expenditure"
    )
    capex_previous: float | None = Field(
        None, description="Previous year capital expenditure"
    )
    reason: str | None = Field(None, description="Explanation when no alert")
    grade: CapitalAllocationGrade = Field(
        ..., description="A/B/C/D grade for expansion discipline dimension"
    )

    model_config = {"frozen": True}


class CapitalAllocationRequest(BaseModel):
    """Request model for capital allocation scorecard analysis.

    Attributes:
        ticker: Stock code matching pattern NNNNNN.{SH|SZ|HK}.
        year: Optional fiscal year (defaults to most recent).
    """

    ticker: str = Field(..., pattern=r"^\d{6}\.(SH|SZ|HK)$")
    year: int | None = Field(None, ge=2000, le=2099)

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
                {"ticker": "600519.SH", "year": 2023},
            ]
        }


class CapitalAllocationResult(BaseModel):
    """Complete capital allocation scorecard result (CAPEX-04).

    Combines three dimensions with equal weighting (D-08) into a single
    A/B/C/D grade. Missing buyback data triggers reweighting to 50/50
    for the remaining two dimensions.

    Attributes:
        ticker: Stock code.
        fiscal_year: Fiscal year of analysis.
        buyback_yield: Buyback dimension result.
        dividend_stability: Dividend dimension result.
        expansion_discipline: Expansion dimension result.
        overall_grade: Combined A/B/C/D scorecard grade.
        weighting: Actual weights used per dimension.
        audit_trail: Calculation audit trail.
        calculated_at: Timestamp of calculation.
    """

    ticker: str = Field(..., description="Stock code")
    fiscal_year: int = Field(..., description="Fiscal year of analysis")
    buyback_yield: BuybackYieldResult = Field(
        ..., description="Buyback yield dimension result"
    )
    dividend_stability: DividendStabilityResult = Field(
        ..., description="Dividend stability dimension result"
    )
    expansion_discipline: ExpansionDisciplineResult = Field(
        ..., description="Expansion discipline dimension result"
    )
    overall_grade: CapitalAllocationGrade = Field(
        ..., description="Combined A/B/C/D scorecard grade"
    )
    weighting: dict[str, float] = Field(
        ..., description="Actual weights used per dimension"
    )
    audit_trail: dict[str, Any] = Field(
        default_factory=dict, description="Calculation audit trail"
    )
    calculated_at: datetime = Field(..., description="Timestamp of calculation")

    model_config = {"frozen": True}


class CapitalAllocationScoreCreate(BaseModel):
    """Model for creating a capital allocation score in the database.

    Used for persistence via the repository layer. Contains serialized
    versions of the dimension results suitable for JSON columns.

    Attributes:
        analysis_id: Unique identifier for this analysis.
        ticker: Stock code.
        fiscal_year: Fiscal year of analysis.
        buyback_yield_data: Serialized buyback yield result.
        dividend_stability_data: Serialized dividend stability result.
        expansion_discipline_data: Serialized expansion discipline result.
        overall_grade: Combined grade as string.
        weighting: Weighting used per dimension.
        audit_trail: Calculation audit trail.
    """

    analysis_id: UUID
    ticker: str
    fiscal_year: int
    buyback_yield_data: dict[str, Any]
    dividend_stability_data: dict[str, Any]
    expansion_discipline_data: dict[str, Any]
    overall_grade: str
    weighting: dict[str, float]
    audit_trail: dict[str, Any]


class CapitalAllocationScoreUpdate(BaseModel):
    """Model for updating a capital allocation score.

    Used by the repository layer for partial updates. All fields are
    optional -- only provided fields will be updated.

    Attributes:
        overall_grade: Updated combined grade.
        audit_trail: Updated audit trail.
    """

    overall_grade: str | None = None
    audit_trail: dict[str, Any] | None = None
