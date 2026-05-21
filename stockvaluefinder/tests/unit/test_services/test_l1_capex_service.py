"""L1 formula verification tests for capex_service pure functions.

Verifies buyback yield, buyback yield grading, dividend stability classification,
blind expansion detection, expansion discipline grading, and capital allocation
scorecard computation.

All tests decorated with @pytest.mark.l1_formula for CI marker filtering.
"""

import pytest

from stockvaluefinder.models.capital_allocation import (
    CapitalAllocationGrade,
    DividendTrend,
)
from stockvaluefinder.services.capex_service import (
    calculate_buyback_yield,
    calculate_capital_allocation_score,
    classify_dividend_stability,
    detect_blind_expansion,
    grade_buyback_yield,
)


# ---------------------------------------------------------------------------
# Buyback yield
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1BuybackYield:
    """L1 tests for buyback yield calculation.

    Formula: buyback_yield = repurchase_amount / market_cap
    """

    def test_buyback_yield_2pct(self) -> None:
        """repurchase=100M, market_cap=5B -> yield=0.02."""
        result = calculate_buyback_yield(100_000_000, 5_000_000_000)
        assert result is not None
        assert result == pytest.approx(0.02, abs=1e-6)

    def test_buyback_yield_none_repurchase(self) -> None:
        """repurchase=None -> None."""
        result = calculate_buyback_yield(None, 5_000_000_000)
        assert result is None

    def test_buyback_yield_zero_market_cap(self) -> None:
        """market_cap=0 -> None (avoid division by zero)."""
        result = calculate_buyback_yield(100_000_000, 0)
        assert result is None

    def test_buyback_yield_half_pct(self) -> None:
        """repurchase=50M, market_cap=10B -> yield=0.005."""
        result = calculate_buyback_yield(50_000_000, 10_000_000_000)
        assert result is not None
        assert result == pytest.approx(0.005, abs=1e-6)


# ---------------------------------------------------------------------------
# Grade buyback yield
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1GradeBuybackYield:
    """L1 tests for buyback yield grading.

    Grade boundaries:
    - A: yield >= 2% (0.02)
    - B: yield >= 1% (0.01)
    - C: yield >= 0.5% (0.005)
    - D: yield < 0.5% or None
    """

    def test_grade_a(self) -> None:
        """yield=0.025 (>=2%) -> A."""
        assert grade_buyback_yield(0.025) == CapitalAllocationGrade.A

    def test_grade_b(self) -> None:
        """yield=0.015 (>=1%) -> B."""
        assert grade_buyback_yield(0.015) == CapitalAllocationGrade.B

    def test_grade_c(self) -> None:
        """yield=0.007 (>=0.5%) -> C."""
        assert grade_buyback_yield(0.007) == CapitalAllocationGrade.C

    def test_grade_d_low_yield(self) -> None:
        """yield=0.003 (<0.5%) -> D."""
        assert grade_buyback_yield(0.003) == CapitalAllocationGrade.D

    def test_grade_d_none(self) -> None:
        """yield=None -> D."""
        assert grade_buyback_yield(None) == CapitalAllocationGrade.D


