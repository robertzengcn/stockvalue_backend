"""Integration tests for sandbox routing in _run_all_analyzers.

Tests cover:
- sandbox_enabled=True routes through CalculationSandboxService.execute()
- sandbox_enabled=False uses existing asyncio.to_thread calls
- Sandbox routing uses config.sandbox_timeout for subprocess timeout
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from stockvaluefinder.models.enums import (
    RiskLevel,
    ValuationLevel,
    YieldRecommendation,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_mock_risk_score():
    """Create a mock RiskScore result."""
    mock_score = MagicMock()
    mock_score.score_id = uuid4()
    mock_score.risk_level = RiskLevel.LOW
    mock_score.m_score = -2.5
    mock_score.f_score = 7
    mock_score.red_flags = []
    return mock_score


def _make_mock_valuation_result():
    """Create a mock ValuationResult."""
    mock_result = MagicMock()
    mock_result.valuation_id = uuid4()
    mock_result.intrinsic_value = Decimal("150.00")
    mock_result.wacc = 0.09
    mock_result.margin_of_safety = 0.5
    mock_result.valuation_level = ValuationLevel.UNDERVALUED
    return mock_result


def _make_mock_yield_gap():
    """Create a mock YieldGap result."""
    mock_gap = MagicMock()
    mock_gap.analysis_id = uuid4()
    mock_gap.yield_gap = 0.025
    mock_gap.recommendation = YieldRecommendation.ATTRACTIVE
    return mock_gap


def _make_current_report():
    """Create a current report dict for testing."""
    return {
        "revenue": "1000000000",
        "net_income": "200000000",
        "operating_cash_flow": "250000000",
        "total_assets": "5000000000",
        "current_price": "100",
        "gross_dividend_yield": 0.03,
        "risk_free_bond_rate": 0.03,
        "risk_free_deposit_rate": 0.025,
    }


# ---------------------------------------------------------------------------
# Test 1: sandbox_enabled=True routes through CalculationSandboxService
# ---------------------------------------------------------------------------


class TestSandboxEnabledRouting:
    """Tests for sandbox_enabled=True routing in _run_all_analyzers."""

    @pytest.mark.asyncio
    async def test_sandbox_enabled_routes_through_sandbox_service(self) -> None:
        """When sandbox_enabled=True, all 3 analyzers route through CalculationSandboxService."""
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.worker import _run_all_analyzers

        current_report = _make_current_report()

        # Mock the sandbox service to return success dicts
        sandbox_results = [
            {"status": "ok", "data": {"m_score": -2.5, "risk_level": "low"}},
            {"status": "ok", "data": {"intrinsic_value": "150.00"}},
            {"status": "ok", "data": {"yield_gap": "0.025"}},
        ]

        with (
            patch(
                "stockvaluefinder.pipeline.worker.config",
                PipelineConfig(sandbox_enabled=True, sandbox_timeout=30),
            ),
            patch(
                "stockvaluefinder.pipeline.worker.CalculationSandboxService"
            ) as mock_sandbox_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.execute = MagicMock(side_effect=sandbox_results)
            mock_sandbox_cls.return_value = mock_instance

            # Patch asyncio.to_thread to just call the function directly
            with patch(
                "stockvaluefinder.pipeline.worker.asyncio.to_thread",
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs),
            ):
                summary = await _run_all_analyzers(
                    current_report, None, "600519.SH", 2023
                )

        # CalculationSandboxService.execute should be called 3 times
        assert mock_instance.execute.call_count == 3

        # Verify the calculation types
        call_types = [call[0][0] for call in mock_instance.execute.call_args_list]
        assert "m_score" in call_types
        assert "dcf_valuation" in call_types
        assert "yield_gap" in call_types

        # All 3 should be successful
        for name in ["risk", "valuation", "yield"]:
            assert summary[name]["status"] == "success"


# ---------------------------------------------------------------------------
# Test 2: sandbox_enabled=False uses direct analyzers
# ---------------------------------------------------------------------------


class TestSandboxDisabledRouting:
    """Tests for sandbox_enabled=False (default) routing in _run_all_analyzers."""

    @pytest.mark.asyncio
    async def test_sandbox_disabled_uses_direct_analyzers(self) -> None:
        """When sandbox_enabled=False, analyzers called directly, not via sandbox."""
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.worker import _run_all_analyzers

        current_report = _make_current_report()

        mock_risk = MagicMock()
        mock_risk.analyze = MagicMock(return_value=_make_mock_risk_score())

        mock_valuation = MagicMock()
        mock_valuation.analyze = MagicMock(return_value=_make_mock_valuation_result())

        mock_yield = MagicMock()
        mock_yield.analyze = MagicMock(return_value=_make_mock_yield_gap())

        with (
            patch(
                "stockvaluefinder.pipeline.worker.config",
                PipelineConfig(sandbox_enabled=False),
            ),
            patch(
                "stockvaluefinder.pipeline.worker.RiskAnalyzer",
                return_value=mock_risk,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.DCFValuationService",
                return_value=mock_valuation,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.YieldAnalyzer",
                return_value=mock_yield,
            ),
            patch(
                "stockvaluefinder.pipeline.worker.CalculationSandboxService"
            ) as mock_sandbox_cls,
            patch(
                "stockvaluefinder.pipeline.worker.asyncio.to_thread",
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs),
            ),
        ):
            summary = await _run_all_analyzers(current_report, None, "600519.SH", 2023)

        # Direct analyzers should be called
        mock_risk.analyze.assert_called_once()
        mock_valuation.analyze.assert_called_once()
        mock_yield.analyze.assert_called_once()

        # CalculationSandboxService should NOT be instantiated
        mock_sandbox_cls.assert_not_called()

        # All 3 should be successful
        for name in ["risk", "valuation", "yield"]:
            assert summary[name]["status"] == "success"


# ---------------------------------------------------------------------------
# Test 3: sandbox uses config.sandbox_timeout
# ---------------------------------------------------------------------------


class TestSandboxTimeoutConfig:
    """Tests for sandbox timeout configuration."""

    @pytest.mark.asyncio
    async def test_sandbox_uses_config_timeout(self) -> None:
        """CalculationSandboxService instantiated with config.sandbox_timeout."""
        from stockvaluefinder.pipeline.config import PipelineConfig
        from stockvaluefinder.pipeline.worker import _run_all_analyzers

        current_report = _make_current_report()

        with (
            patch(
                "stockvaluefinder.pipeline.worker.config",
                PipelineConfig(sandbox_enabled=True, sandbox_timeout=60),
            ),
            patch(
                "stockvaluefinder.pipeline.worker.CalculationSandboxService"
            ) as mock_sandbox_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.execute = MagicMock(
                side_effect=[
                    {"status": "ok", "data": {}},
                    {"status": "ok", "data": {}},
                    {"status": "ok", "data": {}},
                ]
            )
            mock_sandbox_cls.return_value = mock_instance

            with patch(
                "stockvaluefinder.pipeline.worker.asyncio.to_thread",
                side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs),
            ):
                await _run_all_analyzers(current_report, None, "600519.SH", 2023)

        # Verify CalculationSandboxService was instantiated with timeout=60
        mock_sandbox_cls.assert_called_once_with(timeout=60, sandbox_enabled=True)
