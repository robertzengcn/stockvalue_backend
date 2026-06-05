"""Equity pledge domain models (Pydantic)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import DataFreshness


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