# ---------------------------------------------------------------------------
# Dividend stability
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1DividendStability:
    """L1 tests for dividend stability classification via linear regression.

    Classification based on regression slope vs threshold (0.05):
    - slope > 0.05: GROWTH
    - slope < -0.05: DECLINE
    - otherwise: STABLE
    - < 3 valid points: INSUFFICIENT_DATA
    """

    def test_growth_trend(self) -> None:
        """Growth: [1.0, 1.1, 1.2, 1.3, 1.4] -> GROWTH."""
        result = classify_dividend_stability(
            [1.0, 1.1, 1.2, 1.3, 1.4], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["classification"] == DividendTrend.GROWTH

    def test_decline_trend(self) -> None:
        """Decline: [1.4, 1.3, 1.2, 1.1, 1.0] -> DECLINE."""
        result = classify_dividend_stability(
            [1.4, 1.3, 1.2, 1.1, 1.0], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["classification"] == DividendTrend.DECLINE

    def test_stable_trend(self) -> None:
        """Stable: [1.0, 1.0, 1.0, 1.0, 1.0] -> STABLE."""
        result = classify_dividend_stability(
            [1.0, 1.0, 1.0, 1.0, 1.0], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["classification"] == DividendTrend.STABLE

    def test_insufficient_data(self) -> None:
        """Insufficient: [1.0, 1.1] (< 3 points) -> INSUFFICIENT_DATA."""
        result = classify_dividend_stability([1.0, 1.1], [2022, 2023])
        assert result["classification"] == DividendTrend.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Blind expansion detection
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1BlindExpansion:
    """L1 tests for blind expansion detection.

    Alert triggers when:
    1. ROIC < WACC (value destroying)
    2. CapEx YoY growth > 20% (using abs() on CapEx values)
    """

    def test_blind_expansion_alert(self) -> None:
        """ROIC=0.05 < WACC=0.10, CapEx growth=50% -> alert=True."""
        result = detect_blind_expansion(0.05, 0.10, 150, 100)
        assert result["alert"] is True

    def test_blind_expansion_value_creating(self) -> None:
        """ROIC=0.15 > WACC=0.10 (value creating) -> alert=False, reason=value_creating."""
        result = detect_blind_expansion(0.15, 0.10, 150, 100)
        assert result["alert"] is False
        assert result["reason"] == "value_creating"

    def test_blind_expansion_insufficient_data(self) -> None:
        """ROIC=None -> alert=False, reason=insufficient_data."""
        result = detect_blind_expansion(None, 0.10, 150, 100)
        assert result["alert"] is False
        assert result["reason"] == "insufficient_data"

    def test_blind_expansion_below_threshold(self) -> None:
        """ROIC=0.05 < WACC=0.10, CapEx growth=10% (< 20%) -> alert=False, reason=below_threshold."""
        result = detect_blind_expansion(0.05, 0.10, 110, 100)
        assert result["alert"] is False
        assert result["reason"] == "below_threshold"


# ---------------------------------------------------------------------------
# Capital allocation score
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1CapitalAllocationScore:
    """L1 tests for combined capital allocation scorecard.

    Grade mapping: A=4, B=3, C=2, D=1
    Overall grade thresholds: >=3.5 A, >=2.5 B, >=1.5 C, <1.5 D
    Equal weighting (1/3 each). Reweights to 50/50 when buyback is None.
    """

    def test_all_a(self) -> None:
        """A, A, A -> avg=(4+4+4)/3=4.0 -> A."""
        grade, weights = calculate_capital_allocation_score(
            CapitalAllocationGrade.A,
            CapitalAllocationGrade.A,
            CapitalAllocationGrade.A,
        )
        assert grade == CapitalAllocationGrade.A

    def test_reweighted_without_buyback(self) -> None:
        """A, A, None -> avg=(4+4)/2=4.0 -> A (reweighted 50/50)."""
        grade, weights = calculate_capital_allocation_score(
            None,
            CapitalAllocationGrade.A,
            CapitalAllocationGrade.A,
        )
        assert grade == CapitalAllocationGrade.A
        assert weights["buyback_yield"] == 0.0
        assert weights["dividend_stability"] == pytest.approx(0.5, abs=1e-6)
        assert weights["expansion_discipline"] == pytest.approx(0.5, abs=1e-6)

    def test_all_d(self) -> None:
        """D, D, D -> avg=(1+1+1)/3=1.0 -> D."""
        grade, weights = calculate_capital_allocation_score(
            CapitalAllocationGrade.D,
            CapitalAllocationGrade.D,
            CapitalAllocationGrade.D,
        )
        assert grade == CapitalAllocationGrade.D

    def test_mixed_a_b_c(self) -> None:
        """A, B, C -> avg=(4+3+2)/3=3.0 -> B (>=2.5, <3.5)."""
        grade, weights = calculate_capital_allocation_score(
            CapitalAllocationGrade.A,
            CapitalAllocationGrade.B,
            CapitalAllocationGrade.C,
        )
        assert grade == CapitalAllocationGrade.B
