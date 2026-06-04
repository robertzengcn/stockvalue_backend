"""Composite scoring engine for the Market Index Value Scanner.

This module provides pure functions for normalizing five scoring dimensions
to 0-100 and computing a weighted composite score with configurable weights.
It follows the same pure-function pattern as alpha_service.py.

Normalization functions:
    - normalize_safety_margin: Linear map (0% -> 0, 60% -> 100)
    - normalize_alpha_score: Pass-through with clamp [0, 100]
    - normalize_risk_penalty: RiskLevel enum to inverted score
    - normalize_yield_gap: Linear clamp [-2%, +4%] -> [0, 100]
    - normalize_valuation_percentile: Inverted (lower percentile = higher score)

Composite function:
    - calculate_composite_score: Weighted sum of 5 normalized components

All functions are stateless pure functions with no I/O side effects.
"""

from stockvaluefinder.market_scanner.config import MarketScannerConfig
from stockvaluefinder.market_scanner.models import (
    CompositeScore,
    CompositeScoreComponents,
)
from stockvaluefinder.models.enums import RiskLevel


def normalize_safety_margin(margin: float | None) -> float:
    """Map margin of safety to 0-100 using linear mapping.

    Linear mapping: 0% -> 0, 30% -> 50, 60% -> 100.
    Negative values and None map to 0.0.

    Args:
        margin: Margin of safety as decimal (e.g. 0.30 = 30%).

    Returns:
        Normalized score in range [0.0, 100.0].

    Examples:
        >>> normalize_safety_margin(None)
        0.0
        >>> normalize_safety_margin(-0.10)
        0.0
        >>> normalize_safety_margin(0.30)
        50.0
        >>> normalize_safety_margin(0.60)
        100.0
    """
    if margin is None:
        return 0.0

    # NaN guard
    if margin != margin:
        return 0.0

    if margin <= 0:
        return 0.0

    return round(min(100.0, (margin / 0.60) * 100.0), 2)


def normalize_alpha_score(alpha: float | None) -> float:
    """Pass-through Alpha score with clamp to [0, 100].

    Alpha score is already 0-100 from alpha_service.py.
    This function clamps to valid range.

    Args:
        alpha: Alpha score (expected 0-100).

    Returns:
        Score clamped to [0.0, 100.0].

    Examples:
        >>> normalize_alpha_score(None)
        0.0
        >>> normalize_alpha_score(75.0)
        75.0
        >>> normalize_alpha_score(-5.0)
        0.0
        >>> normalize_alpha_score(150.0)
        100.0
    """
    if alpha is None:
        return 0.0

    # NaN guard
    if alpha != alpha:
        return 0.0

    return round(max(0.0, min(100.0, alpha)), 2)


def normalize_risk_penalty(risk_level: RiskLevel | None) -> float:
    """Map risk level to inverted score (LOW risk = HIGH score).

    Dict mapping pattern matching alpha_service.py normalize_capex_score.

    Args:
        risk_level: RiskLevel enum value, or None if no risk data.

    Returns:
        Mapped score: 100.0 (LOW), 50.0 (MEDIUM), 0.0 (HIGH/CRITICAL/None).

    Examples:
        >>> normalize_risk_penalty(RiskLevel.LOW)
        100.0
        >>> normalize_risk_penalty(RiskLevel.MEDIUM)
        50.0
        >>> normalize_risk_penalty(RiskLevel.HIGH)
        0.0
        >>> normalize_risk_penalty(None)
        0.0
    """
    mapping: dict[RiskLevel, float] = {
        RiskLevel.LOW: 100.0,
        RiskLevel.MEDIUM: 50.0,
        RiskLevel.HIGH: 0.0,
        RiskLevel.CRITICAL: 0.0,
    }
    if risk_level is None:
        return 0.0
    return mapping[risk_level]


