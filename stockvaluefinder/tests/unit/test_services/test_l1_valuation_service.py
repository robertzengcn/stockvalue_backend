"""L1 formula verification tests for valuation_service pure functions.

Verifies WACC (CAPM and full), FCF projection, present value, terminal value,
margin of safety, and valuation level classification against hand-verified
examples derived from Damodaran (2012) Investment Valuation.

All tests decorated with @pytest.mark.l1_formula for CI marker filtering.
"""

import pytest

from stockvaluefinder.models.enums import ValuationLevel
from stockvaluefinder.services.valuation_service import (
    calculate_margin_of_safety,
    calculate_present_value,
    calculate_terminal_value,
    calculate_wacc,
    determine_valuation_level,
    project_fcf,
)
from stockvaluefinder.validation.comparators import compare_within_tolerance
from stockvaluefinder.validation.schema import Tolerance

# Tolerance for WACC / valuation calculations
REL_TOL_001 = Tolerance(relative=0.01)
ABS_TOL_0001 = Tolerance(absolute=0.0001)


# ---------------------------------------------------------------------------
# WACC
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1WACC:
    """L1 tests for WACC calculation.

    Reference: Damodaran (2012) Investment Valuation.
    CAPM mode: WACC = Rf + beta * ERP
    Full mode: WACC = We * Ke + Wd * Kd * (1 - T)
    """

    def test_wacc_capm_example_1(self) -> None:
        """CAPM mode: Rf=0.03, beta=1.0, ERP=0.06 -> WACC = 0.09."""
        wacc = calculate_wacc(0.03, 1.0, 0.06)
        result = compare_within_tolerance(0.09, wacc, REL_TOL_001)
        assert result.passed, f"Expected 0.09, got {wacc}"

    def test_wacc_capm_example_2(self) -> None:
        """CAPM mode: Rf=0.025, beta=1.2, ERP=0.05 -> WACC = 0.085."""
        wacc = calculate_wacc(0.025, 1.2, 0.05)
        result = compare_within_tolerance(0.085, wacc, REL_TOL_001)
        assert result.passed, f"Expected 0.085, got {wacc}"

    def test_wacc_full_example(self) -> None:
        """Full WACC: Rf=0.03, beta=1.0, ERP=0.06, debt_weight=0.3, Kd=0.05, T=0.25.

        Ke = 0.03 + 1.0*0.06 = 0.09
        We = 0.7, Wd = 0.3
        WACC = 0.7*0.09 + 0.3*0.05*(1-0.25) = 0.063 + 0.01125 = 0.07425
        """
        wacc = calculate_wacc(
            0.03, 1.0, 0.06, debt_weight=0.3, cost_of_debt=0.05, tax_rate=0.25
        )
        result = compare_within_tolerance(0.07425, wacc, REL_TOL_001)
        assert result.passed, f"Expected 0.07425, got {wacc}"


# ---------------------------------------------------------------------------
# FCF projection
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1FCFProjection:
    """L1 tests for FCF projection.

    Formula: FCF_t = base * (1 + g)^t
    """

    def test_fcf_year_0(self) -> None:
        """year=0: base=100, g=0.05 -> 100.0 (no growth at year 0)."""
        fcf = project_fcf(100.0, 0.05, 0)
        assert fcf == pytest.approx(100.0, abs=1e-6)

    def test_fcf_year_5(self) -> None:
        """year=5: base=100, g=0.05 -> 100 * 1.05^5 = 127.62815625."""
        fcf = project_fcf(100.0, 0.05, 5)
        result = compare_within_tolerance(127.62815625, fcf, REL_TOL_001)
        assert result.passed, f"Expected 127.62815625, got {fcf}"

    def test_fcf_year_3_10pct(self) -> None:
        """year=3: base=50, g=0.10 -> 50 * 1.10^3 = 66.55."""
        fcf = project_fcf(50.0, 0.10, 3)
        result = compare_within_tolerance(66.55, fcf, REL_TOL_001)
        assert result.passed, f"Expected 66.55, got {fcf}"


