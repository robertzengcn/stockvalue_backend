"""Unit tests for Alpha composite score pure functions.

Tests the normalization, composite calculation, and classification functions
in alpha_service.py. Each normalization function maps a component-specific
value to a 0-100 score per the design decisions D-01 through D-04.
"""

from stockvaluefinder.models.capital_allocation import CapitalAllocationGrade
from stockvaluefinder.models.enums import AlphaLevel
from stockvaluefinder.models.roic import MoatTrend
from stockvaluefinder.services.alpha_service import (
    calculate_alpha_score,
    classify_alpha_level,
    normalize_capex_score,
    normalize_moat_score,
    normalize_policy_score,
    normalize_roic_wacc_score,
)


class TestNormalizeRoicWaccScore:
    """Test ROIC-WACC spread normalization to 0-100 (D-02).

    Linear clamp: spread < -10% = 0, spread > +10% = 100,
    linear interpolation between. None spread returns 0.
    """

    def test_none_returns_zero(self) -> None:
        """None spread (negative invested capital) returns 0.0."""
        assert normalize_roic_wacc_score(None) == 0.0

    def test_negative_ten_percent_returns_zero(self) -> None:
        """Spread at -10% lower bound returns 0.0."""
        assert normalize_roic_wacc_score(-0.10) == 0.0

    def test_positive_ten_percent_returns_hundred(self) -> None:
        """Spread at +10% upper bound returns 100.0."""
        assert normalize_roic_wacc_score(0.10) == 100.0

    def test_zero_spread_returns_fifty(self) -> None:
        """Spread at 0% (midpoint) returns 50.0."""
        assert normalize_roic_wacc_score(0.0) == 50.0

    def test_below_negative_ten_clamped(self) -> None:
        """Spread below -10% is clamped to 0.0."""
        assert normalize_roic_wacc_score(-0.20) == 0.0

    def test_above_positive_ten_clamped(self) -> None:
        """Spread above +10% is clamped to 100.0."""
        assert normalize_roic_wacc_score(0.20) == 100.0

    def test_positive_five_returns_seventy_five(self) -> None:
        """Spread at +5% (midpoint between 0 and 100) returns 75.0."""
        assert normalize_roic_wacc_score(0.05) == 75.0

    def test_negative_five_returns_twenty_five(self) -> None:
        """Spread at -5% returns 25.0."""
        assert normalize_roic_wacc_score(-0.05) == 25.0

    def test_extreme_negative_clamped(self) -> None:
        """Extreme negative spread is clamped to 0.0."""
        assert normalize_roic_wacc_score(-1.0) == 0.0

    def test_extreme_positive_clamped(self) -> None:
        """Extreme positive spread is clamped to 100.0."""
        assert normalize_roic_wacc_score(1.0) == 100.0

    def test_small_positive_spread(self) -> None:
        """Small positive spread at +1% returns 55.0."""
        assert normalize_roic_wacc_score(0.01) == 55.0

    def test_small_negative_spread(self) -> None:
        """Small negative spread at -1% returns 45.0."""
        assert normalize_roic_wacc_score(-0.01) == 45.0


class TestNormalizeCapexScore:
    """Test Capital Allocation grade normalization (D-03).

    Grade mapping: A=100.0, B=75.0, C=50.0, D=25.0.
    """

    def test_grade_a_returns_hundred(self) -> None:
        """Grade A maps to 100.0."""
        assert normalize_capex_score(CapitalAllocationGrade.A) == 100.0

    def test_grade_b_returns_seventy_five(self) -> None:
        """Grade B maps to 75.0."""
        assert normalize_capex_score(CapitalAllocationGrade.B) == 75.0

    def test_grade_c_returns_fifty(self) -> None:
        """Grade C maps to 50.0."""
        assert normalize_capex_score(CapitalAllocationGrade.C) == 50.0

    def test_grade_d_returns_twenty_five(self) -> None:
        """Grade D maps to 25.0."""
        assert normalize_capex_score(CapitalAllocationGrade.D) == 25.0


class TestNormalizePolicyScore:
    """Test Policy resonance score normalization (pass-through with clamp).

    Policy score is already 0-100 from policy_service. Pass-through
    with safety clamp at boundaries.
    """

    def test_zero_returns_zero(self) -> None:
        """Score 0.0 passes through."""
        assert normalize_policy_score(0.0) == 0.0

    def test_hundred_returns_hundred(self) -> None:
        """Score 100.0 passes through."""
        assert normalize_policy_score(100.0) == 100.0

    def test_fifty_returns_fifty(self) -> None:
        """Score 50.0 passes through."""
        assert normalize_policy_score(50.0) == 50.0

    def test_negative_clamped_to_zero(self) -> None:
        """Negative score is clamped to 0.0."""
        assert normalize_policy_score(-5.0) == 0.0

    def test_above_hundred_clamped(self) -> None:
        """Score above 100 is clamped to 100.0."""
        assert normalize_policy_score(150.0) == 100.0

    def test_seventy_five_passes_through(self) -> None:
        """Score 75.0 passes through."""
        assert normalize_policy_score(75.0) == 75.0


