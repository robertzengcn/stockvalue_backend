"""Unit tests for DCF valuation service functions."""

import pytest
from hypothesis import given, strategies as st

from stockvaluefinder.services.valuation_service import (
    calculate_margin_of_safety,
    calculate_present_value,
    calculate_terminal_value,
    calculate_wacc,
    project_fcf,
)


class TestWACCCalculation:
    """Test WACC (Weighted Average Cost of Capital) calculation."""

    @pytest.mark.parametrize(
        ("risk_free_rate", "beta", "market_risk_premium", "expected_wacc"),
        [
            (0.03, 1.0, 0.06, 0.09),  # 3% + 1.0 * 6% = 9%
            (0.025, 1.2, 0.05, 0.085),  # 2.5% + 1.2 * 5% = 8.5%
            (0.04, 0.8, 0.07, 0.096),  # 4% + 0.8 * 7% = 9.6%
            (0.02, 1.5, 0.08, 0.14),  # 2% + 1.5 * 8% = 14%
        ],
    )
    def test_wacc_calculation(
        self,
        risk_free_rate: float,
        beta: float,
        market_risk_premium: float,
        expected_wacc: float,
    ) -> None:
        """Test WACC formula: WACC = Rf + β × ERP."""
        result = calculate_wacc(risk_free_rate, beta, market_risk_premium)
        assert result == pytest.approx(expected_wacc, rel=1e-3)

    def test_wacc_with_zero_beta(self) -> None:
        """Test WACC with zero beta (risk-free only)."""
        result = calculate_wacc(0.03, 0.0, 0.06)
        assert result == 0.03

    def test_wacc_with_negative_risk_free_rate(self) -> None:
        """Test WACC with negative risk-free rate (edge case)."""
        result = calculate_wacc(-0.01, 1.0, 0.06)
        assert result == pytest.approx(0.05, rel=1e-3)


class TestFCFProjection:
    """Test Free Cash Flow projection."""

    @pytest.mark.parametrize(
        ("base_fcf", "growth_rate", "year", "expected_fcf"),
        [
            (100.0, 0.05, 0, 100.0),  # Year 0: no growth
            (100.0, 0.05, 1, 105.0),  # Year 1: 5% growth
            (100.0, 0.05, 5, 127.63),  # Year 5: compound growth
            (100.0, 0.10, 3, 133.1),  # Year 3: 10% growth
            (100.0, -0.05, 2, 90.25),  # Year 2: -5% decline
        ],
    )
    def test_fcf_projection(
        self, base_fcf: float, growth_rate: float, year: int, expected_fcf: float
    ) -> None:
        """Test FCF projection formula: FCF_t = base_FCF × (1 + g)^t."""
        result = project_fcf(base_fcf, growth_rate, year)
        assert result == pytest.approx(expected_fcf, rel=1e-2)

    @given(
        base_fcf=st.floats(min_value=0, max_value=1e6),
        growth_rate=st.floats(min_value=-0.5, max_value=0.5),
        year=st.integers(min_value=0, max_value=20),
    )
    def test_fcf_formula_accuracy(
        self, base_fcf: float, growth_rate: float, year: int
    ) -> None:
        """Property-based test: verify FCF projection formula accuracy."""
        result = project_fcf(base_fcf, growth_rate, year)

        # Formula: FCF_t = base_FCF × (1 + g)^t
        expected = base_fcf * ((1 + growth_rate) ** year)

        assert isinstance(result, float)
        assert result == pytest.approx(expected, rel=1e-6)


