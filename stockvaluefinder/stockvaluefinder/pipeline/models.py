"""Pydantic domain models for the pipeline module.

Defines request/response models for pipeline task creation,
document creation, and health status reporting.
"""

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


__all__ = [
    "HealthStatus",
    "PipelineDocumentCreate",
    "PipelineTaskCreate",
]
