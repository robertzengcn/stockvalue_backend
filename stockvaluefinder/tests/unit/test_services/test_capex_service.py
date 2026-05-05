"""Unit tests for capital allocation service pure functions (TDD RED phase).

Tests cover:
- calculate_buyback_yield: repurchase amount / market cap
- grade_buyback_yield: A/B/C/D grading for buyback dimension
- classify_dividend_stability: 5-year DPU trend via scipy linregress
- grade_dividend_stability: A/B/C/D grading for dividend dimension
- detect_blind_expansion: ROIC < WACC AND CapEx growth > 20%
- grade_expansion_discipline: A/B/C/D grading for expansion dimension
- calculate_capital_allocation_score: combined scorecard with equal weighting
"""

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
    grade_dividend_stability,
    grade_expansion_discipline,
)


# ---------------------------------------------------------------------------
# calculate_buyback_yield
# ---------------------------------------------------------------------------


class TestCalculateBuybackYield:
    """Tests for calculate_buyback_yield() (D-02)."""

    def test_normal_yield(self) -> None:
        """100M repurchase / 5B market cap = 2%."""
        result = calculate_buyback_yield(100_000_000, 5_000_000_000)
        assert result is not None
        assert abs(result - 0.02) < 1e-10

    def test_none_repurchase(self) -> None:
        """None repurchase amount returns None."""
        result = calculate_buyback_yield(None, 5_000_000_000)
        assert result is None

    def test_none_market_cap(self) -> None:
        """None market cap returns None."""
        result = calculate_buyback_yield(100_000_000, None)
        assert result is None

    def test_zero_market_cap(self) -> None:
        """Zero market cap returns None (avoids division by zero)."""
        result = calculate_buyback_yield(100_000_000, 0)
        assert result is None

    def test_zero_repurchase(self) -> None:
        """Zero repurchase returns 0.0 yield."""
        result = calculate_buyback_yield(0, 5_000_000_000)
        assert result is not None
        assert result == 0.0

    def test_large_values(self) -> None:
        """Large realistic values work correctly."""
        result = calculate_buyback_yield(500_000_000, 20_000_000_000)
        assert result is not None
        assert abs(result - 0.025) < 1e-10


# ---------------------------------------------------------------------------
# grade_buyback_yield
# ---------------------------------------------------------------------------


class TestGradeBuybackYield:
    """Tests for grade_buyback_yield() (CAPEX-01)."""

    def test_grade_a_above_2_pct(self) -> None:
        """Buyback yield > 2% = grade A."""
        assert grade_buyback_yield(0.025) == CapitalAllocationGrade.A

    def test_grade_a_at_2_pct(self) -> None:
        """Buyback yield exactly 2% = grade A (boundary)."""
        assert grade_buyback_yield(0.02) == CapitalAllocationGrade.A

    def test_grade_b_1_to_2_pct(self) -> None:
        """Buyback yield 1-2% = grade B."""
        assert grade_buyback_yield(0.015) == CapitalAllocationGrade.B

    def test_grade_b_at_1_pct(self) -> None:
        """Buyback yield exactly 1% = grade B (boundary)."""
        assert grade_buyback_yield(0.01) == CapitalAllocationGrade.B

    def test_grade_c_05_to_1_pct(self) -> None:
        """Buyback yield 0.5-1% = grade C."""
        assert grade_buyback_yield(0.007) == CapitalAllocationGrade.C

    def test_grade_c_at_05_pct(self) -> None:
        """Buyback yield exactly 0.5% = grade C (boundary)."""
        assert grade_buyback_yield(0.005) == CapitalAllocationGrade.C

    def test_grade_d_below_05_pct(self) -> None:
        """Buyback yield < 0.5% = grade D."""
        assert grade_buyback_yield(0.003) == CapitalAllocationGrade.D

    def test_grade_d_zero(self) -> None:
        """Zero buyback yield = grade D."""
        assert grade_buyback_yield(0.0) == CapitalAllocationGrade.D

    def test_grade_d_none(self) -> None:
        """None buyback yield = grade D."""
        assert grade_buyback_yield(None) == CapitalAllocationGrade.D


# ---------------------------------------------------------------------------
# classify_dividend_stability
# ---------------------------------------------------------------------------