def normalize_yield_gap(yield_gap: float | None) -> float:
    """Map yield gap to 0-100 using linear clamp [-2%, +4%].

    Args:
        yield_gap: Yield gap as decimal (e.g. 0.01 = 1%).

    Returns:
        Normalized score in range [0.0, 100.0].

    Examples:
        >>> normalize_yield_gap(None)
        0.0
        >>> normalize_yield_gap(-0.02)
        0.0
        >>> normalize_yield_gap(0.01)
        50.0
        >>> normalize_yield_gap(0.04)
        100.0
    """
    if yield_gap is None:
        return 0.0

    # NaN guard
    if yield_gap != yield_gap:
        return 0.0

    clamped = max(-0.02, min(0.04, yield_gap))
    return round(((clamped + 0.02) / 0.06) * 100.0, 2)


def normalize_valuation_percentile(percentile_rank: float | None) -> float:
    """Map valuation percentile to 0-100 (lower percentile = higher score).

    Inverted mapping: cheapest stocks (low percentile) get highest scores.
    None defaults to 50.0 (neutral) since stocks without percentile data
    should not be penalized or rewarded.

    Args:
        percentile_rank: Valuation percentile rank (0-100).

    Returns:
        Inverted score clamped to [0.0, 100.0].

    Examples:
        >>> normalize_valuation_percentile(0.0)
        100.0
        >>> normalize_valuation_percentile(50.0)
        50.0
        >>> normalize_valuation_percentile(100.0)
        0.0
        >>> normalize_valuation_percentile(None)
        50.0
    """
    if percentile_rank is None:
        return 50.0

    # NaN guard
    if percentile_rank != percentile_rank:
        return 50.0

    return round(max(0.0, min(100.0, 100.0 - percentile_rank)), 2)


def calculate_composite_score(
    margin_of_safety: float | None,
    alpha_score: float | None,
    risk_level: RiskLevel | None,
    yield_gap_value: float | None,
    valuation_percentile: float | None,
    config: MarketScannerConfig,
) -> CompositeScore:
    """Calculate weighted composite score from 5 scoring dimensions.

    Each component is first normalized to 0-100, then combined with
    configurable weights from config.scoring_weights. The composite
    score is rounded to 2 decimal places.

    Args:
        margin_of_safety: DCF margin of safety as decimal (e.g. 0.30).
        alpha_score: Alpha composite score (0-100).
        risk_level: Risk assessment level.
        yield_gap_value: Dividend yield gap as decimal.
        valuation_percentile: Relative valuation percentile (0-100).
        config: Scanner configuration with weights and thresholds.

    Returns:
        CompositeScore with weighted composite, component breakdown, and
        pass/fail threshold status.

    Raises:
        ValueError: If weights are invalid (handled by ScoringWeightsConfig).
    """
    # Normalize each component
    safety = normalize_safety_margin(margin_of_safety)
    alpha = normalize_alpha_score(alpha_score)
    risk = normalize_risk_penalty(risk_level)
    ygap = normalize_yield_gap(yield_gap_value)
    valuation = normalize_valuation_percentile(valuation_percentile)

    # Build components
    components = CompositeScoreComponents(
        safety_margin=safety,
        alpha=alpha,
        risk_penalty=risk,
        yield_gap=ygap,
        valuation_percentile=valuation,
    )

    # Get weights and compute weighted sum
    weights = config.scoring_weights.weights_tuple
    if len(weights) != 5:
        raise ValueError(f"weights must have exactly 5 elements, got {len(weights)}")
    if abs(sum(weights) - 1.0) > 0.01:
        raise ValueError(f"weights must sum to approximately 1.0, got {sum(weights)}")

    component_values = (
        components.safety_margin,
        components.alpha,
        components.risk_penalty,
        components.yield_gap,
        components.valuation_percentile,
    )

    composite = round(
        sum(v * w for v, w in zip(component_values, weights)),
        2,
    )

    passed_threshold = composite >= config.min_composite_score

    return CompositeScore(
        composite=composite,
        components=components,
        passed_threshold=passed_threshold,
    )
