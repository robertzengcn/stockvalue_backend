"""Unit tests for market scanner worker cron jobs and run_market_scan function.

Tests the arq worker job functions with mocked dependencies:
    - daily_light_scan delegates to run_market_scan with DAILY type
    - weekly_deep_scan delegates to run_market_scan with WEEKLY type
    - run_market_scan handles index codes, top_n overrides, error handling
    - ScannerWorkerSettings configuration validates correctly
    - Concurrent scan prevention via get_latest_run() status check
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.worker import (
    ScannerWorkerSettings,
    daily_light_scan,
    run_market_scan,
    weekly_deep_scan,
)
from stockvaluefinder.models.enums import ScanType


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_mock_latest_run(status: str) -> MagicMock:
    """Create a mock latest run object with the given status.

    Args:
        status: Lifecycle status string (pending, running, completed, partial_failed).

    Returns:
        MagicMock with .status and .run_id attributes.
    """
    mock_run = MagicMock()
    mock_run.status = status
    mock_run.run_id = uuid4()
    return mock_run


def _patch_session_and_deps(
    latest_runs: dict[str, Any] | None = None,
) -> dict[str, AsyncMock]:
    """Create mock context for worker tests with patched session and deps.

    Args:
        latest_runs: Dict mapping index_code -> mock run object or None.
            Used to configure get_latest_run return values per index_code.

    Returns:
        Dict of mock objects for customizing test behavior.
    """
    if latest_runs is None:
        latest_runs = {}

    mocks: dict[str, AsyncMock] = {}

    # Mock session context manager
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mocks["session"] = mock_session

    # Mock MarketScanRunRepository
    mock_run_repo = AsyncMock()

    def _get_latest_run_side_effect(index_code: str) -> Any:
        return latest_runs.get(index_code, None)

    mock_run_repo.get_latest_run.side_effect = _get_latest_run_side_effect
    mocks["run_repo"] = mock_run_repo

    return mocks


# ---------------------------------------------------------------------------
# Tests: Daily light scan
# ---------------------------------------------------------------------------


class TestDailyLightScan:
    """Tests for daily_light_scan cron job function."""

    @pytest.mark.asyncio
    async def test_calls_run_scan_for_each_index(self) -> None:
        """Daily scan calls orchestrator.run_scan with ScanType.DAILY for each index."""
        config = MarketScannerConfig()
        mocks = _patch_session_and_deps()

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run_scan.return_value = uuid4()

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await daily_light_scan({})

        assert result["status"] == "completed"

        # Should have called run_scan once per config index code
        assert mock_orchestrator.run_scan.call_count == len(config.index_codes)

        # Verify each call uses DAILY scan type
        for call in mock_orchestrator.run_scan.call_args_list:
            assert call.args[1] == ScanType.DAILY

    @pytest.mark.asyncio
    async def test_skips_when_run_already_running(self) -> None:
        """Daily scan skips index when latest run has status='running'."""
        config = MarketScannerConfig()
        running_runs = {
            code: _make_mock_latest_run("running") for code in config.index_codes
        }
        mocks = _patch_session_and_deps(latest_runs=running_runs)

        mock_orchestrator = AsyncMock()

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await daily_light_scan({})

        assert result["status"] == "completed"
        # Orchestrator should NOT be called since all indexes have running scans
        mock_orchestrator.run_scan.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_run_pending(self) -> None:
        """Daily scan skips index when latest run has status='pending'."""
        config = MarketScannerConfig()
        pending_runs = {
            code: _make_mock_latest_run("pending") for code in config.index_codes
        }
        mocks = _patch_session_and_deps(latest_runs=pending_runs)

        mock_orchestrator = AsyncMock()

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await daily_light_scan({})

        assert result["status"] == "completed"
        mock_orchestrator.run_scan.assert_not_called()

    @pytest.mark.asyncio
    async def test_proceeds_when_latest_completed(self) -> None:
        """Daily scan proceeds when latest run has status='completed'."""
        config = MarketScannerConfig()
        completed_runs = {
            code: _make_mock_latest_run("completed") for code in config.index_codes
        }
        mocks = _patch_session_and_deps(latest_runs=completed_runs)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run_scan.return_value = uuid4()

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await daily_light_scan({})

        assert result["status"] == "completed"
        # Should have proceeded with scan for each index
        assert mock_orchestrator.run_scan.call_count == len(config.index_codes)


# ---------------------------------------------------------------------------
# Tests: Weekly deep scan
# ---------------------------------------------------------------------------


class TestWeeklyDeepScan:
    """Tests for weekly_deep_scan cron job function."""

    @pytest.mark.asyncio
    async def test_calls_run_scan_weekly_type(self) -> None:
        """Weekly scan calls orchestrator.run_scan with ScanType.WEEKLY."""
        config = MarketScannerConfig()
        mocks = _patch_session_and_deps()

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run_scan.return_value = uuid4()

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await weekly_deep_scan({})

        assert result["status"] == "completed"
        assert mock_orchestrator.run_scan.call_count == len(config.index_codes)

        # Verify each call uses WEEKLY scan type
        for call in mock_orchestrator.run_scan.call_args_list:
            assert call.args[1] == ScanType.WEEKLY


# ---------------------------------------------------------------------------
# Tests: run_market_scan job function
# ---------------------------------------------------------------------------


class TestRunMarketScan:
    """Tests for run_market_scan job function."""

    @pytest.mark.asyncio
    async def test_accepts_custom_index_codes(self) -> None:
        """Passing index_codes=["CSI300"] scans only CSI300."""
        mocks = _patch_session_and_deps()

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run_scan.return_value = uuid4()

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                return_value=mock_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await run_market_scan(
                {}, index_codes=["CSI300"], scan_type="daily"
            )

        assert result["status"] == "completed"
        # Only one index code specified, so only one call
        mock_orchestrator.run_scan.assert_called_once()
        assert mock_orchestrator.run_scan.call_args.args[0] == "CSI300"

    @pytest.mark.asyncio
    async def test_accepts_top_n_override(self) -> None:
        """Passing top_n=20 applies the override to config."""
        mocks = _patch_session_and_deps()

        captured_configs: list[MarketScannerConfig] = []

        async def _capture_orchestrator(
            config: MarketScannerConfig,
            session: Any,
        ) -> AsyncMock:
            captured_configs.append(config)
            mock_orch = AsyncMock()
            mock_orch.run_scan.return_value = uuid4()
            return mock_orch

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                side_effect=_capture_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await run_market_scan(
                {}, index_codes=["CSI300"], scan_type="daily", top_n=20
            )

        assert result["status"] == "completed"
        # The config passed to _build_orchestrator should have daily_top_n=20
        assert len(captured_configs) == 1
        assert captured_configs[0].daily_top_n == 20

    @pytest.mark.asyncio
    async def test_returns_failed_on_exception(self) -> None:
        """When orchestrator.run_scan raises, returns status='failed'."""
        mocks = _patch_session_and_deps()

        async def _failing_orchestrator(
            config: MarketScannerConfig,
            session: Any,
        ) -> AsyncMock:
            mock_orch = AsyncMock()
            mock_orch.run_scan.side_effect = Exception("test error")
            return mock_orch

        with (
            patch(
                "stockvaluefinder.market_scanner.worker.async_session_maker"
            ) as mock_session_maker,
            patch(
                "stockvaluefinder.market_scanner.worker.MarketScanRunRepository",
                return_value=mocks["run_repo"],
            ),
            patch(
                "stockvaluefinder.market_scanner.worker._build_orchestrator",
                side_effect=_failing_orchestrator,
            ),
        ):
            mock_session_maker.return_value = mocks["session"]

            result = await run_market_scan(
                {}, index_codes=["CSI300"], scan_type="daily"
            )

        assert result["status"] == "failed"
        assert "test error" in result["error"]


# ---------------------------------------------------------------------------
# Tests: ScannerWorkerSettings
# ---------------------------------------------------------------------------


class TestScannerWorkerSettings:
    """Tests for ScannerWorkerSettings configuration class."""

    def test_cron_jobs_count(self) -> None:
        """ScannerWorkerSettings.cron_jobs contains exactly 2 entries."""
        assert len(ScannerWorkerSettings.cron_jobs) == 2

    def test_functions_includes_run_market_scan(self) -> None:
        """ScannerWorkerSettings.functions contains run_market_scan."""
        assert run_market_scan in ScannerWorkerSettings.functions

    def test_has_redis_settings(self) -> None:
        """ScannerWorkerSettings.redis_settings is not None."""
        assert ScannerWorkerSettings.redis_settings is not None
