"""Unit tests for CalculationSandboxService.

Tests cover:
- Subprocess execution with JSON stdin/stdout protocol
- Timeout handling raises CalculationError
- Non-zero exit code raises CalculationError
- Invalid JSON stdout raises CalculationError
- Invalid calculation_type rejected via whitelist
- sandbox_runner.py sets resource limits (RLIMIT_CPU, RLIMIT_AS)
- In-process fallback for m_score calls RiskAnalyzer.analyze() directly
- In-process fallback for dcf_valuation calls DCFValuationService.analyze() directly
- In-process fallback for yield_gap calls YieldAnalyzer.analyze() directly
- JSON input passed via subprocess stdin
"""

import json
import subprocess
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from stockvaluefinder.models.enums import (
    RiskLevel,
    ValuationLevel,
    YieldRecommendation,
)
from stockvaluefinder.utils.errors import CalculationError


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


# ---------------------------------------------------------------------------
# Test 1: execute returns JSON result from subprocess
# ---------------------------------------------------------------------------


class TestSubprocessExecution:
    """Tests for subprocess execution path (sandbox_enabled=True)."""

    def test_execute_returns_json_result(self) -> None:
        """Subprocess returns valid JSON result dict."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        expected = {"status": "ok", "data": {"m_score": -2.5}}
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(expected), stderr=""
        )

        with patch(
            "stockvaluefinder.services.calculation_sandbox.subprocess.run",
            return_value=mock_result,
        ):
            service = CalculationSandboxService(
                timeout=30, max_memory_mb=256, sandbox_enabled=True
            )
            result = service.execute("m_score", {"revenue": "100"})

        assert result == expected

    def test_execute_timeout_raises_calculation_error(self) -> None:
        """TimeoutExpired raises CalculationError with 'timed out' in message."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        with patch(
            "stockvaluefinder.services.calculation_sandbox.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=[], timeout=30),
        ):
            service = CalculationSandboxService(timeout=30, sandbox_enabled=True)
            with pytest.raises(CalculationError, match="timed out"):
                service.execute("m_score", {})

    def test_execute_nonzero_exit_raises_calculation_error(self) -> None:
        """Non-zero exit code raises CalculationError with 'failed' in message."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="MemoryError: limit exceeded"
        )

        with patch(
            "stockvaluefinder.services.calculation_sandbox.subprocess.run",
            return_value=mock_result,
        ):
            service = CalculationSandboxService(timeout=30, sandbox_enabled=True)
            with pytest.raises(CalculationError, match="failed"):
                service.execute("m_score", {})

    def test_execute_invalid_json_stdout_raises_calculation_error(self) -> None:
        """Invalid JSON in subprocess stdout raises CalculationError."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not json", stderr=""
        )

        with patch(
            "stockvaluefinder.services.calculation_sandbox.subprocess.run",
            return_value=mock_result,
        ):
            service = CalculationSandboxService(timeout=30, sandbox_enabled=True)
            with pytest.raises(CalculationError, match="Invalid JSON"):
                service.execute("m_score", {})

    def test_execute_invalid_calculation_type_raises_error(self) -> None:
        """Invalid calculation_type raises ValueError."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        service = CalculationSandboxService(sandbox_enabled=True)
        with pytest.raises(ValueError, match="invalid|whitelist|Allowed"):
            service.execute("rm_rf", {})

    def test_execute_passes_json_via_stdin(self) -> None:
        """Execute passes JSON via stdin argument to subprocess.run."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        expected_response = {"status": "ok", "data": {}}
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(expected_response), stderr=""
        )

        with patch(
            "stockvaluefinder.services.calculation_sandbox.subprocess.run",
            return_value=mock_result,
        ) as mock_run:
            service = CalculationSandboxService(
                timeout=30, max_memory_mb=256, sandbox_enabled=True
            )
            service.execute("m_score", {"revenue": "100"})

        # Verify the input argument is JSON containing type and inputs
        call_kwargs = mock_run.call_args
        stdin_input = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")
        parsed = json.loads(stdin_input)
        assert parsed["type"] == "m_score"
        assert parsed["inputs"] == {"revenue": "100"}


# ---------------------------------------------------------------------------
# Test 6: sandbox_runner sets resource limits
# ---------------------------------------------------------------------------


