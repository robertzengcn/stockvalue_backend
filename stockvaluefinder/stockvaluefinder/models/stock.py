"""Stock domain models (Pydantic)."""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from stockvaluefinder.models.enums import Market


class StockBase(BaseModel):
    """Base Stock model with common fields."""

    name: str = Field(..., min_length=1, description="Company name")
    market: Market = Field(..., description="Market enum (A_SHARE, HK_SHARE)")
    industry: str = Field(..., min_length=1, description="Industry sector")
    list_date: date = Field(..., description="Listing date")


class StockCreate(StockBase):
    """Model for creating a new Stock."""

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock code (e.g., '600519.SH', '0700.HK')",
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        """Normalize ticker to uppercase."""
        return v.upper()

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure name is not empty or whitespace."""
        if not v.strip():
            raise ValueError("Company name cannot be empty or whitespace")
        return v.strip()


class StockUpdate(BaseModel):
    """Model for updating a Stock (all fields optional)."""

    name: str | None = Field(None, min_length=1)
    industry: str | None = Field(None, min_length=1)
    list_date: date | None = None


class Stock(StockBase):
    """Complete Stock model with all fields including timestamps."""

    model_config = {"frozen": True}

    ticker: str = Field(..., description="Stock code (primary key)")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class StockInDB(Stock):
    """Stock model as stored in database (includes all fields)."""

    pass
