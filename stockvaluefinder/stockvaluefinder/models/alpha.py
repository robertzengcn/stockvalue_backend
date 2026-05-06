"""Alpha composite score domain models (Pydantic).

This module defines all Pydantic models for the Alpha composite score,
which aggregates four forward-looking analysis dimensions into a single
0-100 score with fixed transparent weights (40/30/20/10).

Key models:
    - AlphaComponentScores: Individual normalized component scores with raw values
    - AlphaRequest: API request model
    - AlphaAnalysisResult: Complete analysis result with audit trail
    - AlphaScoreCreate: Persistence model for repository layer
    - AlphaScoreUpdate: Partial update model for repository layer
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import AlphaLevel


class AlphaComponentScores(BaseModel):
    """Normalized component scores with original raw values for audit.

    Each component is normalized to 0-100 before being weighted into
    the composite Alpha score.

    Attributes:
        roic_wacc_score: Normalized ROIC-WACC spread score (0-100).
        roic_wacc_raw: Original spread value (decimal, e.g. 0.05).
        capex_score: Normalized capital allocation score (0-100).
        capex_raw_grade: Original letter grade (A/B/C/D).
        policy_score: Policy resonance score (0-100, pass-through).
        policy_raw_score: Original resonance score from policy engine.
        moat_score: Normalized moat trend score (0-100).
        moat_raw_trend: Original MoatTrend enum value string, or None.
    """

    roic_wacc_score: float = Field(
        ..., ge=0.0, le=100.0, description="Normalized ROIC-WACC spread (0-100)"
    )
    roic_wacc_raw: float | None = Field(
        None, description="Original spread value (decimal)"
    )
    capex_score: float = Field(
        ..., ge=0.0, le=100.0, description="Normalized capital allocation (0-100)"
    )
    capex_raw_grade: str = Field(..., description="Original letter grade (A/B/C/D)")
    policy_score: float = Field(
        ..., ge=0.0, le=100.0, description="Policy resonance score (0-100)"
    )
    policy_raw_score: float = Field(
        ..., description="Original resonance score from policy engine"
    )
    moat_score: float = Field(
        ..., ge=0.0, le=100.0, description="Normalized moat trend (0-100)"
    )
    moat_raw_trend: str | None = Field(
        None, description="Original MoatTrend value string"
    )

    model_config = {"frozen": True}


class AlphaRequest(BaseModel):
    """Request model for Alpha composite score analysis.

    Attributes:
        ticker: Stock code matching pattern NNNNNN.{SH|SZ|HK}.
        year: Optional fiscal year (defaults to most recent).
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., 600519.SH)",
    )
    year: int | None = Field(None, ge=2000, le=2099)

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
                {"ticker": "600519.SH", "year": 2023},
            ]
        }


class AlphaAnalysisResult(BaseModel):
    """Complete Alpha composite score analysis result.

    Aggregates four forward-looking dimensions with fixed weights (D-01):
    ROIC-WACC (40%), Capital Allocation (30%), Policy (20%), Moat (10%).

    Attributes:
        ticker: Stock code.
        fiscal_year: Fiscal year of analysis.
        component_scores: Normalized scores with raw values.
        alpha_score: Weighted composite score (0-100).
        alpha_level: Classification tier (EXCELLENT/GOOD/FAIR/WEAK/POOR).
        weights_used: Actual weights applied per dimension.
        dcf_adjustment_summary: Policy resonance DCF terminal growth adjustment.
        audit_trail: Calculation audit trail with input provenance.
        calculated_at: Timestamp of calculation.
    """

    ticker: str = Field(..., description="Stock code")
    fiscal_year: int = Field(..., description="Fiscal year of analysis")
    component_scores: AlphaComponentScores = Field(
        ..., description="Normalized component scores with raw values"
    )
    alpha_score: float = Field(
        ..., ge=0.0, le=100.0, description="Composite Alpha score (0-100)"
    )
    alpha_level: AlphaLevel = Field(..., description="Classification tier")
    weights_used: dict[str, float] = Field(
        ..., description="Actual weights applied per dimension"
    )
    dcf_adjustment_summary: dict[str, Any] | None = Field(
        None, description="Policy resonance DCF adjustment details"
    )
    audit_trail: dict[str, Any] = Field(
        default_factory=dict, description="Calculation audit trail"
    )
    calculated_at: datetime = Field(..., description="Timestamp of calculation")

    model_config = {"frozen": True}


class AlphaScoreCreate(BaseModel):
    """Model for creating an Alpha score in the database.

    Used for persistence via the repository layer. Contains all component
    scores, composite score, weights, and audit information.

    Attributes:
        analysis_id: Unique identifier for this analysis.
        ticker: Stock code.
        fiscal_year: Fiscal year of analysis.
        roic_wacc_score: Normalized ROIC-WACC component score.
        roic_wacc_raw: Original spread value.
        capex_score: Normalized capital allocation score.
        capex_raw_grade: Original letter grade.
        policy_score: Policy resonance score.
        policy_raw_score: Original resonance score.
        moat_score: Normalized moat trend score.
        moat_raw_trend: Original MoatTrend value string.
        alpha_score: Composite Alpha score.
        weights_used: Weights applied per dimension.
        dcf_adjustment_summary: DCF adjustment details.
        audit_trail: Calculation audit trail.
    """

    analysis_id: UUID
    ticker: str
    fiscal_year: int
    roic_wacc_score: float
    roic_wacc_raw: float | None
    capex_score: float
    capex_raw_grade: str
    policy_score: float
    policy_raw_score: float
    moat_score: float
    moat_raw_trend: str | None
    alpha_score: float
    weights_used: dict[str, float]
    dcf_adjustment_summary: dict[str, Any] | None
    audit_trail: dict[str, Any]


class AlphaScoreUpdate(BaseModel):
    """Model for updating an Alpha score.

    Used by the repository layer for partial updates. All fields are
    optional -- only provided fields will be updated.

    Attributes:
        alpha_score: Updated composite score.
        audit_trail: Updated audit trail.
    """

    alpha_score: float | None = None
    audit_trail: dict[str, Any] | None = None
