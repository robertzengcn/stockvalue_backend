"""Unit tests for yield gap service functions."""

from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, strategies as st

from stockvaluefinder.models.enums import Market, YieldRecommendation
from stockvaluefinder.services.yield_service import (
    YieldAnalyzer,
    analyze_yield_gap,
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
    def test_net_dividend_yield_calculation(
        self, gross_yield: float, market: Market, expected_net: float
    ) -> None:
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
        assert result == pytest.approx(0.16, rel=1e-3)  # 20% - 20% tax


class TestYieldGapCalculation:
    """Test yield gap calculation."""

    @pytest.mark.parametrize(
        ("net_yield", "bond_rate", "deposit_rate", "expected_gap"),
        [
            (0.05, 0.03, 0.025, 0.02),  # gap = 5% - max(3%, 2.5%) = 2%
            (0.04, 0.03, 0.04, 0.00),  # gap = 4% - max(3%, 4%) = 0%
            (0.02, 0.03, 0.025, -0.01),  # gap = 2% - max(3%, 2.5%) = -1%
            (0.00, 0.03, 0.025, -0.03),  # gap = 0% - max(3%, 2.5%) = -3%
        ],
    )
    def test_yield_gap_calculation(
        self,
        net_yield: float,
        bond_rate: float,
        deposit_rate: float,
        expected_gap: float,
    ) -> None:
        """Test yield gap formula: yield_gap = net_yield - max(bond_rate, deposit_rate)."""
        result = calculate_yield_gap(net_yield, bond_rate, deposit_rate)
        assert result == pytest.approx(expected_gap, rel=1e-3)

    @given(
        net_yield=st.floats(min_value=-0.1, max_value=0.3),
        bond_rate=st.floats(min_value=0.0, max_value=0.2),
        deposit_rate=st.floats(min_value=0.0, max_value=0.2),
    )
    def test_yield_gap_formula_accuracy(
        self, net_yield: float, bond_rate: float, deposit_rate: float
    ) -> None:
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
    def test_yield_recommendation_determination(
        self, yield_gap: float, expected_recommendation: YieldRecommendation
    ) -> None:
        """Test recommendation logic based on yield gap."""
        result = determine_yield_recommendation(yield_gap)
        assert result == expected_recommendation

    def test_boundary_conditions(self) -> None:
        """Test edge cases at recommendation boundaries."""
        # Exactly 2% = NEUTRAL (boundary is > 2% for ATTRACTIVE)
        assert determine_yield_recommendation(0.02) == YieldRecommendation.NEUTRAL

        # Exactly -1% = NEUTRAL
        assert determine_yield_recommendation(-0.01) == YieldRecommendation.NEUTRAL

        # Slightly below -1% = UNATTRACTIVE
        assert (
            determine_yield_recommendation(-0.0101) == YieldRecommendation.UNATTRACTIVE
        )

        # Slightly above 2% = ATTRACTIVE
        assert determine_yield_recommendation(0.0201) == YieldRecommendation.ATTRACTIVE


class TestAnalyzeYieldGap:
    """Test the yield gap orchestrator function."""

    def test_full_analysis_a_share(self) -> None:
        """Full yield gap analysis for A-share with all fields populated."""
        analysis_id = uuid4()

        result = analyze_yield_gap(
            ticker="600519.SH",
            cost_basis=Decimal("1800"),
            current_price=Decimal("1850"),
            gross_dividend_yield=0.022,
            risk_free_bond_rate=0.028,
            risk_free_deposit_rate=0.025,
            market=Market.A_SHARE,
            analysis_id=analysis_id,
        )

        # A-share: no tax, net_yield == gross_yield
        assert result.net_dividend_yield == pytest.approx(0.022, rel=1e-3)

        # yield_gap = 0.022 - max(0.028, 0.025) = 0.022 - 0.028 = -0.006
        assert result.yield_gap == pytest.approx(-0.006, rel=1e-3)

        # -0.006 is between -0.01 and 0.02 -> NEUTRAL
        assert result.recommendation == YieldRecommendation.NEUTRAL

        # Verify all fields are populated
        assert result.ticker == "600519.SH"
        assert result.cost_basis == Decimal("1800")
        assert result.current_price == Decimal("1850")
        assert result.gross_dividend_yield == pytest.approx(0.022, rel=1e-3)
        assert result.risk_free_bond_rate == pytest.approx(0.028, rel=1e-3)
        assert result.risk_free_deposit_rate == pytest.approx(0.025, rel=1e-3)
        assert result.market == Market.A_SHARE
        assert result.analysis_id == analysis_id

    def test_full_analysis_hk_share(self) -> None:
        """Full yield gap analysis for HK share with 20% tax applied."""
        analysis_id = uuid4()

        result = analyze_yield_gap(
            ticker="0700.HK",
            cost_basis=Decimal("300"),
            current_price=Decimal("350"),
            gross_dividend_yield=0.022,
            risk_free_bond_rate=0.028,
            risk_free_deposit_rate=0.025,
            market=Market.HK_SHARE,
            analysis_id=analysis_id,
        )

        # HK: 20% tax, net_yield = 0.022 * 0.80 = 0.0176
        assert result.net_dividend_yield == pytest.approx(0.0176, rel=1e-3)

        # yield_gap = 0.0176 - max(0.028, 0.025) = 0.0176 - 0.028 = -0.0104
        assert result.yield_gap == pytest.approx(-0.0104, rel=1e-3)

        # -0.0104 < -0.01 -> UNATTRACTIVE
        assert result.recommendation == YieldRecommendation.UNATTRACTIVE

    def test_analysis_attractive_recommendation(self) -> None:
        """High dividend yield produces ATTRACTIVE recommendation."""
        analysis_id = uuid4()

        result = analyze_yield_gap(
            ticker="600519.SH",
            cost_basis=Decimal("1800"),
            current_price=Decimal("1850"),
            gross_dividend_yield=0.06,
            risk_free_bond_rate=0.03,
            risk_free_deposit_rate=0.025,
            market=Market.A_SHARE,
            analysis_id=analysis_id,
        )

        # A-share: no tax, net_yield = 0.06
        # yield_gap = 0.06 - max(0.03, 0.025) = 0.06 - 0.03 = 0.03 > 0.02 -> ATTRACTIVE
        assert result.net_dividend_yield == pytest.approx(0.06, rel=1e-3)
        assert result.yield_gap == pytest.approx(0.03, rel=1e-3)
        assert result.recommendation == YieldRecommendation.ATTRACTIVE

    def test_analysis_unattractive_recommendation(self) -> None:
        """Low dividend yield vs high risk-free rates produces UNATTRACTIVE."""
        analysis_id = uuid4()

        result = analyze_yield_gap(
            ticker="600519.SH",
            cost_basis=Decimal("1800"),
            current_price=Decimal("1850"),
            gross_dividend_yield=0.01,
            risk_free_bond_rate=0.04,
            risk_free_deposit_rate=0.035,
            market=Market.A_SHARE,
            analysis_id=analysis_id,
        )

        # A-share: no tax, net_yield = 0.01
        # yield_gap = 0.01 - max(0.04, 0.035) = 0.01 - 0.04 = -0.03 < -0.01 -> UNATTRACTIVE
        assert result.net_dividend_yield == pytest.approx(0.01, rel=1e-3)
        assert result.yield_gap == pytest.approx(-0.03, rel=1e-3)
        assert result.recommendation == YieldRecommendation.UNATTRACTIVE

    def test_analysis_populates_all_fields(self) -> None:
        """Verify all YieldGap fields are populated after analysis."""
        analysis_id = uuid4()

        result = analyze_yield_gap(
            ticker="600519.SH",
            cost_basis=Decimal("1800"),
            current_price=Decimal("1850"),
            gross_dividend_yield=0.03,
            risk_free_bond_rate=0.028,
            risk_free_deposit_rate=0.025,
            market=Market.A_SHARE,
            analysis_id=analysis_id,
        )

        # Verify every field on the YieldGap model is populated
        assert result.ticker == "600519.SH"
        assert result.cost_basis == Decimal("1800")
        assert result.current_price == Decimal("1850")
        assert isinstance(result.gross_dividend_yield, float)
        assert isinstance(result.net_dividend_yield, float)
        assert isinstance(result.risk_free_bond_rate, float)
        assert isinstance(result.risk_free_deposit_rate, float)
        assert isinstance(result.yield_gap, float)
        assert isinstance(result.recommendation, YieldRecommendation)
        assert result.market == Market.A_SHARE
        assert result.analysis_id == analysis_id
        assert result.calculated_at is not None


class TestYieldAnalyzer:
    """Test YieldAnalyzer service class delegates to analyze_yield_gap."""

    def test_analyzer_delegates_to_function(self) -> None:
        """YieldAnalyzer.analyze returns same result as analyze_yield_gap."""
        analysis_id = uuid4()
        kwargs = {
            "ticker": "600519.SH",
            "cost_basis": Decimal("1800"),
            "current_price": Decimal("1850"),
            "gross_dividend_yield": 0.022,
            "risk_free_bond_rate": 0.028,
            "risk_free_deposit_rate": 0.025,
            "market": Market.A_SHARE,
            "analysis_id": analysis_id,
        }

        function_result = analyze_yield_gap(**kwargs)

        analyzer = YieldAnalyzer()
        service_result = analyzer.analyze(**kwargs)

        # Results should be identical
        assert service_result.net_dividend_yield == pytest.approx(
            function_result.net_dividend_yield, rel=1e-6
        )
        assert service_result.yield_gap == pytest.approx(
            function_result.yield_gap, rel=1e-6
        )
        assert service_result.recommendation == function_result.recommendation
        assert service_result.ticker == function_result.ticker
        assert service_result.market == function_result.market
