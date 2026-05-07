"""Capital allocation scorecard service - pure functions for management quality assessment.

This module provides pure functions for evaluating how well management deploys
shareholder capital across three dimensions:

1. **Buyback Yield** (CAPEX-01): Repurchase amount / market cap
2. **Dividend Stability** (CAPEX-02): 5-year DPU trend via scipy linregress
3. **Expansion Discipline** (CAPEX-03): Blind expansion = ROIC < WACC + CapEx surge

The combined scorecard produces an A/B/C/D letter grade with equal weighting
(1/3 each) per D-07/D-08.

All functions are stateless pure functions with no I/O side effects.
"""

from typing import Any

from stockvaluefinder.config import capital_allocation_config
from stockvaluefinder.models.capital_allocation import (
    CapitalAllocationGrade,
    DividendTrend,
)


def calculate_buyback_yield(
    repurchase_amount: float | None,
    market_cap: float | None,
) -> float | None:
    """Calculate buyback yield from repurchase amount and market cap (D-02).

    Formula: buyback_yield = repurchase_amount / market_cap

    Args:
        repurchase_amount: Annual repurchase amount in CNY, None if unavailable.
        market_cap: Market capitalization in CNY, None if unavailable.

    Returns:
        Buyback yield as decimal (e.g. 0.02 = 2%), or None if inputs are
        None or market_cap is 0.

    Examples:
        >>> abs(calculate_buyback_yield(100_000_000, 5_000_000_000) - 0.02) < 1e-10
        True
        >>> calculate_buyback_yield(None, 5_000_000_000) is None
        True
        >>> calculate_buyback_yield(100_000_000, 0) is None
        True
    """
    if repurchase_amount is None or market_cap is None or market_cap == 0:
        return None
    return round(repurchase_amount / market_cap, 6)


def grade_buyback_yield(buyback_yield: float | None) -> CapitalAllocationGrade:
    """Grade buyback yield dimension (CAPEX-01).

    Grade boundaries (per CapitalAllocationConfig):
        - A: yield >= 2% (0.02)
        - B: yield >= 1% (0.01) and < 2%
        - C: yield >= 0.5% (0.005) and < 1%
        - D: yield < 0.5% or None

    Args:
        buyback_yield: Buyback yield as decimal, or None if no data.

    Returns:
        CapitalAllocationGrade for the buyback dimension.

    Examples:
        >>> grade_buyback_yield(0.025)
        <CapitalAllocationGrade.A: 'A'>
        >>> grade_buyback_yield(None)
        <CapitalAllocationGrade.D: 'D'>
    """
    if buyback_yield is None:
        return CapitalAllocationGrade.D

    if buyback_yield >= capital_allocation_config.BUYBACK_YIELD_GRADE_A:
        return CapitalAllocationGrade.A
    elif buyback_yield >= capital_allocation_config.BUYBACK_YIELD_GRADE_B:
        return CapitalAllocationGrade.B
    elif buyback_yield >= capital_allocation_config.BUYBACK_YIELD_GRADE_C:
        return CapitalAllocationGrade.C
    else:
        return CapitalAllocationGrade.D


def classify_dividend_stability(
    dpu_values: list[float | None],
    years: list[int],
) -> dict[str, Any]:
    """Classify 5-year dividend per unit stability trend (D-04).

    Uses scipy.stats.linregress to compute the slope of the DPU time series,
    reusing the analyze_roic_trend() pattern from roic_service.py.

    Classification:
        - slope > DPU_TREND_THRESHOLD (0.05): GROWTH
        - slope < -DPU_TREND_THRESHOLD (-0.05): DECLINE
        - Otherwise: STABLE
        - Fewer than MIN_DPU_DATA_POINTS (3) valid points: INSUFFICIENT_DATA

    Args:
        dpu_values: List of dividend per unit values (may contain None/NaN/0).
        years: List of fiscal years corresponding to each DPU value.

    Returns:
        Dictionary with keys:
            - classification: DividendTrend enum
            - slope: Linear regression slope (or None if insufficient data)
            - p_value: Statistical significance (or None if insufficient data)
            - data_points: Number of valid data points used

    Examples:
        >>> r = classify_dividend_stability([1.0, 1.1, 1.2, 1.3, 1.4], [2019, 2020, 2021, 2022, 2023])
        >>> r["classification"] == DividendTrend.GROWTH
        True
    """
    # Filter out None, NaN, and zero DPU values, keeping corresponding years
    valid: list[float] = []
    valid_years: list[int] = []
    for dpu, year in zip(dpu_values, years):
        if dpu is not None and dpu == dpu and dpu > 0:  # NaN check + positive only
            valid.append(float(dpu))
            valid_years.append(year)

    if len(valid) < capital_allocation_config.MIN_DPU_DATA_POINTS:
        return {
            "classification": DividendTrend.INSUFFICIENT_DATA,
            "slope": None,
            "p_value": None,
            "data_points": len(valid),
        }

    # Use year values for x-axis (more meaningful than ordinal positions)
    x = valid_years
    y = valid

    # Lazy import consistent with project convention
    from scipy.stats import linregress

    regression_result = linregress(x, y)
    slope = regression_result.slope
    p_value = regression_result.pvalue

    threshold = capital_allocation_config.DPU_TREND_THRESHOLD
    if slope > threshold:
        classification = DividendTrend.GROWTH
    elif slope < -threshold:
        classification = DividendTrend.DECLINE
    else:
        classification = DividendTrend.STABLE

    return {
        "classification": classification,
        "slope": round(slope, 6),
        "p_value": round(p_value, 6),
        "data_points": len(valid),
    }