class TestNormalizeMoatScore:
    """Test Moat trend normalization (D-04).

    COMPETITIVE_ADVANTAGE=100.0, STABLE=50.0,
    DETERIORATING=0.0, INSUFFICIENT_DATA=0.0, None=0.0.
    """

    def test_competitive_advantage_returns_hundred(self) -> None:
        """COMPETITIVE_ADVANTAGE maps to 100.0."""
        assert normalize_moat_score(MoatTrend.COMPETITIVE_ADVANTAGE) == 100.0

    def test_stable_returns_fifty(self) -> None:
        """STABLE maps to 50.0."""
        assert normalize_moat_score(MoatTrend.STABLE) == 50.0

    def test_deteriorating_returns_zero(self) -> None:
        """DETERIORATING maps to 0.0."""
        assert normalize_moat_score(MoatTrend.DETERIORATING) == 0.0

    def test_insufficient_data_returns_zero(self) -> None:
        """INSUFFICIENT_DATA maps to 0.0."""
        assert normalize_moat_score(MoatTrend.INSUFFICIENT_DATA) == 0.0

    def test_none_returns_zero(self) -> None:
        """None moat trend maps to 0.0."""
        assert normalize_moat_score(None) == 0.0


class TestCalculateAlphaScore:
    """Test weighted Alpha composite score calculation.

    Fixed weights: ROIC-WACC=0.40, CapEx=0.30, Policy=0.20, Moat=0.10.
    Weighted sum of normalized component scores, rounded to 2 decimal places.
    """

    def test_all_hundreds_returns_hundred(self) -> None:
        """All component scores at 100 produce composite 100.0."""
        result = calculate_alpha_score(100.0, 100.0, 100.0, 100.0)
        assert result == 100.0

    def test_all_zeros_returns_zero(self) -> None:
        """All component scores at 0 produce composite 0.0."""
        result = calculate_alpha_score(0.0, 0.0, 0.0, 0.0)
        assert result == 0.0

    def test_mixed_scores_returns_weighted_sum(self) -> None:
        """Mixed scores: roic=100, capex=75, policy=50, moat=0 -> 72.5.

        Calculation: 100*0.40 + 75*0.30 + 50*0.20 + 0*0.10
                   = 40.0   + 22.5    + 10.0   + 0.0
                   = 72.5
        """
        result = calculate_alpha_score(100.0, 75.0, 50.0, 0.0)
        assert result == 72.5

    def test_roic_weight_contribution(self) -> None:
        """ROIC-WACC component contributes 40% weight."""
        result = calculate_alpha_score(100.0, 0.0, 0.0, 0.0)
        assert result == 40.0

    def test_capex_weight_contribution(self) -> None:
        """CapEx component contributes 30% weight."""
        result = calculate_alpha_score(0.0, 100.0, 0.0, 0.0)
        assert result == 30.0

    def test_policy_weight_contribution(self) -> None:
        """Policy component contributes 20% weight."""
        result = calculate_alpha_score(0.0, 0.0, 100.0, 0.0)
        assert result == 20.0

    def test_moat_weight_contribution(self) -> None:
        """Moat component contributes 10% weight."""
        result = calculate_alpha_score(0.0, 0.0, 0.0, 100.0)
        assert result == 10.0

    def test_custom_weights(self) -> None:
        """Custom weights override defaults."""
        result = calculate_alpha_score(
            100.0, 0.0, 0.0, 0.0, weights=(0.50, 0.20, 0.20, 0.10)
        )
        assert result == 50.0

    def test_result_rounded_to_two_decimals(self) -> None:
        """Result is rounded to 2 decimal places."""
        result = calculate_alpha_score(33.33, 66.67, 99.99, 11.11)
        # 33.33*0.40 + 66.67*0.30 + 99.99*0.20 + 11.11*0.10
        # = 13.332 + 20.001 + 19.998 + 1.111
        # = 54.442
        assert result == round(result, 2)


class TestClassifyAlphaLevel:
    """Test Alpha score classification into tiers.

    EXCELLENT >= 80, GOOD >= 60, FAIR >= 40, WEAK >= 20, POOR < 20.
    """

    def test_hundred_is_excellent(self) -> None:
        """Score 100 classifies as EXCELLENT."""
        assert classify_alpha_level(100.0) == AlphaLevel.EXCELLENT

    def test_eighty_is_excellent(self) -> None:
        """Score 80 (boundary) classifies as EXCELLENT."""
        assert classify_alpha_level(80.0) == AlphaLevel.EXCELLENT

    def test_seventy_nine_is_good(self) -> None:
        """Score 79 (just below EXCELLENT) classifies as GOOD."""
        assert classify_alpha_level(79.0) == AlphaLevel.GOOD

    def test_sixty_is_good(self) -> None:
        """Score 60 (boundary) classifies as GOOD."""
        assert classify_alpha_level(60.0) == AlphaLevel.GOOD

    def test_fifty_nine_is_fair(self) -> None:
        """Score 59 classifies as FAIR."""
        assert classify_alpha_level(59.0) == AlphaLevel.FAIR

    def test_forty_is_fair(self) -> None:
        """Score 40 (boundary) classifies as FAIR."""
        assert classify_alpha_level(40.0) == AlphaLevel.FAIR

    def test_thirty_nine_is_weak(self) -> None:
        """Score 39 classifies as WEAK."""
        assert classify_alpha_level(39.0) == AlphaLevel.WEAK

    def test_twenty_is_weak(self) -> None:
        """Score 20 (boundary) classifies as WEAK."""
        assert classify_alpha_level(20.0) == AlphaLevel.WEAK

    def test_nineteen_is_poor(self) -> None:
        """Score 19 classifies as POOR."""
        assert classify_alpha_level(19.0) == AlphaLevel.POOR

    def test_zero_is_poor(self) -> None:
        """Score 0 classifies as POOR."""
        assert classify_alpha_level(0.0) == AlphaLevel.POOR
