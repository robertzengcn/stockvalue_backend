"""Pydantic domain models for the pipeline module.

Defines request/response models for pipeline task creation,
document creation, health status reporting, watchlist management,
watcher state tracking, and pending disclosure staging.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PipelineTaskCreate(BaseModel):
    """Request model for creating a new pipeline task.

    Attributes:
        ticker: Stock ticker in format NNNNNN.{SH|SZ|HK}.
        business_key: Unique identifier for deduplication (ticker:fiscal_year:report_type).
        fiscal_year: The fiscal year of the report.
        report_type: Type of report (e.g., "annual", "quarterly").
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{4,6}\.(SH|SZ|HK)$",
        description="Stock ticker: 6 digits for SH/SZ, 4-5 digits for HK",
    )
    business_key: str = Field(
        ...,
        min_length=1,
        description="Unique business key for deduplication (e.g., ticker:fiscal_year:report_type)",
    )
    fiscal_year: int = Field(
        ...,
        ge=2000,
        le=2100,
        description="Fiscal year of the report",
    )
    report_type: str = Field(
        ...,
        description="Report type (e.g., annual, quarterly)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "600519.SH",
                    "business_key": "600519.SH:2023:annual",
                    "fiscal_year": 2023,
                    "report_type": "annual",
                }
            ]
        }
    }


class PipelineDocumentCreate(BaseModel):
    """Request model for creating a pipeline document record.

    Attributes:
        task_id: Foreign key to the pipeline task.
        source_url: URL where the document was downloaded from.
        source_id: Announcement/source identifier for deduplication.
        content_hash: SHA256 hash of the document content.
        file_path: Local filesystem path where the file is stored.
        file_size: Size of the file in bytes.
    """

    task_id: str = Field(
        ...,
        description="Foreign key to the pipeline task",
    )
    source_url: str | None = Field(
        None,
        description="URL where the document was downloaded from",
    )
    source_id: str | None = Field(
        None,
        description="Announcement/source identifier for deduplication",
    )
    content_hash: str | None = Field(
        None,
        description="SHA256 hash of the document content",
    )
    file_path: str | None = Field(
        None,
        description="Local filesystem path where the file is stored",
    )
    file_size: int | None = Field(
        None,
        ge=0,
        description="Size of the file in bytes",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "550e8400-e29b-41d4-a716-446655440000",
                    "source_url": "https://www.cninfo.com.cn/disclosure/600519_2023_annual.pdf",
                    "source_id": "announcement-12345",
                    "content_hash": "a1b2c3d4e5f6...",
                    "file_path": "/data/reports/600519/2023_annual.pdf",
                    "file_size": 2048000,
                }
            ]
        }
    }


class HealthStatus(BaseModel):
    """Health check response model.

    Attributes:
        status: Overall system status ("healthy" or "degraded").
        components: Status of individual components.
        checked_at: ISO 8601 timestamp of the health check.
    """

    status: str
    components: dict[str, str]
    checked_at: str

    model_config = {"frozen": True}


class WatchlistItemCreate(BaseModel):
    """Request model for adding a stock to the watchlist.

    Attributes:
        ticker: Stock ticker in format NNNNNN.{SH|SZ|HK}.
        name: Stock name or company name (max 100 characters).
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{4,6}\.(SH|SZ|HK)$",
        description="Stock ticker: 6 digits for SH/SZ, 4-5 digits for HK",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Stock name or company name",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "600519.SH",
                    "name": "Kweichow Moutai",
                }
            ]
        }
    }


class WatchlistItemResponse(BaseModel):
    """Response model for watchlist items.

    Attributes:
        ticker: Stock ticker.
        name: Stock name or company name.
        added_at: Timestamp when the stock was added to the watchlist.
        is_active: Whether the stock is actively being monitored.
    """

    ticker: str
    name: str
    added_at: datetime
    is_active: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "600519.SH",
                    "name": "Kweichow Moutai",
                    "added_at": "2026-05-01T00:00:00Z",
                    "is_active": True,
                }
            ]
        }
    }


class WatcherStateUpdate(BaseModel):
    """Model for updating watcher state after each poll cycle.

    Attributes:
        last_poll_time: Timestamp of the most recent poll.
        last_akshare_success: Whether the last AKShare poll succeeded.
        last_cninfo_fallback: Whether CNInfo fallback was used in the last poll.
        polls_count: Total number of poll cycles completed.
        errors_count: Total number of errors encountered.
    """

    last_poll_time: datetime | None = None
    last_akshare_success: bool = False
    last_cninfo_fallback: bool = False
    polls_count: int = Field(default=0, ge=0)
    errors_count: int = Field(default=0, ge=0)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "last_poll_time": "2026-05-01T01:00:00Z",
                    "last_akshare_success": True,
                    "last_cninfo_fallback": False,
                    "polls_count": 42,
                    "errors_count": 3,
                }
            ]
        }
    }


class PendingDisclosureCreate(BaseModel):
    """Request model for staging a disclosure in the pending_disclosures table.

    Attributes:
        ticker: Stock ticker in format NNNNNN.{SH|SZ|HK}.
        stock_name: Stock name (optional).
        report_type: Type of report. Must be one of annual, semi_annual, q1, q3.
        fiscal_year: Fiscal year of the report.
        disclosure_date: Actual disclosure date (if available).
        first_appointment: First appointment date from disclosure schedule.
        source: Data source, either 'akshare' or 'cninfo'.
        source_raw: Raw source data for debugging/audit.
    """

    ticker: str = Field(
        ...,
        pattern=r"^\d{4,6}\.(SH|SZ|HK)$",
        description="Stock ticker: 6 digits for SH/SZ, 4-5 digits for HK",
    )
    stock_name: str | None = Field(
        None,
        description="Stock name or company name",
    )
    report_type: Literal["annual", "semi_annual", "q1", "q3"] = Field(
        ...,
        description="Report type: annual, semi_annual, q1, or q3",
    )
    fiscal_year: int = Field(
        ...,
        ge=2000,
        le=2100,
        description="Fiscal year of the report",
    )
    disclosure_date: date | None = Field(
        None,
        description="Actual disclosure date (if disclosed)",
    )
    first_appointment: date | None = Field(
        None,
        description="First appointment date from disclosure schedule",
    )
    source: Literal["akshare", "cninfo"] = Field(
        ...,
        description="Data source for this disclosure",
    )
    source_raw: dict[str, Any] | None = Field(
        None,
        description="Raw source data for debugging/audit",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "600519.SH",
                    "stock_name": "Kweichow Moutai",
                    "report_type": "annual",
                    "fiscal_year": 2023,
                    "disclosure_date": "2024-04-30",
                    "first_appointment": "2024-03-15",
                    "source": "akshare",
                    "source_raw": {"raw_code": "600519"},
                }
            ]
        }
    }


__all__ = [
    "HealthStatus",
    "PendingDisclosureCreate",
    "PipelineDocumentCreate",
    "PipelineTaskCreate",
    "WatcherStateUpdate",
    "WatchlistItemCreate",
    "WatchlistItemResponse",
]