def grade_dividend_stability(
    classification: DividendTrend,
) -> CapitalAllocationGrade:
    """Grade dividend stability dimension (CAPEX-02).

    Grade mapping:
        - GROWTH: A (consistently increasing dividends)
        - STABLE: B (reliable dividend payer)
        - INSUFFICIENT_DATA: C (neutral, cannot assess)
        - DECLINE: D (dividends declining, warning signal)

    Args:
        classification: DividendTrend enum from classify_dividend_stability.

    Returns:
        CapitalAllocationGrade for the dividend stability dimension.

    Examples:
        >>> grade_dividend_stability(DividendTrend.GROWTH)
        <CapitalAllocationGrade.A: 'A'>
    """
    grade_map: dict[DividendTrend, CapitalAllocationGrade] = {
        DividendTrend.GROWTH: CapitalAllocationGrade.A,
        DividendTrend.STABLE: CapitalAllocationGrade.B,
        DividendTrend.INSUFFICIENT_DATA: CapitalAllocationGrade.C,
        DividendTrend.DECLINE: CapitalAllocationGrade.D,
    }
    return grade_map[classification]


def detect_blind_expansion(
    roic: float | None,
    wacc: float,
    capex_current: float | None,
    capex_previous: float | None,
) -> dict[str, Any]:
    """Detect blind expansion: value destruction combined with aggressive capex (D-05).

    Alert triggers when:
    1. ROIC < WACC (value destroying per Phase 9)
    2. YoY CapEx growth > CAPEX_GROWTH_THRESHOLD (20%)

    Uses abs() on CapEx values before computing growth, since cash flow
    outflows are reported as negative numbers.

    Args:
        roic: Return on Invested Capital from Phase 9, or None.
        wacc: Weighted Average Cost of Capital.
        capex_current: Current year capital expenditure (may be negative).
        capex_previous: Previous year capital expenditure (may be negative).

    Returns:
        Dictionary with keys:
            - alert: bool - True if blind expansion detected
            - roic_wacc_spread: ROIC - WACC spread (or None)
            - capex_yoy_growth: YoY CapEx growth rate (or None)
            - capex_current: Current year CapEx (or None)
            - capex_previous: Previous year CapEx (or None)
            - reason: str or None - explanation when no alert

    Examples:
        >>> r = detect_blind_expansion(0.05, 0.10, 150, 100)
        >>> r["alert"]
        True
    """
    # Check for insufficient data
    if roic is None:
        return {
            "alert": False,
            "roic_wacc_spread": None,
            "capex_yoy_growth": None,
            "capex_current": capex_current,
            "capex_previous": capex_previous,
            "reason": "insufficient_data",
        }

    if capex_current is None or capex_previous is None:
        return {
            "alert": False,
            "roic_wacc_spread": round(roic - wacc, 6),
            "capex_yoy_growth": None,
            "capex_current": capex_current,
            "capex_previous": capex_previous,
            "reason": "insufficient_data",
        }

    # Use abs() for CapEx (cash flow outflow is negative)
    abs_current = abs(capex_current)
    abs_previous = abs(capex_previous)

    # Handle no prior CapEx
    if abs_previous == 0:
        return {
            "alert": False,
            "roic_wacc_spread": round(roic - wacc, 6),
            "capex_yoy_growth": None,
            "capex_current": capex_current,
            "capex_previous": capex_previous,
            "reason": "no_prior_capex",
        }

    spread = round(roic - wacc, 6)
    capex_growth = (abs_current - abs_previous) / abs_previous
    capex_growth = round(capex_growth, 6)

    # Check if value-creating (ROIC >= WACC)
    if spread >= 0:
        return {
            "alert": False,
            "roic_wacc_spread": spread,
            "capex_yoy_growth": capex_growth,
            "capex_current": capex_current,
            "capex_previous": capex_previous,
            "reason": "value_creating",
        }

    # Value-destroying: check CapEx growth
    threshold = capital_allocation_config.CAPEX_GROWTH_THRESHOLD
    alert = capex_growth > threshold

    return {
        "alert": alert,
        "roic_wacc_spread": spread,
        "capex_yoy_growth": capex_growth,
        "capex_current": capex_current,
        "capex_previous": capex_previous,
        "reason": None if alert else "below_threshold",
    }


