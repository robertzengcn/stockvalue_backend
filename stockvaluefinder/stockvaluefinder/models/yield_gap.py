"""Pydantic models for Yield Gap analysis."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import Market, YieldRecommendation


class YieldGapRequest(BaseModel):
    """Request model for yield gap analysis."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )
    cost_basis: Decimal = Field(
        ...,
        gt=0,
        description="Purchase price per share (for calculating yield based on cost)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "0700.HK", "cost_basis": 300.00},
                {"ticker": "600519.SH", "cost_basis": 1800.00},
            ]
        }


class YieldGapDataBase(BaseModel):
    """Base Pydantic model for Yield Gap result."""

    ticker: str = Field(..., description="Stock code")
    cost_basis: Decimal = Field(..., gt=0, description="Purchase price per share")
    current_price: Decimal = Field(..., gt=0, description="Current market price per share")
    gross_dividend_yield: float = Field(..., ge=0, description="Gross dividend yield (before tax)")
    net_dividend_yield: float = Field(..., ge=0, description="Net dividend yield (after tax)")
    risk_free_bond_rate: float = Field(..., ge=0, description="10-year treasury bond rate")
    risk_free_deposit_rate: float = Field(..., ge=0, description="3-year large deposit rate")
    yield_gap: float = Field(..., description="Yield gap: net_yield - max(bond, deposit)")
    recommendation: YieldRecommendation = Field(..., description="Investment recommendation")
    market: Market = Field(..., description="Market (A_SHARE or HK_SHARE)")


class YieldGapCreate(YieldGapDataBase):
    """Pydantic model for creating a YieldGap record."""

    analysis_id: UUID = Field(..., description="Unique identifier")
    calculated_at: datetime = Field(..., description="Calculation timestamp")


class YieldGapUpdate(BaseModel):
    """Pydantic model for updating a YieldGap record."""

    current_price: Decimal | None = Field(None, gt=0)
    gross_dividend_yield: float | None = Field(None, ge=0)
    net_dividend_yield: float | None = Field(None, ge=0)
    risk_free_bond_rate: float | None = Field(None, ge=0)
    risk_free_deposit_rate: float | None = Field(None, ge=0)
    yield_gap: float | None = None
    recommendation: YieldRecommendation | None = None


class YieldGap(YieldGapDataBase):
    """Complete Pydantic model for Yield Gap analysis."""

    model_config = {"frozen": True}

    analysis_id: UUID = Field(..., description="Unique identifier")
    calculated_at: datetime = Field(..., description="Calculation timestamp")
