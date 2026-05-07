"""Alpha composite score pure calculation functions.

This module provides pure functions for normalizing four forward-looking
analysis dimensions to 0-100 scores and computing a weighted composite
Alpha score with fixed transparent weights (40/30/20/10).

Normalization functions:
    - normalize_roic_wacc_score: Linear clamp +/-10% (D-02)
    - normalize_capex_score: Letter grade A/B/C/D mapping (D-03)
    - normalize_policy_score: Pass-through with safety clamp
    - normalize_moat_score: Three-tier MoatTrend mapping (D-04)

Composite functions:
    - calculate_alpha_score: Weighted sum of normalized components
    - classify_alpha_level: Score to EXCELLENT/GOOD/FAIR/WEAK/POOR tier

All functions are stateless pure functions with no I/O side effects.
"""

from stockvaluefinder.config import alpha_config
from stockvaluefinder.models.capital_allocation import CapitalAllocationGrade
from stockvaluefinder.models.enums import AlphaLevel
from stockvaluefinder.models.roic import MoatTrend


def normalize_roic_wacc_score(spread: float | None) -> float:
    """Map ROIC-WACC spread to 0-100 using linear clamp +/-10% (D-02).

    Spread values are clamped to [-0.10, +0.10], then linearly interpolated
    to [0, 100]. A None spread (negative invested capital) returns 0.

    Args:
        spread: ROIC - WACC spread as decimal (e.g. 0.05 = 5%).

    Returns:
        Normalized score in range [0.0, 100.0].

    Examples:
        >>> normalize_roic_wacc_score(None)
        0.0
        >>> normalize_roic_wacc_score(-0.10)
        0.0
        >>> normalize_roic_wacc_score(0.10)
        100.0
        >>> normalize_roic_wacc_score(0.0)
        50.0
        >>> normalize_roic_wacc_score(0.05)
        75.0
    """
    if spread is None:
        return 0.0

    # Guard against NaN
    if spread != spread:
        return 0.0

    clamped = max(
        alpha_config.SPREAD_CLAMP_MIN,
        min(alpha_config.SPREAD_CLAMP_MAX, spread),
    )
    range_width = alpha_config.SPREAD_CLAMP_MAX - alpha_config.SPREAD_CLAMP_MIN
    return round((clamped - alpha_config.SPREAD_CLAMP_MIN) / range_width * 100.0, 2)


def normalize_capex_score(grade: CapitalAllocationGrade) -> float:
    """Map capital allocation grade to 0-100 score (D-03).

    Linear grade mapping: A=100, B=75, C=50, D=25. Even 25-point steps
    for simple, transparent, auditable scoring.

    Args:
        grade: Capital allocation letter grade (A/B/C/D).

    Returns:
        Mapped score: 100.0, 75.0, 50.0, or 25.0.

    Examples:
        >>> normalize_capex_score(CapitalAllocationGrade.A)
        100.0
        >>> normalize_capex_score(CapitalAllocationGrade.D)
        25.0
    """
    mapping: dict[CapitalAllocationGrade, float] = {
        CapitalAllocationGrade.A: 100.0,
        CapitalAllocationGrade.B: 75.0,
        CapitalAllocationGrade.C: 50.0,
        CapitalAllocationGrade.D: 25.0,
    }
    return mapping[grade]


def normalize_policy_score(score: float) -> float:
    """Pass-through policy resonance score with safety clamp.

    Policy resonance score is already 0-100 from the policy engine.
    This function applies a safety clamp at boundaries to handle
    any edge cases.

    Args:
        score: Policy resonance score (expected 0-100).

    Returns:
        Score clamped to [0.0, 100.0].

    Examples:
        >>> normalize_policy_score(75.0)
        75.0
        >>> normalize_policy_score(-5.0)
        0.0
        >>> normalize_policy_score(150.0)
        100.0
    """
    return max(0.0, min(100.0, score))


def normalize_moat_score(trend: MoatTrend | None) -> float:
    """Map moat trend enum to 0-100 score (D-04).

    Three-tier mapping:
        - COMPETITIVE_ADVANTAGE: 100 (widening moat is rewarded)
        - STABLE: 50 (maintaining position)
        - DETERIORATING, INSUFFICIENT_DATA, None: 0 (not rewarded)

    Args:
        trend: MoatTrend enum value, or None if no trend data.

    Returns:
        Mapped score: 100.0, 50.0, or 0.0.

    Examples:
        >>> normalize_moat_score(MoatTrend.COMPETITIVE_ADVANTAGE)
        100.0
        >>> normalize_moat_score(MoatTrend.STABLE)
        50.0
        >>> normalize_moat_score(None)
        0.0
    """
    if trend == MoatTrend.COMPETITIVE_ADVANTAGE:
        return 100.0
    elif trend == MoatTrend.STABLE:
        return 50.0
    return 0.0


def calculate_alpha_score(
    roic_wacc_score: float,
    capex_score: float,
    policy_score: float,
    moat_score: float,
    weights: tuple[float, float, float, float] = (0.40, 0.30, 0.20, 0.10),
) -> float:
    """Calculate weighted composite Alpha score.

    Applies fixed weights (D-01) to four normalized component scores:
    ROIC-WACC 40%, Capital Allocation 30%, Policy 20%, Moat 10%.

    Args:
        roic_wacc_score: Normalized ROIC-WACC component (0-100).
        capex_score: Normalized capital allocation component (0-100).
        policy_score: Normalized policy resonance component (0-100).
        moat_score: Normalized moat trend component (0-100).
        weights: Optional custom weights as (roic, capex, policy, moat).
            Defaults to (0.40, 0.30, 0.20, 0.10).

    Returns:
        Weighted composite score rounded to 2 decimal places.

    Examples:
        >>> calculate_alpha_score(100.0, 100.0, 100.0, 100.0)
        100.0
        >>> calculate_alpha_score(100.0, 75.0, 50.0, 0.0)
        72.5
        >>> calculate_alpha_score(0.0, 0.0, 0.0, 0.0)
        0.0
    """
    if len(weights) != 4:
        raise ValueError(f"weights must have exactly 4 elements, got {len(weights)}")
    if abs(sum(weights) - 1.0) > 0.01:
        raise ValueError(f"weights must sum to approximately 1.0, got {sum(weights)}")

    raw = (
        roic_wacc_score * weights[0]
        + capex_score * weights[1]
        + policy_score * weights[2]
        + moat_score * weights[3]
    )
    return round(raw, 2)


def classify_alpha_level(score: float) -> AlphaLevel:
    """Classify Alpha score into tier.

    Tier boundaries:
        - EXCELLENT: >= 80
        - GOOD: >= 60
        - FAIR: >= 40
        - WEAK: >= 20
        - POOR: < 20

    Args:
        score: Composite Alpha score (0-100).

    Returns:
        AlphaLevel enum classification.

    Examples:
        >>> classify_alpha_level(100.0)
        <AlphaLevel.EXCELLENT: 'EXCELLENT'>
        >>> classify_alpha_level(60.0)
        <AlphaLevel.GOOD: 'GOOD'>
        >>> classify_alpha_level(0.0)
        <AlphaLevel.POOR: 'POOR'>
    """
    if score >= 80.0:
        return AlphaLevel.EXCELLENT
    elif score >= 60.0:
        return AlphaLevel.GOOD
    elif score >= 40.0:
        return AlphaLevel.FAIR
    elif score >= 20.0:
        return AlphaLevel.WEAK
    return AlphaLevel.POOR
