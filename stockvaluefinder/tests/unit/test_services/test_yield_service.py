"""Unit tests for yield gap service functions."""


import pytest
from hypothesis import given, strategies as st

from stockvaluefinder.models.enums import Market, YieldRecommendation
from stockvaluefinder.services.yield_service import (
    calculate_net_dividend_yield,
    calculate_yield_gap,
    determine_yield_recommendation,
)


class TestNetDividendYield:
    """Test net dividend yield calculation."""

    @pytest.mark.parametrize(
        ("gross_yield", "market", "expected_net"),
        [
            (0.05, Market.A_SHARE, 0.05),  # A-share: 0% tax
            (0.05, Market.HK_SHARE, 0.04),  # HK: 20% tax
            (0.03, Market.A_SHARE, 0.03),  # A-share: 0% tax
            (0.03, Market.HK_SHARE, 0.024),  # HK: 20% tax
            (0.00, Market.A_SHARE, 0.00),  # Zero yield
            (0.00, Market.HK_SHARE, 0.00),  # Zero yield
        ],
    )
    def test_net_dividend_yield_calculation(self, gross_yield: float, market: Market, expected_net: float) -> None:
        """Test net dividend yield calculation with different markets."""
        result = calculate_net_dividend_yield(gross_yield, market)
        assert result == pytest.approx(expected_net, rel=1e-3)

    def test_negative_gross_yield(self) -> None:
        """Test negative gross yield (edge case)."""
        result = calculate_net_dividend_yield(-0.01, Market.A_SHARE)
        assert result == -0.01

    def test_very_high_yield(self) -> None:
        """Test very high dividend yield."""
        result = calculate_net_dividend_yield(0.20, Market.HK_SHARE)
        assert result == 0.16  # 20% - 20% tax


class TestYieldGapCalculation:
    """Test yield gap calculation."""

    @pytest.mark.parametrize(
        ("net_yield", "bond_rate", "deposit_rate", "expected_gap"),
        [
            (0.05, 0.03, 0.025, 0.025),  # gap = 5% - max(3%, 2.5%) = 2.5%
            (0.04, 0.03, 0.04, 0.00),  # gap = 4% - max(3%, 4%) = 0%
            (0.02, 0.03, 0.025, -0.01),  # gap = 2% - max(3%, 2.5%) = -1%
            (0.00, 0.03, 0.025, -0.03),  # gap = 0% - max(3%, 2.5%) = -3%
        ],
    )
    def test_yield_gap_calculation(self, net_yield: float, bond_rate: float, deposit_rate: float, expected_gap: float) -> None:
        """Test yield gap formula: yield_gap = net_yield - max(bond_rate, deposit_rate)."""
        result = calculate_yield_gap(net_yield, bond_rate, deposit_rate)
        assert result == pytest.approx(expected_gap, rel=1e-3)

    @given(
        net_yield=st.floats(min_value=-0.1, max_value=0.3),
        bond_rate=st.floats(min_value=0.0, max_value=0.2),
        deposit_rate=st.floats(min_value=0.0, max_value=0.2),
    )
    def test_yield_gap_formula_accuracy(self, net_yield: float, bond_rate: float, deposit_rate: float) -> None:
        """Property-based test: verify yield gap formula accuracy with Hypothesis."""
        result = calculate_yield_gap(net_yield, bond_rate, deposit_rate)

        # Formula: yield_gap = net_dividend_yield - max(rf_bond, rf_deposit)
        expected = net_yield - max(bond_rate, deposit_rate)

        assert isinstance(result, float)
        assert result == pytest.approx(expected, abs=1e-6)
        # Check for NaN (should never happen with valid inputs)
        assert result == result  # NaN check: NaN != NaN


class TestYieldRecommendation:
    """Test yield recommendation determination."""

    @pytest.mark.parametrize(
        ("yield_gap", "expected_recommendation"),
        [
            (0.025, YieldRecommendation.ATTRACTIVE),  # gap > 2%
            (0.05, YieldRecommendation.ATTRACTIVE),  # gap > 2%
            (0.01, YieldRecommendation.NEUTRAL),  # -1% < gap <= 2%
            (0.00, YieldRecommendation.NEUTRAL),  # -1% < gap <= 2%
            (-0.005, YieldRecommendation.NEUTRAL),  # -1% < gap <= 2%
            (-0.01, YieldRecommendation.NEUTRAL),  # boundary
            (-0.02, YieldRecommendation.UNATTRACTIVE),  # gap < -1%
            (-0.05, YieldRecommendation.UNATTRACTIVE),  # gap < -1%
        ],
    )
    def test_yield_recommendation_determination(self, yield_gap: float, expected_recommendation: YieldRecommendation) -> None:
        """Test recommendation logic based on yield gap."""
        result = determine_yield_recommendation(yield_gap)
        assert result == expected_recommendation

    def test_boundary_conditions(self) -> None:
        """Test edge cases at recommendation boundaries."""
        # Exactly 2% = ATTRACTIVE
        assert determine_yield_recommendation(0.02) == YieldRecommendation.ATTRACTIVE

        # Exactly -1% = NEUTRAL
        assert determine_yield_recommendation(-0.01) == YieldRecommendation.NEUTRAL

        # Slightly below -1% = UNATTRACTIVE
        assert determine_yield_recommendation(-0.0101) == YieldRecommendation.UNATTRACTIVE

        # Slightly above 2% = ATTRACTIVE
        assert determine_yield_recommendation(0.0201) == YieldRecommendation.ATTRACTIVE
