"""Subprocess entry point for isolated calculation execution.

This module is run as ``python -m stockvaluefinder.services.sandbox_runner``.
It reads JSON from stdin, sets resource limits (RLIMIT_CPU, RLIMIT_AS),
executes the requested calculation, and writes JSON result to stdout.

Resource limits are set BEFORE importing calculation modules to ensure
limits apply to all allocations (Pitfall 3 from RESEARCH.md).
"""

import json
import resource
import sys
import traceback
from typing import Any


def set_resource_limits(timeout: int, max_memory_bytes: int) -> None:
    """Set process resource limits before calculation.

    Args:
        timeout: CPU time limit in seconds (RLIMIT_CPU).
        max_memory_bytes: Virtual memory limit in bytes (RLIMIT_AS).
    """
    # RLIMIT_CPU: SIGXCPU when exceeded, then SIGKILL
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
    # RLIMIT_AS: MemoryError on allocation exceeding limit
    resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))


def run_calculation(calc_type: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Execute the requested calculation type.

    Args:
        calc_type: One of m_score, dcf_valuation, yield_gap.
        inputs: Calculation input parameters.

    Returns:
        Calculation result dict.
    """
    if calc_type == "m_score":
        return _run_m_score(inputs)

    elif calc_type == "dcf_valuation":
        return _run_dcf_valuation(inputs)

    elif calc_type == "yield_gap":
        return _run_yield_gap(inputs)

    else:
        return {"status": "error", "message": f"Unknown calculation type: {calc_type}"}


def _run_m_score(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run M-Score calculation in subprocess via RiskAnalyzer."""
    from stockvaluefinder.services.risk_service import RiskAnalyzer

    risk_analyzer = RiskAnalyzer()
    current_report = inputs.get("current_report", {})
    previous_report = inputs.get("previous_report")
    risk_result = risk_analyzer.analyze(current_report, previous_report)
    return {
        "status": "ok",
        "data": {
            "m_score": risk_result.m_score
            if hasattr(risk_result, "m_score")
            else str(risk_result),
        },
    }


def _run_dcf_valuation(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run DCF valuation in subprocess via DCFValuationService."""
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
    return {"status": "ok", "data": str(val_result)}


def _run_yield_gap(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run yield gap calculation in subprocess via YieldAnalyzer."""
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
    return {"status": "ok", "data": str(yield_result)}


def main() -> None:
    """Read request from stdin, set limits, run calculation, write result to stdout."""
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        json.dump(
            {"status": "error", "message": f"Invalid JSON input: {e}"}, sys.stdout
        )
        sys.exit(1)

    calc_type = request.get("type", "")
    inputs = request.get("inputs", {})
    timeout = request.get("timeout", 30)
    max_memory_bytes = request.get("max_memory_bytes", 256 * 1024 * 1024)

    # Set resource limits BEFORE importing calculation modules
    try:
        set_resource_limits(timeout, max_memory_bytes)
    except (ValueError, OSError) as e:
        json.dump(
            {"status": "error", "message": f"Failed to set resource limits: {e}"},
            sys.stdout,
        )
        sys.exit(1)

    # Execute calculation
    try:
        result = run_calculation(calc_type, inputs)
        json.dump(result, sys.stdout)
    except MemoryError:
        json.dump({"status": "error", "message": "Memory limit exceeded"}, sys.stdout)
        sys.exit(1)
    except Exception as e:
        json.dump(
            {
                "status": "error",
                "message": f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            },
            sys.stdout,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