class TestPresentValueCalculation:
    """Test present value of future cash flows."""

    @pytest.mark.parametrize(
        ("fcf_stream", "wacc", "expected_pv"),
        [
            ([100.0, 100.0, 100.0], 0.10, 248.69),  # 3 years of 100 at 10%
            ([50.0, 55.0, 60.0], 0.08, 141.08),  # Growing FCFs at 8%
            ([100.0], 0.05, 95.24),  # Single year at 5%
            ([], 0.10, 0.0),  # Empty stream
        ],
    )
    def test_pv_calculation(
        self, fcf_stream: list[float], wacc: float, expected_pv: float
    ) -> None:
        """Test PV formula: PV = Σ FCF_t / (1 + WACC)^t."""
        result = calculate_present_value(fcf_stream, wacc)
        assert result == pytest.approx(expected_pv, rel=1e-2)

    def test_pv_with_zero_wacc(self) -> None:
        """Test PV with zero discount rate (no discounting)."""
        # When wacc=0, (1+0)^t = 1, so PV = sum of all FCFs
        result = calculate_present_value([100.0, 100.0], 0.0)
        assert result == 200.0  # 100 + 100 with no discounting


class TestTerminalValueCalculation:
    """Test Gordon Growth Model for terminal value."""

    @pytest.mark.parametrize(
        ("final_fcf", "growth_rate", "wacc", "expected_tv"),
        [
            (100.0, 0.02, 0.10, 1275.0),  # TV = 100 × 1.02 / (0.10 - 0.02) = 1275
            (150.0, 0.03, 0.09, 2575.0),  # TV = 150 × 1.03 / (0.09 - 0.03) = 2575
            (
                200.0,
                0.025,
                0.08,
                3727.27,
            ),  # TV = 200 × 1.025 / (0.08 - 0.025) = 3727.27
        ],
    )
    def test_terminal_value(
        self, final_fcf: float, growth_rate: float, wacc: float, expected_tv: float
    ) -> None:
        """Test Gordon Growth Model: TV = FCF_final × (1 + g) / (WACC - g)."""
        result = calculate_terminal_value(final_fcf, growth_rate, wacc)
        assert result == pytest.approx(expected_tv, rel=1e-2)

    def test_terminal_value_with_equal_rates(self) -> None:
        """Test terminal value when growth_rate = WACC (undefined)."""
        with pytest.raises(ZeroDivisionError):
            calculate_terminal_value(100.0, 0.05, 0.05)

    def test_terminal_value_with_negative_growth(self) -> None:
        """Test terminal value with negative growth (valid for declining companies)."""
        result = calculate_terminal_value(100.0, -0.01, 0.10)
        # TV = 100 × 0.99 / (0.10 - (-0.01)) = 99 / 0.11 = 900
        assert result == pytest.approx(900.0, rel=1e-2)


class TestMarginOfSafety:
    """Test margin of safety calculation."""

    @pytest.mark.parametrize(
        ("intrinsic_value", "current_price", "expected_mos"),
        [
            (150.0, 100.0, 0.50),  # 50% undervalued
            (120.0, 100.0, 0.20),  # 20% undervalued
            (100.0, 100.0, 0.00),  # Fair value
            (80.0, 100.0, -0.20),  # 20% overvalued
            (50.0, 100.0, -0.50),  # 50% overvalued
        ],
    )
    def test_margin_of_safety(
        self, intrinsic_value: float, current_price: float, expected_mos: float
    ) -> None:
        """Test MoS formula: MoS = (intrinsic_value - price) / price."""
        result = calculate_margin_of_safety(intrinsic_value, current_price)
        assert result == pytest.approx(expected_mos, rel=1e-3)

    def test_margin_of_safety_with_zero_price(self) -> None:
        """Test margin of safety with zero price (undefined)."""
        with pytest.raises(ZeroDivisionError):
            calculate_margin_of_safety(100.0, 0.0)

    @given(
        intrinsic_value=st.floats(min_value=0, max_value=1e6),
        current_price=st.floats(min_value=0.01, max_value=1e6),
    )
    def test_mos_formula_accuracy(
        self, intrinsic_value: float, current_price: float
    ) -> None:
        """Property-based test: verify MoS formula accuracy."""
        result = calculate_margin_of_safety(intrinsic_value, current_price)

        # Formula: MoS = (intrinsic_value - price) / price
        expected = (intrinsic_value - current_price) / current_price

        assert isinstance(result, float)
        assert result == pytest.approx(expected, rel=1e-6)
