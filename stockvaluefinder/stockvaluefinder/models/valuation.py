"""Pydantic models for DCF Valuation analysis."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from stockvaluefinder.models.enums import ValuationLevel


class DCFValuationRequest(BaseModel):
    """Request model for DCF valuation analysis."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )
    growth_rate_stage1: float = Field(
        default=0.05,
        ge=-0.5,
        le=1.0,
        description="Growth rate for stage 1 (high growth), as decimal (e.g., 0.05 for 5%)",
    )
    growth_rate_stage2: float = Field(
        default=0.03,
        ge=-0.1,
        le=0.5,
        description="Growth rate for stage 2 (stable growth), as decimal",
    )
    years_stage1: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of years for high-growth stage",
    )
    years_stage2: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Number of years for stable-growth stage (0 for direct terminal)",
    )
    terminal_growth: float = Field(
        default=0.025,
        ge=-0.05,
        le=0.10,
        description="Terminal growth rate (perpetual), as decimal",
    )
    risk_free_rate: float | None = Field(
        default=None,
        ge=0,
        le=0.20,
        description="Risk-free rate (overrides current rate if provided)",
    )
    beta: float | None = Field(
        default=None,
        ge=0,
        le=3.0,
        description="Beta (overrides default if provided)",
    )
    market_risk_premium: float | None = Field(
        default=None,
        ge=0.01,
        le=0.15,
        description="Market risk premium (overrides default if provided)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "ticker": "000002.SZ",
                    "growth_rate_stage1": 0.05,
                    "growth_rate_stage2": 0.03,
                },
                {
                    "ticker": "600519.SH",
                    "growth_rate_stage1": 0.08,
                    "years_stage1": 10,
                },
            ]
        }


class DCFParams(BaseModel):
    """DCF calculation parameters."""

    growth_rate_stage1: float = Field(..., description="Stage 1 growth rate")
    growth_rate_stage2: float = Field(..., description="Stage 2 growth rate")
    years_stage1: int = Field(..., description="Stage 1 years")
    years_stage2: int = Field(..., description="Stage 2 years")
    terminal_growth: float = Field(..., description="Terminal growth rate")
    risk_free_rate: float = Field(..., description="Risk-free rate")
    beta: float = Field(..., description="Beta")
    market_risk_premium: float = Field(..., description="Market risk premium")


class ValuationResultBase(BaseModel):
    """Base Pydantic model for DCF valuation result."""

    ticker: str = Field(..., description="Stock code")
    current_price: Decimal = Field(
        ..., gt=0, description="Current market price per share"
    )
    intrinsic_value: Decimal = Field(
        ..., description="Calculated intrinsic value per share"
    )
    wacc: float = Field(..., ge=0, description="Weighted average cost of capital")
    margin_of_safety: float = Field(
        ..., description="Margin of safety (intrinsic - price) / price"
    )
    valuation_level: ValuationLevel = Field(
        ..., description="Valuation level (UNDERVALUED, FAIR_VALUE, OVERVALUED)"
    )

    @field_serializer("current_price", "intrinsic_value")
    def serialize_decimal(self, value: Decimal | None) -> float | None:
        """Serialize Decimal to float for JSON responses."""
        return float(value) if value is not None else None


class ValuationResultCreate(ValuationResultBase):
    """Pydantic model for creating a ValuationResult record."""

    valuation_id: UUID = Field(..., description="Unique identifier")
    calculated_at: datetime = Field(..., description="Calculation timestamp")
    dcf_params: DCFParams = Field(..., description="DCF parameters used")
    audit_trail: dict[str, Any] = Field(..., description="Full calculation audit trail")


class ValuationResultUpdate(BaseModel):
    """Pydantic model for updating a ValuationResult record."""

    current_price: Decimal | None = Field(None, gt=0)
    intrinsic_value: Decimal | None = None
    wacc: float | None = Field(None, ge=0)
    margin_of_safety: float | None = None
    valuation_level: ValuationLevel | None = None


class ValuationResult(ValuationResultBase):
    """Complete Pydantic model for DCF valuation result."""

    model_config = {"frozen": True}

    valuation_id: UUID = Field(..., description="Unique identifier")
    calculated_at: datetime = Field(..., description="Calculation timestamp")
    dcf_params: DCFParams = Field(..., description="DCF parameters used")
    audit_trail: dict[str, Any] = Field(..., description="Full calculation audit trail")
