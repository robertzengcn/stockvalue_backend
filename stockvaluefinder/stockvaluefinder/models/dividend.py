"""Pydantic models for Dividend data."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import DividendFrequency


class DividendDataBase(BaseModel):
    """Base Pydantic model for Dividend data."""

    ticker: str = Field(..., description="Stock code")
    ex_dividend_date: date = Field(..., description="Ex-dividend date")
    dividend_per_share: Decimal = Field(
        ..., ge=0, description="Dividend amount per share (CNY/HKD)"
    )
    dividend_frequency: DividendFrequency = Field(
        ..., description="Dividend frequency (ANNUAL, SEMI_ANNUAL, QUARTERLY, SPECIAL)"
    )
    fiscal_year: int | None = Field(
        None, ge=1990, le=2100, description="Fiscal year of dividend payment"
    )


class DividendCreate(DividendDataBase):
    """Pydantic model for creating a Dividend record."""

    pass


class DividendUpdate(BaseModel):
    """Pydantic model for updating a Dividend record."""

    dividend_per_share: Decimal | None = Field(
        None, ge=0, description="Dividend amount per share"
    )
    dividend_frequency: DividendFrequency | None = Field(
        None, description="Dividend frequency"
    )


class Dividend(DividendDataBase):
    """Complete Pydantic model for Dividend with immutable fields."""

    model_config = {"frozen": True}

    dividend_id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
