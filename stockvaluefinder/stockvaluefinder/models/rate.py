"""Interest rate domain models (Pydantic)."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RateDataBase(BaseModel):
    """Base RateData model with common fields."""

    rate_date: date = Field(..., description="Date of rate")
    ten_year_treasury: float = Field(
        ...,
        ge=0.0,
        le=0.20,
        description="10-year government bond yield (0-20%)",
    )
    three_year_deposit: float = Field(
        ...,
        ge=0.0,
        le=0.20,
        description="3-year large deposit rate (0-20%)",
    )
    one_year_deposit: float = Field(
        ...,
        ge=0.0,
        le=0.20,
        description="1-year deposit rate (0-20%)",
    )
    benchmark_rate: float = Field(
        ...,
        ge=0.0,
        le=0.20,
        description="Central bank benchmark rate (0-20%)",
    )
    rate_source: str = Field(
        ...,
        min_length=1,
        description="Source of data (PBOC, HKMA, etc.)",
    )


class RateDataCreate(RateDataBase):
    """Model for creating new RateData."""

    @field_validator("rate_date")
    @classmethod
    def validate_rate_date_not_future(cls, v: date) -> date:
        """Ensure rate_date is not in the future."""
        from datetime import datetime

        if v > datetime.now().date():
            raise ValueError("Rate date cannot be in the future")
        return v

    @field_validator("rate_source")
    @classmethod
    def validate_source_not_empty(cls, v: str) -> str:
        """Ensure source is not empty or whitespace."""
        if not v.strip():
            raise ValueError("Rate source cannot be empty or whitespace")
        return v.strip()


class RateDataUpdate(BaseModel):
    """Model for updating RateData (all fields optional)."""

    ten_year_treasury: float | None = Field(None, ge=0.0, le=0.20)
    three_year_deposit: float | None = Field(None, ge=0.0, le=0.20)
    one_year_deposit: float | None = Field(None, ge=0.0, le=0.20)
    benchmark_rate: float | None = Field(None, ge=0.0, le=0.20)
    rate_source: str | None = Field(None, min_length=1)


class RateData(RateDataBase):
    """Complete RateData model with all fields including timestamps."""

    model_config = {"frozen": True}

    rate_id: UUID = Field(..., description="Unique identifier (primary key)")
    created_at: datetime = Field(..., description="Record creation timestamp")


class RateDataInDB(RateData):
    """RateData model as stored in database (includes all fields)."""

    pass
