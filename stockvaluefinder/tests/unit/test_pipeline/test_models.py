"""Tests for pipeline Pydantic domain models."""

import pytest
from pydantic import ValidationError

from stockvaluefinder.pipeline.models import (
    HealthStatus,
    PipelineDocumentCreate,
    PipelineTaskCreate,
)


class TestPipelineTaskCreate:
    """Test PipelineTaskCreate Pydantic model."""

    def test_valid_creation(self) -> None:
        task = PipelineTaskCreate(
            ticker="600519.SH",
            business_key="600519.SH:2023:annual",
            fiscal_year=2023,
            report_type="annual",
        )
        assert task.ticker == "600519.SH"
        assert task.business_key == "600519.SH:2023:annual"
        assert task.fiscal_year == 2023
        assert task.report_type == "annual"

    def test_valid_sz_ticker(self) -> None:
        task = PipelineTaskCreate(
            ticker="000001.SZ",
            business_key="000001.SZ:2023:annual",
            fiscal_year=2023,
            report_type="annual",
        )
        assert task.ticker == "000001.SZ"

    def test_valid_hk_ticker(self) -> None:
        task = PipelineTaskCreate(
            ticker="0700.HK",
            business_key="0700.HK:2023:annual",
            fiscal_year=2023,
            report_type="annual",
        )
        assert task.ticker == "0700.HK"

    def test_invalid_ticker_format(self) -> None:
        with pytest.raises(ValidationError):
            PipelineTaskCreate(
                ticker="INVALID",
                business_key="INVALID:2023:annual",
                fiscal_year=2023,
                report_type="annual",
            )

    def test_missing_ticker(self) -> None:
        with pytest.raises(ValidationError):
            PipelineTaskCreate(  # type: ignore[call-arg]
                business_key="600519.SH:2023:annual",
                fiscal_year=2023,
                report_type="annual",
            )

    def test_missing_business_key(self) -> None:
        with pytest.raises(ValidationError):
            PipelineTaskCreate(  # type: ignore[call-arg]
                ticker="600519.SH",
                fiscal_year=2023,
                report_type="annual",
            )

    def test_empty_business_key(self) -> None:
        with pytest.raises(ValidationError):
            PipelineTaskCreate(
                ticker="600519.SH",
                business_key="",
                fiscal_year=2023,
                report_type="annual",
            )

    def test_fiscal_year_too_low(self) -> None:
        with pytest.raises(ValidationError):
            PipelineTaskCreate(
                ticker="600519.SH",
                business_key="600519.SH:1999:annual",
                fiscal_year=1999,
                report_type="annual",
            )

    def test_fiscal_year_too_high(self) -> None:
        with pytest.raises(ValidationError):
            PipelineTaskCreate(
                ticker="600519.SH",
                business_key="600519.SH:2101:annual",
                fiscal_year=2101,
                report_type="annual",
            )

    def test_missing_report_type(self) -> None:
        with pytest.raises(ValidationError):
            PipelineTaskCreate(  # type: ignore[call-arg]
                ticker="600519.SH",
                business_key="600519.SH:2023:annual",
                fiscal_year=2023,
            )


class TestPipelineDocumentCreate:
    """Test PipelineDocumentCreate Pydantic model."""

    def test_valid_creation_with_all_fields(self) -> None:
        doc = PipelineDocumentCreate(
            task_id="550e8400-e29b-41d4-a716-446655440000",
            source_url="https://example.com/report.pdf",
            source_id="announcement-123",
            content_hash="abc123",
            file_path="/data/reports/report.pdf",
            file_size=1024000,
        )
        assert doc.task_id == "550e8400-e29b-41d4-a716-446655440000"
        assert doc.file_size == 1024000

    def test_valid_creation_minimal(self) -> None:
        doc = PipelineDocumentCreate(
            task_id="550e8400-e29b-41d4-a716-446655440000",
        )
        assert doc.source_url is None
        assert doc.source_id is None
        assert doc.content_hash is None
        assert doc.file_path is None
        assert doc.file_size is None

    def test_missing_task_id(self) -> None:
        with pytest.raises(ValidationError):
            PipelineDocumentCreate(  # type: ignore[call-arg]
                source_url="https://example.com/report.pdf",
            )

    def test_negative_file_size(self) -> None:
        with pytest.raises(ValidationError):
            PipelineDocumentCreate(
                task_id="550e8400-e29b-41d4-a716-446655440000",
                file_size=-1,
            )

    def test_zero_file_size_is_valid(self) -> None:
        doc = PipelineDocumentCreate(
            task_id="550e8400-e29b-41d4-a716-446655440000",
            file_size=0,
        )
        assert doc.file_size == 0


class TestHealthStatus:
    """Test HealthStatus Pydantic model."""

    def test_valid_creation(self) -> None:
        status = HealthStatus(
            status="healthy",
            components={"redis": "up", "postgresql": "up", "worker": "connected"},
            checked_at="2026-05-01T00:00:00Z",
        )
        assert status.status == "healthy"

    def test_frozen(self) -> None:
        status = HealthStatus(
            status="healthy",
            components={"redis": "up"},
            checked_at="2026-05-01T00:00:00Z",
        )
        with pytest.raises(ValidationError):
            status.status = "degraded"  # type: ignore[misc]

    def test_degraded_status(self) -> None:
        status = HealthStatus(
            status="degraded",
            components={"redis": "down", "postgresql": "up", "worker": "disconnected"},
            checked_at="2026-05-01T00:00:00Z",
        )
        assert status.status == "degraded"