class TestClassifyDividendStability:
    """Tests for classify_dividend_stability() (D-04)."""

    def test_growth_trend(self) -> None:
        """Rising DPU values -> GROWTH."""
        result = classify_dividend_stability(
            [1.0, 1.1, 1.2, 1.3, 1.4], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["classification"] == DividendTrend.GROWTH
        assert result["slope"] is not None
        assert result["slope"] > 0
        assert result["data_points"] == 5

    def test_decline_trend(self) -> None:
        """Falling DPU values -> DECLINE."""
        result = classify_dividend_stability(
            [1.4, 1.3, 1.2, 1.1, 1.0], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["classification"] == DividendTrend.DECLINE
        assert result["slope"] is not None
        assert result["slope"] < 0

    def test_stable_trend(self) -> None:
        """Flat DPU values -> STABLE."""
        result = classify_dividend_stability(
            [1.0, 1.0, 1.0, 1.0, 1.0], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["classification"] == DividendTrend.STABLE
        assert result["slope"] is not None
        assert abs(result["slope"]) < 0.05

    def test_insufficient_data(self) -> None:
        """Fewer than 3 valid points -> INSUFFICIENT_DATA."""
        result = classify_dividend_stability([1.0, 1.1], [2022, 2023])
        assert result["classification"] == DividendTrend.INSUFFICIENT_DATA
        assert result["slope"] is None
        assert result["p_value"] is None

    def test_with_none_values(self) -> None:
        """None DPU values are filtered; 3 valid points still works."""
        result = classify_dividend_stability(
            [None, 1.0, 1.1, 1.2, None], [2019, 2020, 2021, 2022, 2023]
        )
        # 3 valid points -> should compute trend
        assert result["data_points"] == 3
        assert result["classification"] == DividendTrend.GROWTH

    def test_too_few_after_filtering(self) -> None:
        """Too many None values -> INSUFFICIENT_DATA."""
        result = classify_dividend_stability(
            [None, None, None, 1.0, 1.1], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["classification"] == DividendTrend.INSUFFICIENT_DATA

    def test_zero_dpu_filtered(self) -> None:
        """Zero DPU values are filtered out."""
        result = classify_dividend_stability(
            [0.0, 0.0, 1.0, 1.1, 1.2], [2019, 2020, 2021, 2022, 2023]
        )
        assert result["data_points"] == 3

    def test_returns_slope_and_pvalue(self) -> None:
        """Result contains slope and p_value."""
        result = classify_dividend_stability(
            [1.0, 1.1, 1.2, 1.3, 1.4], [2019, 2020, 2021, 2022, 2023]
        )
        assert "slope" in result
        assert "p_value" in result
        assert result["slope"] is not None
        assert result["p_value"] is not None


# ---------------------------------------------------------------------------
# grade_dividend_stability
# ---------------------------------------------------------------------------


class TestGradeDividendStability:
    """Tests for grade_dividend_stability()."""

    def test_growth_is_a(self) -> None:
        """GROWTH classification -> grade A."""
        assert (
            grade_dividend_stability(DividendTrend.GROWTH) == CapitalAllocationGrade.A
        )

    def test_stable_is_b(self) -> None:
        """STABLE classification -> grade B."""
        assert (
            grade_dividend_stability(DividendTrend.STABLE) == CapitalAllocationGrade.B
        )

    def test_insufficient_data_is_c(self) -> None:
        """INSUFFICIENT_DATA -> grade C (neutral)."""
        assert (
            grade_dividend_stability(DividendTrend.INSUFFICIENT_DATA)
            == CapitalAllocationGrade.C
        )

    def test_decline_is_d(self) -> None:
        """DECLINE classification -> grade D."""
        assert (
            grade_dividend_stability(DividendTrend.DECLINE) == CapitalAllocationGrade.D
        )


# ---------------------------------------------------------------------------
# detect_blind_expansion
# ---------------------------------------------------------------------------


class TestDetectBlindExpansion:
    """Tests for detect_blind_expansion() (D-05)."""

    def test_alert_triggered(self) -> None:
        """ROIC < WACC AND 50% CapEx growth -> alert."""
        result = detect_blind_expansion(
            roic=0.05, wacc=0.10, capex_current=150, capex_previous=100
        )
        assert result["alert"] is True
        assert result["roic_wacc_spread"] is not None
        assert abs(result["roic_wacc_spread"] - (-0.05)) < 1e-10
        assert result["capex_yoy_growth"] is not None
        assert abs(result["capex_yoy_growth"] - 0.50) < 1e-10

    def test_no_alert_roic_above_wacc(self) -> None:
        """ROIC > WACC -> no alert even with high CapEx growth."""
        result = detect_blind_expansion(
            roic=0.15, wacc=0.10, capex_current=150, capex_previous=100
        )
        assert result["alert"] is False
        assert result["reason"] == "value_creating"

    def test_no_alert_insufficient_roic(self) -> None:
        """None ROIC -> no alert (insufficient data)."""
        result = detect_blind_expansion(
            roic=None, wacc=0.10, capex_current=150, capex_previous=100
        )
        assert result["alert"] is False
        assert result["reason"] == "insufficient_data"

    def test_no_alert_low_capex_growth(self) -> None:
        """10% CapEx growth < 20% threshold -> no alert."""
        result = detect_blind_expansion(
            roic=0.05, wacc=0.10, capex_current=110, capex_previous=100
        )
        assert result["alert"] is False
        assert result["reason"] is not None

    def test_no_prior_capex(self) -> None:
        """Previous CapEx = 0 -> no alert with reason."""
        result = detect_blind_expansion(
            roic=0.05, wacc=0.10, capex_current=150, capex_previous=0
        )
        assert result["alert"] is False
        assert result["reason"] == "no_prior_capex"

    def test_none_capex_values(self) -> None:
        """None CapEx values -> no alert (insufficient data)."""
        result = detect_blind_expansion(
            roic=0.05, wacc=0.10, capex_current=None, capex_previous=100
        )
        assert result["alert"] is False
        assert result["reason"] == "insufficient_data"

    def test_negative_capex_handled(self) -> None:
        """Negative CapEx (cash outflow) handled with abs()."""
        result = detect_blind_expansion(
            roic=0.05, wacc=0.10, capex_current=-150, capex_previous=-100
        )
        assert result["alert"] is True
        assert result["capex_yoy_growth"] is not None
        assert abs(result["capex_yoy_growth"] - 0.50) < 1e-10

    def test_just_above_threshold_triggers(self) -> None:
        """CapEx growth just above 20% threshold -> alert."""
        result = detect_blind_expansion(
            roic=0.05, wacc=0.10, capex_current=121, capex_previous=100
        )
        assert result["alert"] is True

    def test_exact_threshold_no_alert(self) -> None:
        """CapEx growth exactly at 20% threshold -> no alert (> not >=)."""
        result = detect_blind_expansion(
            roic=0.05, wacc=0.10, capex_current=120, capex_previous=100
        )
        assert result["alert"] is False


# ---------------------------------------------------------------------------
# grade_expansion_discipline
# ---------------------------------------------------------------------------


class TestGradeExpansionDiscipline:
    """Tests for grade_expansion_discipline()."""

    def test_no_alert_is_a(self) -> None:
        """No blind expansion alert -> grade A."""
        result = {"alert": False, "capex_yoy_growth": 0.1}
        assert grade_expansion_discipline(result) == CapitalAllocationGrade.A

    def test_alert_moderate_growth_is_c(self) -> None:
        """Alert with CapEx growth 20-50% -> grade C."""
        result = {"alert": True, "capex_yoy_growth": 0.30}
        assert grade_expansion_discipline(result) == CapitalAllocationGrade.C

    def test_alert_at_50_pct_is_c(self) -> None:
        """Alert with CapEx growth exactly 50% -> grade C."""
        result = {"alert": True, "capex_yoy_growth": 0.50}
        assert grade_expansion_discipline(result) == CapitalAllocationGrade.C

    def test_alert_high_growth_is_d(self) -> None:
        """Alert with CapEx growth > 50% -> grade D."""
        result = {"alert": True, "capex_yoy_growth": 0.75}
        assert grade_expansion_discipline(result) == CapitalAllocationGrade.D

    def test_insufficient_data_is_c(self) -> None:
        """Insufficient data (reason set) -> grade C (neutral)."""
        result = {
            "alert": False,
            "capex_yoy_growth": None,
            "reason": "insufficient_data",
        }
        assert grade_expansion_discipline(result) == CapitalAllocationGrade.C

    def test_no_prior_capex_is_c(self) -> None:
        """No prior CapEx -> grade C (neutral)."""
        result = {"alert": False, "capex_yoy_growth": None, "reason": "no_prior_capex"}
        assert grade_expansion_discipline(result) == CapitalAllocationGrade.C


# ---------------------------------------------------------------------------
# calculate_capital_allocation_score
# ---------------------------------------------------------------------------


class TestCalculateCapitalAllocationScore:
    """Tests for calculate_capital_allocation_score() (D-07, D-08)."""

    def test_all_a_grades(self) -> None:
        """All A grades -> overall A."""
        grade, weights = calculate_capital_allocation_score(
            buyback_grade=CapitalAllocationGrade.A,
            dividend_grade=CapitalAllocationGrade.A,
            expansion_grade=CapitalAllocationGrade.A,
        )
        assert grade == CapitalAllocationGrade.A
        assert "buyback_yield" in weights
        assert "dividend_stability" in weights
        assert "expansion_discipline" in weights

    def test_all_d_grades(self) -> None:
        """All D grades -> overall D."""
        grade, weights = calculate_capital_allocation_score(
            buyback_grade=CapitalAllocationGrade.D,
            dividend_grade=CapitalAllocationGrade.D,
            expansion_grade=CapitalAllocationGrade.D,
        )
        assert grade == CapitalAllocationGrade.D

    def test_mixed_grades_b(self) -> None:
        """A + B + C -> average 3.0 -> B (>=2.5)."""
        grade, weights = calculate_capital_allocation_score(
            buyback_grade=CapitalAllocationGrade.A,
            dividend_grade=CapitalAllocationGrade.B,
            expansion_grade=CapitalAllocationGrade.C,
        )
        assert grade == CapitalAllocationGrade.B

    def test_mixed_grades_c(self) -> None:
        """B + C + D -> average 2.0 -> C (>=1.5)."""
        grade, weights = calculate_capital_allocation_score(
            buyback_grade=CapitalAllocationGrade.B,
            dividend_grade=CapitalAllocationGrade.C,
            expansion_grade=CapitalAllocationGrade.D,
        )
        assert grade == CapitalAllocationGrade.C

    def test_missing_buyback_reweights(self) -> None:
        """Missing buyback data reweights to 50/50 for remaining 2 dims."""
        grade, weights = calculate_capital_allocation_score(
            buyback_grade=None,
            dividend_grade=CapitalAllocationGrade.A,
            expansion_grade=CapitalAllocationGrade.A,
        )
        assert grade == CapitalAllocationGrade.A
        # Weights should be 0.5/0.5 for dividend and expansion
        assert weights.get("buyback_yield", 0) == 0
        assert abs(weights["dividend_stability"] - 0.5) < 1e-10
        assert abs(weights["expansion_discipline"] - 0.5) < 1e-10

    def test_missing_buyback_mixed(self) -> None:
        """Missing buyback: A dividend + D expansion -> average 2.5 -> B."""
        grade, weights = calculate_capital_allocation_score(
            buyback_grade=None,
            dividend_grade=CapitalAllocationGrade.A,
            expansion_grade=CapitalAllocationGrade.D,
        )
        assert grade == CapitalAllocationGrade.B

    def test_equal_weights_normal(self) -> None:
        """Normal case uses 1/3 weights per dimension."""
        _, weights = calculate_capital_allocation_score(
            buyback_grade=CapitalAllocationGrade.A,
            dividend_grade=CapitalAllocationGrade.B,
            expansion_grade=CapitalAllocationGrade.C,
        )
        for key in ["buyback_yield", "dividend_stability", "expansion_discipline"]:
            assert abs(weights[key] - 1.0 / 3) < 1e-10

    def test_grade_boundary_a_b(self) -> None:
        """Average exactly 3.5 -> A (boundary)."""
        # Need 3 dims averaging exactly 3.5: A(4) + A(4) + C(2) = 10/3 = 3.33, not 3.5
        # A(4) + A(4) + B(3) = 11/3 = 3.67 -> A
        grade, _ = calculate_capital_allocation_score(
            buyback_grade=CapitalAllocationGrade.A,
            dividend_grade=CapitalAllocationGrade.A,
            expansion_grade=CapitalAllocationGrade.B,
        )
        assert grade == CapitalAllocationGrade.A

    def test_grade_boundary_b_c(self) -> None:
        """Average exactly 2.5 -> B (boundary)."""
        # B(3) + B(3) + C(2) = 8/3 = 2.67 -> B
        # B(3) + C(2) + C(2) = 7/3 = 2.33 -> C
        grade, _ = calculate_capital_allocation_score(
            buyback_grade=CapitalAllocationGrade.B,
            dividend_grade=CapitalAllocationGrade.B,
            expansion_grade=CapitalAllocationGrade.C,
        )
        assert grade == CapitalAllocationGrade.B