class TestSandboxRunner:
    """Tests for sandbox_runner.py resource limit setting."""

    def test_sandbox_runner_sets_resource_limits(self) -> None:
        """sandbox_runner.set_resource_limits calls setrlimit with RLIMIT_CPU and RLIMIT_AS."""
        from stockvaluefinder.services.sandbox_runner import set_resource_limits

        with patch(
            "stockvaluefinder.services.sandbox_runner.resource.setrlimit"
        ) as mock_setrlimit:
            set_resource_limits(timeout=30, max_memory_bytes=256 * 1024 * 1024)

        assert mock_setrlimit.call_count == 2
        # First call: RLIMIT_CPU
        import resource

        assert mock_setrlimit.call_args_list[0][0][0] == resource.RLIMIT_CPU
        assert mock_setrlimit.call_args_list[0][0][1] == (30, 30)
        # Second call: RLIMIT_AS
        assert mock_setrlimit.call_args_list[1][0][0] == resource.RLIMIT_AS
        assert mock_setrlimit.call_args_list[1][0][1] == (
            256 * 1024 * 1024,
            256 * 1024 * 1024,
        )


# ---------------------------------------------------------------------------
# Test 7-9: In-process fallback when sandbox_enabled=False
# ---------------------------------------------------------------------------


class TestInProcessFallback:
    """Tests for in-process execution when sandbox_enabled=False."""

    def test_sandbox_disabled_m_score_in_process(self) -> None:
        """sandbox_enabled=False calls RiskAnalyzer.analyze() directly."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        mock_score = _make_mock_risk_score()

        with patch(
            "stockvaluefinder.services.risk_service.RiskAnalyzer"
        ) as mock_analyzer_cls:
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = mock_score
            mock_analyzer_cls.return_value = mock_instance

            service = CalculationSandboxService(sandbox_enabled=False)
            result = service.execute(
                "m_score",
                {
                    "current_report": {"revenue": 100},
                    "previous_report": None,
                },
            )

        # Verify RiskAnalyzer.analyze was called with the report dicts
        mock_instance.analyze.assert_called_once_with({"revenue": 100}, None)
        assert result["status"] == "ok"
        assert "data" in result
        assert result["data"]["m_score"] == -2.5

    def test_sandbox_disabled_dcf_valuation_in_process(self) -> None:
        """sandbox_enabled=False calls DCFValuationService.analyze() directly."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        mock_val = _make_mock_valuation_result()

        with patch(
            "stockvaluefinder.services.valuation_service.DCFValuationService"
        ) as mock_service_cls:
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = mock_val
            mock_service_cls.return_value = mock_instance

            service = CalculationSandboxService(sandbox_enabled=False)
            result = service.execute(
                "dcf_valuation",
                {
                    "ticker": "600519.SH",
                    "current_price": 100,
                    "base_fcf": 50,
                    "shares_outstanding": 1000000,
                    "dcf_params": {},
                    "valuation_id": "test-id",
                },
            )

        mock_instance.analyze.assert_called_once()
        assert result["status"] == "ok"

    def test_sandbox_disabled_yield_gap_in_process(self) -> None:
        """sandbox_enabled=False calls YieldAnalyzer.analyze() directly."""
        from stockvaluefinder.services.calculation_sandbox import (
            CalculationSandboxService,
        )

        mock_yield = _make_mock_yield_gap()

        with patch(
            "stockvaluefinder.services.yield_service.YieldAnalyzer"
        ) as mock_analyzer_cls:
            mock_instance = MagicMock()
            mock_instance.analyze.return_value = mock_yield
            mock_analyzer_cls.return_value = mock_instance

            service = CalculationSandboxService(sandbox_enabled=False)
            result = service.execute(
                "yield_gap",
                {
                    "ticker": "600519.SH",
                    "cost_basis": 100,
                    "current_price": 100,
                    "gross_dividend_yield": 0.03,
                    "risk_free_bond": 0.03,
                    "risk_free_deposit": 0.025,
                    "market": "A_SHARE",
                    "analysis_id": "test-id",
                },
            )

        mock_instance.analyze.assert_called_once()
        assert result["status"] == "ok"
