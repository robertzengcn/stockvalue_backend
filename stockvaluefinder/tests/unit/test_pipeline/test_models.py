"""Tests for pipeline Pydantic domain models."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from stockvaluefinder.pipeline.models import (
    HealthStatus,
    PendingDisclosureCreate,
    PipelineDocumentCreate,
    PipelineTaskCreate,
    WatcherStateUpdate,
    WatchlistItemCreate,
    WatchlistItemResponse,
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


class TestWatchlistItemCreate:
    """Test WatchlistItemCreate Pydantic model (D-13, D-15)."""

    def test_valid_creation(self) -> None:
        item = WatchlistItemCreate(ticker="600519.SH", name="Kweichow Moutai")
        assert item.ticker == "600519.SH"
        assert item.name == "Kweichow Moutai"

    def test_valid_sz_ticker(self) -> None:
        item = WatchlistItemCreate(ticker="000001.SZ", name="Ping An Bank")
        assert item.ticker == "000001.SZ"

    def test_valid_hk_ticker(self) -> None:
        item = WatchlistItemCreate(ticker="0700.HK", name="Tencent")
        assert item.ticker == "0700.HK"

    def test_invalid_ticker_format(self) -> None:
        with pytest.raises(ValidationError):
            WatchlistItemCreate(ticker="INVALID", name="Test")

    def test_invalid_ticker_no_exchange(self) -> None:
        with pytest.raises(ValidationError):
            WatchlistItemCreate(ticker="600519", name="Test")

    def test_missing_ticker(self) -> None:
        with pytest.raises(ValidationError):
            WatchlistItemCreate(name="Test")  # type: ignore[call-arg]

    def test_missing_name(self) -> None:
        with pytest.raises(ValidationError):
            WatchlistItemCreate(ticker="600519.SH")  # type: ignore[call-arg]

    def test_name_max_100_chars(self) -> None:
        long_name = "A" * 100
        item = WatchlistItemCreate(ticker="600519.SH", name=long_name)
        assert len(item.name) == 100

    def test_name_exceeds_100_chars(self) -> None:
        with pytest.raises(ValidationError):
            WatchlistItemCreate(ticker="600519.SH", name="A" * 101)


class TestWatchlistItemResponse:
    """Test WatchlistItemResponse Pydantic model (D-13)."""

    def test_valid_creation(self) -> None:
        now = datetime.now(timezone.utc)
        response = WatchlistItemResponse(
            ticker="600519.SH",
            name="Kweichow Moutai",
            added_at=now,
            is_active=True,
        )
        assert response.ticker == "600519.SH"
        assert response.name == "Kweichow Moutai"
        assert response.added_at == now
        assert response.is_active is True

    def test_inactive_item(self) -> None:
        response = WatchlistItemResponse(
            ticker="600519.SH",
            name="Kweichow Moutai",
            added_at=datetime.now(timezone.utc),
            is_active=False,
        )
        assert response.is_active is False


class TestWatcherStateUpdate:
    """Test WatcherStateUpdate Pydantic model (D-16)."""

    def test_valid_creation_all_fields(self) -> None:
        now = datetime.now(timezone.utc)
        state = WatcherStateUpdate(
            last_poll_time=now,
            last_akshare_success=True,
            last_cninfo_fallback=False,
            polls_count=42,
            errors_count=3,
        )
        assert state.last_poll_time == now
        assert state.last_akshare_success is True
        assert state.last_cninfo_fallback is False
        assert state.polls_count == 42
        assert state.errors_count == 3

    def test_valid_defaults(self) -> None:
        state = WatcherStateUpdate()
        assert state.last_poll_time is None
        assert state.last_akshare_success is False
        assert state.last_cninfo_fallback is False
        assert state.polls_count == 0
        assert state.errors_count == 0

    def test_negative_polls_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WatcherStateUpdate(polls_count=-1)

    def test_negative_errors_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WatcherStateUpdate(errors_count=-1)


class TestPendingDisclosureCreate:
    """Test PendingDisclosureCreate Pydantic model (D-11)."""

    def test_valid_creation_all_fields(self) -> None:
        disclosure = PendingDisclosureCreate(
            ticker="600519.SH",
            stock_name="Kweichow Moutai",
            report_type="annual",
            fiscal_year=2023,
            disclosure_date=date(2024, 4, 30),
            first_appointment=date(2024, 3, 15),
            source="akshare",
            source_raw={"raw": "data"},
        )
        assert disclosure.ticker == "600519.SH"
        assert disclosure.stock_name == "Kweichow Moutai"
        assert disclosure.report_type == "annual"
        assert disclosure.fiscal_year == 2023
        assert disclosure.disclosure_date == date(2024, 4, 30)
        assert disclosure.source == "akshare"
        assert disclosure.source_raw == {"raw": "data"}

    def test_valid_creation_minimal(self) -> None:
        disclosure = PendingDisclosureCreate(
            ticker="600519.SH",
            report_type="semi_annual",
            fiscal_year=2023,
            source="cninfo",
        )
        assert disclosure.stock_name is None
        assert disclosure.disclosure_date is None
        assert disclosure.first_appointment is None
        assert disclosure.source_raw is None

    def test_valid_report_types(self) -> None:
        """All four report types are valid (D-03)."""
        for report_type in ("annual", "semi_annual", "q1", "q3"):
            d = PendingDisclosureCreate(
                ticker="600519.SH",
                report_type=report_type,
                fiscal_year=2023,
                source="akshare",
            )
            assert d.report_type == report_type

    def test_invalid_report_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PendingDisclosureCreate(
                ticker="600519.SH",
                report_type="monthly",
                fiscal_year=2023,
                source="akshare",
            )

    def test_invalid_source_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PendingDisclosureCreate(
                ticker="600519.SH",
                report_type="annual",
                fiscal_year=2023,
                source="yahoo",
            )

    def test_invalid_ticker_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PendingDisclosureCreate(
                ticker="INVALID",
                report_type="annual",
                fiscal_year=2023,
                source="akshare",
            )

    def test_fiscal_year_too_low(self) -> None:
        with pytest.raises(ValidationError):
            PendingDisclosureCreate(
                ticker="600519.SH",
                report_type="annual",
                fiscal_year=1999,
                source="akshare",
            )

    def test_fiscal_year_too_high(self) -> None:
        with pytest.raises(ValidationError):
            PendingDisclosureCreate(
                ticker="600519.SH",
                report_type="annual",
                fiscal_year=2101,
                source="akshare",
            )

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            PendingDisclosureCreate()  # type: ignore[call-arg]
