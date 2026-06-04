"""Quality review gate for value-confirmed stocks (SCR-03).

This module provides a pure-function quality review that checks whether a
stock passes all quality criteria before entering the candidate list.
All checks are deterministic and use only pre-computed analysis results
as inputs -- no I/O, no external calls, no class dependencies.

Quality checks:
    1. ROIC-WACC spread: positive spread required
    2. M-Score: below -1.78 manipulation threshold
    3. Cash flow divergence: profit-cash divergence not detected
    4. Risk level: not HIGH or CRITICAL
    5. Leverage: no cun-dai-shuang-gao anomaly
    6. Dividend sustainability: yield gap >= -2% boundary

Graceful degradation: When a data source is None (unavailable), the
corresponding checks are recorded as passing (True) rather than failing,
allowing partial data to still produce a valid review result.
"""

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import RiskLevel
from stockvaluefinder.models.risk import RiskScore
from stockvaluefinder.models.valuation import ValuationResult
from stockvaluefinder.models.yield_gap import YieldGap


class QualityReviewResult(BaseModel):
    """Result of a quality review evaluation.

    Attributes:
        passed: True if the stock passes all quality checks.
        failure_reasons: List of human-readable failure messages
            (empty when passed=True).
        checks_detail: Mapping of check name to pass/fail boolean
            for audit trail and debugging.
    """

    model_config = {"frozen": True}

    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)
    checks_detail: dict[str, bool] = Field(default_factory=dict)


# M-Score manipulation threshold from Beneish (1999)
_MSCORE_THRESHOLD: float = -1.78

# Dividend sustainability boundary: yield gap below this triggers failure
_DIVIDEND_YIELD_GAP_FLOOR: float = -0.02

# Check name constants for consistency
_CHECK_ROIC_WACC = "roic_wacc_spread"
_CHECK_MSCORE = "m_score"
_CHECK_CASH_FLOW = "cash_flow_divergence"
_CHECK_RISK_LEVEL = "risk_level"
_CHECK_LEVERAGE = "leverage"
_CHECK_DIVIDEND = "dividend_sustainability"


def review_stock_quality(
    valuation_result: ValuationResult | None = None,
    risk_score: RiskScore | None = None,
    yield_gap: YieldGap | None = None,
    roic_wacc_spread: float | None = None,
) -> QualityReviewResult:
    """Evaluate whether a stock passes quality review (SCR-03).

    Checks six quality criteria against pre-computed analysis results.
    Any single failure causes the overall result to be passed=False.
    Missing data (None inputs) triggers graceful degradation: the
    corresponding checks are recorded as passing rather than failing.

    Args:
        valuation_result: DCF valuation result (currently unused directly
            but reserved for future checks).
        risk_score: Risk analysis result with M-Score, risk level,
            divergence flag, and leverage anomaly.
        yield_gap: Dividend yield gap analysis result.
        roic_wacc_spread: ROIC minus WACC spread as decimal
            (e.g., 0.05 means 5% positive spread).

    Returns:
        QualityReviewResult with passed flag, failure reasons, and
        per-check detail mapping.

    Examples:
        >>> review_stock_quality(roic_wacc_spread=0.05)
        QualityReviewResult(passed=True, ...)
        >>> review_stock_quality(roic_wacc_spread=-0.01)
        QualityReviewResult(passed=False, ...)
    """
    failures: list[str] = []
    checks: dict[str, bool] = {}

    # Check 1: ROIC-WACC spread
    if roic_wacc_spread is not None:
        checks[_CHECK_ROIC_WACC] = roic_wacc_spread > 0
        if roic_wacc_spread <= 0:
            failures.append(
                f"ROIC-WACC spread {roic_wacc_spread:.2%} is non-positive"
            )
    else:
        checks[_CHECK_ROIC_WACC] = True

    # Checks 2-5 depend on risk_score
    if risk_score is not None:
        # Check 2: M-Score manipulation threshold
        checks[_CHECK_MSCORE] = risk_score.m_score < _MSCORE_THRESHOLD
        if risk_score.m_score >= _MSCORE_THRESHOLD:
            failures.append(
                f"M-Score {risk_score.m_score:.2f} above manipulation "
                f"threshold {_MSCORE_THRESHOLD:.2f}"
            )

        # Check 3: Cash flow divergence
        checks[_CHECK_CASH_FLOW] = not risk_score.profit_cash_divergence
        if risk_score.profit_cash_divergence:
            failures.append("Profit-cash flow divergence detected")

        # Check 4: Risk level gate
        checks[_CHECK_RISK_LEVEL] = risk_score.risk_level not in (
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        )
        if risk_score.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            failures.append(
                f"Risk level {risk_score.risk_level.value} exceeds "
                f"acceptable threshold"
            )

        # Check 5: Leverage (cun-dai-shuang-gao)
        checks[_CHECK_LEVERAGE] = not risk_score.存贷双高
        if risk_score.存贷双高:
            failures.append(
                "High cash and high debt anomaly (cun-dai-shuang-gao)"
            )
    else:
        # Graceful degradation: no risk data = not a failure
        checks[_CHECK_MSCORE] = True
        checks[_CHECK_CASH_FLOW] = True
        checks[_CHECK_RISK_LEVEL] = True
        checks[_CHECK_LEVERAGE] = True

    # Check 6: Dividend sustainability
    if yield_gap is not None:
        checks[_CHECK_DIVIDEND] = yield_gap.yield_gap >= _DIVIDEND_YIELD_GAP_FLOOR
        if yield_gap.yield_gap < _DIVIDEND_YIELD_GAP_FLOOR:
            failures.append(
                f"Negative yield gap ({yield_gap.yield_gap:.2%}), "
                f"dividend sustainability concern"
            )
    else:
        checks[_CHECK_DIVIDEND] = True

    return QualityReviewResult(
        passed=len(failures) == 0,
        failure_reasons=failures,
        checks_detail=checks,
    )


__all__ = ["QualityReviewResult", "review_stock_quality"]
