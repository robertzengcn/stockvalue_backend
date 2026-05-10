"""Pydantic models for stock access management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class StockAccessEntry(BaseModel):
    """A single stock access entry for a user.

    Attributes:
        ticker: Stock ticker in format NNNNNN.XX (e.g., 600519.SH)
        created_at: When this access entry was created
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock ticker in format NNNNNN.XX (e.g., 600519.SH)",
    )
    created_at: datetime = Field(
        ...,
        description="When this access entry was created",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH", "created_at": "2026-05-10T00:00:00Z"},
            ]
        }


class StockAccessListResponse(BaseModel):
    """Response containing all stock access entries for a user.

    Attributes:
        user_id: The user's UUID
        tickers: List of stock access entries (empty means access to all stocks)
    """

    user_id: UUID = Field(..., description="User unique identifier")
    tickers: list[StockAccessEntry] = Field(
        default_factory=list,
        description="List of accessible stock tickers (empty = all stocks)",
    )


class StockAccessUpdateRequest(BaseModel):
    """Request to replace all stock access entries for a user.

    Attributes:
        tickers: List of tickers to set as the user's accessible stocks
    """

    tickers: list[str] = Field(
        ...,
        min_length=1,
        description="List of tickers to set",
    )

    @field_validator("tickers")
    @classmethod
    def validate_ticker_formats(cls, v: list[str]) -> list[str]:
        """Validate all tickers match the required format."""
        import re

        pattern = r"^\d{6}\.(SH|SZ|HK)$"
        for ticker in v:
            if not re.match(pattern, ticker):
                raise ValueError(
                    f"Invalid ticker format: {ticker}. "
                    "Expected format: NNNNNN.XX (e.g., 600519.SH)"
                )
        return v

    class Config:
        json_schema_extra = {
            "examples": [
                {"tickers": ["600519.SH", "000001.SZ"]},
            ]
        }


class StockAccessAddRequest(BaseModel):
    """Request to add a single stock access entry.

    Attributes:
        ticker: Stock ticker to add to user's accessible list
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock ticker to add (e.g., 600519.SH)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
            ]
        }


class StockAccessRemoveRequest(BaseModel):
    """Request to remove a single stock access entry.

    Attributes:
        ticker: Stock ticker to remove from user's accessible list
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{6}\.(SH|SZ|HK)$",
        description="Stock ticker to remove (e.g., 600519.SH)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"ticker": "600519.SH"},
            ]
        }
