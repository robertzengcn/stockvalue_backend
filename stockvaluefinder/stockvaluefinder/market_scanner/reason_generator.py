"""Deterministic reason generator for the Market Index Value Scanner (SCR-06).

This module produces structured selection reasons and risk flags from computed
metrics using deterministic templates with actual metric values. It has NO
LLM involvement -- every reason and flag is generated from rule-based templates
triggered by metric thresholds.

Compliance requirement: Every candidate must have at least one risk flag,
enforced by both CandidateReasons model validation (min_length=1) and a
fallback generic flag in generate_reasons().

Public API:
    generate_reasons: Main entry point producing CandidateReasons

Private helpers (each appends to reasons/risk_flags lists):
    _generate_valuation_reasons: Margin of safety reasons/flags
    _generate_risk_reasons: Risk level, M-Score, F-Score, red flags
    _generate_yield_reasons: Yield gap reasons/flags
    _generate_composite_reasons: Composite score reasons
"""

from stockvaluefinder.market_scanner.models import (
    CandidateReasons,
    CompositeScore,
)
from stockvaluefinder.models.enums import RiskLevel
from stockvaluefinder.models.risk import RiskScore
from stockvaluefinder.models.valuation import ValuationResult
from stockvaluefinder.models.yield_gap import YieldGap


def generate_reasons(
    composite_score: CompositeScore,
    valuation_result: ValuationResult | None = None,
    risk_score: RiskScore | None = None,
    yield_gap: YieldGap | None = None,
) -> CandidateReasons:
    """Generate deterministic selection reasons and risk flags from metrics.

    Each domain (valuation, risk, yield, composite) is evaluated by a
    dedicated helper function that appends to shared reasons and risk_flags
    lists. After all helpers run, a compliance check ensures at least one
    risk flag is present.

    Args:
        composite_score: Composite scoring result (required).
        valuation_result: DCF valuation result, or None if unavailable.
        risk_score: Risk analysis result, or None if unavailable.
        yield_gap: Dividend yield gap analysis, or None if unavailable.

    Returns:
        CandidateReasons with reasons and at least one risk flag.

    Examples:
        >>> from stockvaluefinder.market_scanner.models import (
        ...     CompositeScore, CompositeScoreComponents,
        ... )
        >>> cs = CompositeScore(
        ...     composite=75.0,
        ...     components=CompositeScoreComponents(
        ...         safety_margin=50.0, alpha=50.0,
        ...         risk_penalty=50.0, yield_gap=50.0,
        ...         valuation_percentile=50.0,
        ...     ),
        ...     passed_threshold=True,
        ... )
        >>> result = generate_reasons(composite_score=cs)
        >>> len(result.risk_flags) >= 1
        True
    """
    reasons: list[str] = []
    risk_flags: list[str] = []

    _generate_valuation_reasons(valuation_result, reasons, risk_flags)
    _generate_risk_reasons(risk_score, reasons, risk_flags)
    _generate_yield_reasons(yield_gap, reasons, risk_flags)
    _generate_composite_reasons(composite_score, reasons)

    # Compliance enforcement: always at least one risk flag
    if len(risk_flags) == 0:
        risk_flags.append("Standard risk factors apply; review full analysis")

    return CandidateReasons(reasons=reasons, risk_flags=risk_flags)


def _generate_valuation_reasons(
    valuation_result: ValuationResult | None,
    reasons: list[str],
    risk_flags: list[str],
) -> None:
    """Generate reasons and risk flags from DCF valuation margin of safety.

    Args:
        valuation_result: Valuation result with margin_of_safety, or None.
        reasons: List to append selection reasons to.
        risk_flags: List to append risk flags to.
    """
    if valuation_result is None:
        risk_flags.append("DCF valuation not available")
        return

    margin = valuation_result.margin_of_safety

    if margin >= 0.30:
        reasons.append(f"Safety margin {margin:.0%}, above 30% threshold")
    elif margin > 0:
        risk_flags.append(f"Safety margin {margin:.0%} below 30% threshold")
    else:
        risk_flags.append(
            f"No safety margin ({margin:.0%}), intrinsic value below market price"
        )


def _generate_risk_reasons(
    risk_score: RiskScore | None,
    reasons: list[str],
    risk_flags: list[str],
) -> None:
    """Generate reasons and risk flags from risk analysis results.

    Evaluates risk level, M-Score, F-Score, red flags, and individual
    anomaly flags (profit-cash divergence, goodwill, cun-dai-shuang-gao).

    Args:
        risk_score: Risk analysis result, or None if unavailable.
        reasons: List to append selection reasons to.
        risk_flags: List to append risk flags to.
    """
    if risk_score is None:
        risk_flags.append("Risk analysis not available")
        return

    risk_level = risk_score.risk_level
    m_score = risk_score.m_score

    # Risk level evaluation
    if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        risk_flags.append(f"Risk level {risk_level.value}, M-Score={m_score:.2f}")
    elif risk_level == RiskLevel.LOW:
        reasons.append(f"Low risk profile (M-Score={m_score:.2f})")
    elif risk_level == RiskLevel.MEDIUM:
        risk_flags.append(f"Moderate risk level (M-Score={m_score:.2f})")

    # Red flags aggregation
    if risk_score.red_flags:
        truncated = risk_score.red_flags[:3]
        risk_flags.append(
            f"{len(risk_score.red_flags)} risk indicator(s): {'; '.join(truncated)}"
        )

    # Individual anomaly flags
    if risk_score.profit_cash_divergence:
        risk_flags.append("Profit-cash flow divergence detected")

    if risk_score.goodwill_excessive:
        risk_flags.append("Excessive goodwill ratio")

    if risk_score.存贷双高:
        risk_flags.append("High cash and high debt (cun-dai-shuang-gao)")

    # Piotroski F-Score evaluation
    if risk_score.f_score >= 7:
        reasons.append(
            f"Strong Piotroski F-Score ({risk_score.f_score}/9), solid fundamentals"
        )
    elif risk_score.f_score <= 3:
        risk_flags.append(
            f"Low Piotroski F-Score ({risk_score.f_score}/9), fundamental weakness"
        )


def _generate_yield_reasons(
    yield_gap: YieldGap | None,
    reasons: list[str],
    risk_flags: list[str],
) -> None:
    """Generate reasons and risk flags from dividend yield gap analysis.

    Args:
        yield_gap: Yield gap analysis result, or None if unavailable.
        reasons: List to append selection reasons to.
        risk_flags: List to append risk flags to.
    """
    if yield_gap is None:
        risk_flags.append("Dividend yield gap analysis not available")
        return

    gap = yield_gap.yield_gap

    if gap > 0:
        reasons.append(
            f"Positive yield gap ({gap:.2%}), dividend exceeds risk-free rate"
        )
    elif gap < 0:
        risk_flags.append(
            f"Negative yield gap ({gap:.2%}), dividend below risk-free rate"
        )
    else:
        risk_flags.append("Yield gap at breakeven, dividend equals risk-free rate")


def _generate_composite_reasons(
    composite_score: CompositeScore,
    reasons: list[str],
) -> None:
    """Generate reasons from composite score ranking.

    Only generates positive reasons; composite score does not produce
    risk flags (other domain helpers cover risk conditions).

    Args:
        composite_score: Composite scoring result.
        reasons: List to append selection reasons to.
    """
    composite = composite_score.composite

    if composite >= 70:
        reasons.append(f"Composite score {composite:.1f}, strong overall ranking")
    elif composite >= 50:
        reasons.append(f"Composite score {composite:.1f}, moderate overall ranking")
