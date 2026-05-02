"""Calculation sandbox for isolated subprocess execution.

Executes financial calculations (M-Score, DCF, yield gap) in an isolated
subprocess with configurable timeout and memory limits per D-06.

The sandbox is optional per D-07: when sandbox_enabled=False, calculations
run in-process as today by calling analyzers directly. When enabled,
CalculationSandboxService spawns a subprocess that sets resource limits
before executing the calculation.
"""

import json
import logging
import subprocess
import sys
from typing import Any

from stockvaluefinder.utils.errors import CalculationError

logger = logging.getLogger(__name__)

# Whitelist of allowed calculation types to prevent command injection (T-08-08)
ALLOWED_CALCULATIONS = frozenset({"m_score", "dcf_valuation", "yield_gap"})


class CalculationSandboxService:
    """Execute financial calculations in an isolated subprocess.

    Spawns a subprocess running sandbox_runner.py which sets resource
    limits (RLIMIT_CPU, RLIMIT_AS) before executing the calculation.
    Communication is JSON via stdin/stdout per SBOX-02.

    When sandbox_enabled=False (the default per D-07), calculations run
    in-process by calling the analyzer classes directly. This preserves
    the current pipeline behavior (SBOX-04).

    Attributes:
        _timeout: Maximum execution time in seconds.
        _max_memory_bytes: Maximum memory in bytes.
        _sandbox_enabled: If False, runs calculations in-process (SBOX-04).
    """

    def __init__(
        self,
        timeout: int = 30,
        max_memory_mb: int = 256,
        sandbox_enabled: bool = True,
    ) -> None:
        self._timeout = timeout
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._sandbox_enabled = sandbox_enabled

    def execute(self, calculation_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run calculation with optional subprocess isolation.

        Args:
            calculation_type: Must be in ALLOWED_CALCULATIONS whitelist.
            inputs: Calculation input parameters.

        Returns:
            Calculation result dict.

        Raises:
            ValueError: If calculation_type is not in whitelist.
            CalculationError: On timeout, memory breach, or execution failure.
        """
        if calculation_type not in ALLOWED_CALCULATIONS:
            raise ValueError(
                f"Invalid calculation type: {calculation_type}. "
                f"Allowed: {sorted(ALLOWED_CALCULATIONS)}"
            )

        if not self._sandbox_enabled:
            return self._execute_in_process(calculation_type, inputs)

        return self._execute_subprocess(calculation_type, inputs)

    def _execute_subprocess(
        self, calculation_type: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute calculation in subprocess with resource limits.

        Args:
            calculation_type: Type of calculation to run.
            inputs: Calculation input parameters.

        Returns:
            Calculation result dict from subprocess stdout.

        Raises:
            CalculationError: On timeout, non-zero exit, or invalid output.
        """
        request = json.dumps(
            {
                "type": calculation_type,
                "inputs": inputs,
                "timeout": self._timeout,
                "max_memory_bytes": self._max_memory_bytes,
            }
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "stockvaluefinder.services.sandbox_runner"],
                input=request,
                capture_output=True,
                text=True,
                timeout=self._timeout + 5,  # Extra buffer for startup
            )
        except subprocess.TimeoutExpired:
            raise CalculationError(
                f"Calculation timed out after {self._timeout}s",
                calculation=calculation_type,
            )

        if result.returncode != 0:
            raise CalculationError(
                f"Calculation failed (exit {result.returncode}): {result.stderr[:500]}",
                calculation=calculation_type,
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise CalculationError(
                f"Invalid JSON output: {e}",
                calculation=calculation_type,
            )

    def _execute_in_process(
        self, calculation_type: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute calculation in-process by calling analyzers directly.

        This is the fallback when sandbox is disabled (the default per D-07).
        Calls the same analyzer classes that _run_all_analyzers uses,
        preserving current in-process behavior (SBOX-04).

        Args:
            calculation_type: Type of calculation to run.
            inputs: Calculation input parameters.

        Returns:
            Calculation result dict with 'status' and 'data' keys.

        Raises:
            CalculationError: If the analyzer raises an exception.
        """
        logger.info(f"Running {calculation_type} in-process (sandbox disabled)")
        try:
            if calculation_type == "m_score":
                return self._run_m_score(inputs)

            elif calculation_type == "dcf_valuation":
                return self._run_dcf_valuation(inputs)

            elif calculation_type == "yield_gap":
                return self._run_yield_gap(inputs)

            else:
                raise CalculationError(
                    f"Unknown calculation type: {calculation_type}",
                    calculation=calculation_type,
                )
        except CalculationError:
            raise
        except Exception as e:
            raise CalculationError(
                f"In-process calculation failed: {e}",
                calculation=calculation_type,
            ) from e

    @staticmethod
    def _run_m_score(inputs: dict[str, Any]) -> dict[str, Any]:
        """Run M-Score calculation in-process via RiskAnalyzer."""
        from stockvaluefinder.services.risk_service import RiskAnalyzer

        analyzer = RiskAnalyzer()
        current_report = inputs.get("current_report", {})
        previous_report = inputs.get("previous_report")
        risk_result = analyzer.analyze(current_report, previous_report)
        return {
            "status": "ok",
            "data": {
                "m_score": risk_result.m_score,
                "risk_level": risk_result.risk_level.value,
            },
        }

    @staticmethod
    def _run_dcf_valuation(inputs: dict[str, Any]) -> dict[str, Any]:
        """Run DCF valuation calculation in-process via DCFValuationService."""
        from stockvaluefinder.services.valuation_service import DCFValuationService

        service = DCFValuationService()
        val_result = service.analyze(
            inputs.get("ticker", ""),
            inputs.get("current_price", 100),
            inputs.get("base_fcf", 0),
            inputs.get("shares_outstanding", 1_000_000),
            inputs.get("dcf_params", {}),
            inputs.get("valuation_id", ""),
        )
        return {
            "status": "ok",
            "data": {
                "intrinsic_value": str(val_result),
            },
        }

    @staticmethod
    def _run_yield_gap(inputs: dict[str, Any]) -> dict[str, Any]:
        """Run yield gap calculation in-process via YieldAnalyzer."""
        from stockvaluefinder.models.enums import Market
        from stockvaluefinder.services.yield_service import YieldAnalyzer

        yield_analyzer = YieldAnalyzer()
        market_raw = inputs.get("market")
        market = Market(market_raw) if isinstance(market_raw, str) else Market.A_SHARE
        yield_result = yield_analyzer.analyze(
            inputs.get("ticker", ""),
            inputs.get("cost_basis", 0),
            inputs.get("current_price", 0),
            inputs.get("gross_dividend_yield", 0),
            inputs.get("risk_free_bond", 0),
            inputs.get("risk_free_deposit", 0),
            market,
            inputs.get("analysis_id", ""),
        )
        return {
            "status": "ok",
            "data": {
                "yield_gap": str(yield_result),
            },
        }