def grade_expansion_discipline(
    blind_expansion: dict[str, Any],
) -> CapitalAllocationGrade:
    """Grade expansion discipline dimension (CAPEX-03).

    Grade mapping:
        - No alert: A (management deploys capital wisely)
        - Alert + CapEx growth <= 50%: C (moderate concern)
        - Alert + CapEx growth > 50%: D (severe concern)
        - Insufficient data (reason set): C (neutral)

    Args:
        blind_expansion: Result dict from detect_blind_expansion().

    Returns:
        CapitalAllocationGrade for the expansion discipline dimension.

    Examples:
        >>> grade_expansion_discipline({"alert": False, "capex_yoy_growth": 0.1})
        <CapitalAllocationGrade.A: 'A'>
    """
    # Insufficient data or no prior capex -> neutral grade C
    reason = blind_expansion.get("reason")
    if reason in ("insufficient_data", "no_prior_capex"):
        return CapitalAllocationGrade.C

    if not blind_expansion["alert"]:
        return CapitalAllocationGrade.A

    # Alert triggered: grade based on CapEx growth severity
    growth = blind_expansion.get("capex_yoy_growth")
    if (
        growth is not None
        and growth > capital_allocation_config.EXPANSION_ALERT_GRADE_C_THRESHOLD
    ):
        return CapitalAllocationGrade.D
    return CapitalAllocationGrade.C


def calculate_capital_allocation_score(
    buyback_grade: CapitalAllocationGrade | None,
    dividend_grade: CapitalAllocationGrade,
    expansion_grade: CapitalAllocationGrade,
) -> tuple[CapitalAllocationGrade, dict[str, float]]:
    """Calculate combined capital allocation scorecard grade (D-07, D-08).

    Uses equal weighting (1/3 each) for three dimensions. When buyback data
    is unavailable (None), reweights remaining two dimensions to 50/50.

    Grade numeric mapping: A=4, B=3, C=2, D=1
    Overall grade boundaries:
        - >= 3.5: A
        - >= 2.5: B
        - >= 1.5: C
        - < 1.5: D

    Args:
        buyback_grade: Grade for buyback yield, or None if no buyback data.
        dividend_grade: Grade for dividend stability.
        expansion_grade: Grade for expansion discipline.

    Returns:
        Tuple of (overall_grade, weights_dict) where weights_dict shows
        the actual weights used per dimension.

    Examples:
        >>> g, w = calculate_capital_allocation_score(
        ...     CapitalAllocationGrade.A, CapitalAllocationGrade.A, CapitalAllocationGrade.A
        ... )
        >>> g
        <CapitalAllocationGrade.A: 'A'>
    """
    grade_to_numeric: dict[CapitalAllocationGrade, int] = {
        CapitalAllocationGrade.A: 4,
        CapitalAllocationGrade.B: 3,
        CapitalAllocationGrade.C: 2,
        CapitalAllocationGrade.D: 1,
    }

    if buyback_grade is None:
        # Reweight to 50/50 for remaining two dimensions
        dividend_numeric = grade_to_numeric[dividend_grade]
        expansion_numeric = grade_to_numeric[expansion_grade]
        avg = (dividend_numeric + expansion_numeric) / 2.0
        weights = {
            "buyback_yield": 0.0,
            "dividend_stability": 0.5,
            "expansion_discipline": 0.5,
        }
    else:
        buyback_numeric = grade_to_numeric[buyback_grade]
        dividend_numeric = grade_to_numeric[dividend_grade]
        expansion_numeric = grade_to_numeric[expansion_grade]
        avg = (buyback_numeric + dividend_numeric + expansion_numeric) / 3.0
        weights = {
            "buyback_yield": 1.0 / 3,
            "dividend_stability": 1.0 / 3,
            "expansion_discipline": 1.0 / 3,
        }

    # Map average back to letter grade using thresholds
    cfg = capital_allocation_config
    if avg >= cfg.OVERALL_GRADE_A_THRESHOLD:
        overall = CapitalAllocationGrade.A
    elif avg >= cfg.OVERALL_GRADE_B_THRESHOLD:
        overall = CapitalAllocationGrade.B
    elif avg >= cfg.OVERALL_GRADE_C_THRESHOLD:
        overall = CapitalAllocationGrade.C
    else:
        overall = CapitalAllocationGrade.D

    return overall, weights