# ---------------------------------------------------------------------------
# Present value
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1PresentValue:
    """L1 tests for present value of cash flow stream.

    Formula: PV = sum(FCF_t / (1 + WACC)^t)
    """

    def test_pv_three_equal_cashflows(self) -> None:
        """[100, 100, 100] at WACC=0.10 -> PV = 100/1.1 + 100/1.21 + 100/1.331 = 248.6852."""
        pv = calculate_present_value([100.0, 100.0, 100.0], 0.10)
        result = compare_within_tolerance(248.6852, pv, REL_TOL_001)
        assert result.passed, f"Expected 248.6852, got {pv}"

    def test_pv_single_cashflow(self) -> None:
        """[200] at WACC=0.08 -> PV = 200/1.08 = 185.1852."""
        pv = calculate_present_value([200.0], 0.08)
        result = compare_within_tolerance(185.1852, pv, REL_TOL_001)
        assert result.passed, f"Expected 185.1852, got {pv}"


# ---------------------------------------------------------------------------
# Terminal value
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1TerminalValue:
    """L1 tests for terminal value (Gordon Growth Model).

    Formula: TV = FCF * (1+g) / (WACC - g)
    """

    def test_terminal_value_example_1(self) -> None:
        """FCF=100, g=0.02, WACC=0.10 -> TV = 100*1.02/0.08 = 1275.0."""
        tv = calculate_terminal_value(100.0, 0.02, 0.10)
        result = compare_within_tolerance(1275.0, tv, REL_TOL_001)
        assert result.passed, f"Expected 1275.0, got {tv}"

    def test_terminal_value_example_2(self) -> None:
        """FCF=50, g=0.03, WACC=0.09 -> TV = 50*1.03/0.06 = 858.333..."""
        tv = calculate_terminal_value(50.0, 0.03, 0.09)
        result = compare_within_tolerance(858.333, tv, REL_TOL_001)
        assert result.passed, f"Expected 858.333, got {tv}"


# ---------------------------------------------------------------------------
# Margin of safety
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1MarginOfSafety:
    """L1 tests for margin of safety calculation.

    Formula: MoS = (IV - price) / price
    """

    def test_mos_positive(self) -> None:
        """IV=150, price=100 -> MoS = 50/100 = 0.5."""
        mos = calculate_margin_of_safety(150.0, 100.0)
        assert mos == pytest.approx(0.5, abs=1e-6)

    def test_mos_negative(self) -> None:
        """IV=80, price=100 -> MoS = -20/100 = -0.2."""
        mos = calculate_margin_of_safety(80.0, 100.0)
        assert mos == pytest.approx(-0.2, abs=1e-6)

    def test_mos_zero(self) -> None:
        """IV=100, price=100 -> MoS = 0.0."""
        mos = calculate_margin_of_safety(100.0, 100.0)
        assert mos == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Valuation level
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1ValuationLevel:
    """L1 tests for valuation level classification.

    Thresholds:
    - UNDERVALUED: MoS >= 0.30 (>= 30%)
    - FAIR_VALUE: -0.30 < MoS < 0.30
    - OVERVALUED: MoS <= -0.30 (<= -30%)

    Note: Source code uses `>= 0.30` for UNDERVALUED and `> -0.30` for FAIR_VALUE,
    meaning exactly -0.30 falls to OVERVALUED (else branch).
    """

    def test_level_undervalued_high(self) -> None:
        """MoS=0.50 -> UNDERVALUED (>= 30%)."""
        assert determine_valuation_level(0.50) == ValuationLevel.UNDERVALUED

    def test_level_undervalued_boundary(self) -> None:
        """MoS=0.30 -> UNDERVALUED (exactly at >= 0.30 boundary)."""
        assert determine_valuation_level(0.30) == ValuationLevel.UNDERVALUED

    def test_level_fair_value_just_below_30(self) -> None:
        """MoS=0.2999 -> FAIR_VALUE (below 30% threshold)."""
        assert determine_valuation_level(0.2999) == ValuationLevel.FAIR_VALUE

    def test_level_fair_value_zero(self) -> None:
        """MoS=0.0 -> FAIR_VALUE."""
        assert determine_valuation_level(0.0) == ValuationLevel.FAIR_VALUE

    def test_level_fair_value_just_above_neg30(self) -> None:
        """MoS=-0.2999 -> FAIR_VALUE (above -30% threshold, source uses > -0.30)."""
        assert determine_valuation_level(-0.2999) == ValuationLevel.FAIR_VALUE

    def test_level_overvalued_boundary(self) -> None:
        """MoS=-0.30 -> OVERVALUED (exactly at <= -0.30, falls to else branch)."""
        assert determine_valuation_level(-0.30) == ValuationLevel.OVERVALUED

    def test_level_overvalued_high(self) -> None:
        """MoS=-0.50 -> OVERVALUED."""
        assert determine_valuation_level(-0.50) == ValuationLevel.OVERVALUED
