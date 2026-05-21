"""L1 formula verification tests for roic_service pure functions.

Verifies NOPAT (both non-financial and financial sector formulas), invested
capital, ROIC, ROIC-WACC spread, and moat trend detection against hand-verified
examples derived from Damodaran (2012) Investment Valuation.

All tests decorated with @pytest.mark.l1_formula for CI marker filtering.
"""

import pytest

from stockvaluefinder.models.roic import MoatTrend, SpreadClassification
from stockvaluefinder.services.roic_service import (
    analyze_roic_trend,
    calculate_invested_capital,
    calculate_nopat,
    calculate_roic,
    calculate_roic_wacc_spread,
)
from stockvaluefinder.validation.comparators import compare_within_tolerance
from stockvaluefinder.validation.schema import Tolerance

# Tolerance for NOPAT / ROIC calculations (relative 2%)
REL_TOL_002 = Tolerance(relative=0.02)


# ---------------------------------------------------------------------------
# NOPAT non-financial formula
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1NOPATNonFinancial:
    """L1 tests for NOPAT non-financial formula.

    Reference: Damodaran (2012) Investment Valuation.
    Formula: NOPAT = (Total Profit + Finance Expense) * (1 - Tax Rate)
    Tax Rate = Income Tax / Total Profit
    """

    def test_nopat_non_financial_example_1(self) -> None:
        """Example 1: TOTAL_PROFIT=1000, FINANCE_EXPENSE=100, INCOME_TAX=250.

        tax_rate = 250/1000 = 0.25
        NOPAT = (1000+100) * (1-0.25) = 1100 * 0.75 = 825.0
        """
        nopat, audit = calculate_nopat(
            {"TOTAL_PROFIT": 1000, "FINANCE_EXPENSE": 100, "INCOME_TAX": 250},
            is_financial=False,
        )
        assert nopat is not None
        result = compare_within_tolerance(825.0, nopat, REL_TOL_002)
        assert result.passed, (
            f"NOPAT example 1: expected 825.0, got {nopat}, delta={result.delta}"
        )
        assert audit["tax_rate"] == pytest.approx(0.25, abs=1e-6)

    def test_nopat_non_financial_example_2(self) -> None:
        """Example 2: TOTAL_PROFIT=5000, FINANCE_EXPENSE=200, INCOME_TAX=1250.

        tax_rate = 1250/5000 = 0.25
        NOPAT = (5000+200) * (1-0.25) = 5200 * 0.75 = 3900.0
        """
        nopat, audit = calculate_nopat(
            {"TOTAL_PROFIT": 5000, "FINANCE_EXPENSE": 200, "INCOME_TAX": 1250},
            is_financial=False,
        )
        assert nopat is not None
        result = compare_within_tolerance(3900.0, nopat, REL_TOL_002)
        assert result.passed, (
            f"NOPAT example 2: expected 3900.0, got {nopat}, delta={result.delta}"
        )
        assert audit["tax_rate"] == pytest.approx(0.25, abs=1e-6)

    def test_nopat_non_financial_example_3(self) -> None:
        """Example 3: TOTAL_PROFIT=2000, FINANCE_EXPENSE=0, INCOME_TAX=400.

        tax_rate = 400/2000 = 0.20
        NOPAT = (2000+0) * (1-0.20) = 2000 * 0.80 = 1600.0
        """
        nopat, audit = calculate_nopat(
            {"TOTAL_PROFIT": 2000, "FINANCE_EXPENSE": 0, "INCOME_TAX": 400},
            is_financial=False,
        )
        assert nopat is not None
        result = compare_within_tolerance(1600.0, nopat, REL_TOL_002)
        assert result.passed, (
            f"NOPAT example 3: expected 1600.0, got {nopat}, delta={result.delta}"
        )
        assert audit["tax_rate"] == pytest.approx(0.20, abs=1e-6)


# ---------------------------------------------------------------------------
# NOPAT financial-sector formula
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1NOPATFinancial:
    """L1 tests for NOPAT financial-sector formula.

    Reference: Damodaran (2012) Investment Valuation.
    Formula: NOPAT = Operating Profit * (1 - Tax Rate)
    Tax Rate = Income Tax / Total Profit
    """

    def test_nopat_financial_example_1(self) -> None:
        """Example 1: OPERATE_PROFIT=800, INCOME_TAX=200, TOTAL_PROFIT=1000.

        tax_rate = 200/1000 = 0.20
        NOPAT = 800 * (1-0.20) = 800 * 0.80 = 640.0
        """
        nopat, audit = calculate_nopat(
            {"OPERATE_PROFIT": 800, "INCOME_TAX": 200, "TOTAL_PROFIT": 1000},
            is_financial=True,
        )
        assert nopat is not None
        result = compare_within_tolerance(640.0, nopat, REL_TOL_002)
        assert result.passed, (
            f"NOPAT financial example 1: expected 640.0, got {nopat}, delta={result.delta}"
        )
        assert audit["tax_rate"] == pytest.approx(0.20, abs=1e-6)

    def test_nopat_financial_example_2(self) -> None:
        """Example 2: OPERATE_PROFIT=3000, INCOME_TAX=750, TOTAL_PROFIT=3000.

        tax_rate = 750/3000 = 0.25
        NOPAT = 3000 * (1-0.25) = 3000 * 0.75 = 2250.0
        """
        nopat, audit = calculate_nopat(
            {"OPERATE_PROFIT": 3000, "INCOME_TAX": 750, "TOTAL_PROFIT": 3000},
            is_financial=True,
        )
        assert nopat is not None
        result = compare_within_tolerance(2250.0, nopat, REL_TOL_002)
        assert result.passed, (
            f"NOPAT financial example 2: expected 2250.0, got {nopat}, delta={result.delta}"
        )
        assert audit["tax_rate"] == pytest.approx(0.25, abs=1e-6)

    def test_nopat_financial_example_3(self) -> None:
        """Example 3: OPERATE_PROFIT=1500, INCOME_TAX=300, TOTAL_PROFIT=1500.

        tax_rate = 300/1500 = 0.20
        NOPAT = 1500 * (1-0.20) = 1500 * 0.80 = 1200.0
        """
        nopat, audit = calculate_nopat(
            {"OPERATE_PROFIT": 1500, "INCOME_TAX": 300, "TOTAL_PROFIT": 1500},
            is_financial=True,
        )
        assert nopat is not None
        result = compare_within_tolerance(1200.0, nopat, REL_TOL_002)
        assert result.passed, (
            f"NOPAT financial example 3: expected 1200.0, got {nopat}, delta={result.delta}"
        )
        assert audit["tax_rate"] == pytest.approx(0.20, abs=1e-6)


# ---------------------------------------------------------------------------
# Invested capital
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1InvestedCapital:
    """L1 tests for invested capital calculation.

    Reference: Damodaran (2012) Investment Valuation.
    Formula: IC = Equity + Short Debt + Long Debt + Bonds - Treasury Stock
    """

    def test_invested_capital_example_1(self) -> None:
        """Example 1: Equity=5000, ShortDebt=1000, LongDebt=2000, Bonds=500, Treasury=200.

        IC = 5000+1000+2000+500-200 = 8300.
        """
        ic, negative = calculate_invested_capital(
            {
                "TOTAL_PARENT_EQUITY": 5000,
                "SHORT_LOAN": 1000,
                "LONG_LOAN": 2000,
                "BOND_PAYABLE": 500,
                "TREASURY_SHARES": 200,
            }
        )
        assert ic is not None
        assert ic == pytest.approx(8300.0, abs=1e-6)
        assert negative is False

    def test_invested_capital_example_2(self) -> None:
        """Example 2: Equity=10000, no debt, no bonds, no treasury stock.

        IC = 10000.
        """
        ic, negative = calculate_invested_capital(
            {
                "TOTAL_PARENT_EQUITY": 10000,
                "SHORT_LOAN": 0,
                "LONG_LOAN": 0,
                "BOND_PAYABLE": 0,
                "TREASURY_SHARES": 0,
            }
        )
        assert ic is not None
        assert ic == pytest.approx(10000.0, abs=1e-6)
        assert negative is False

    def test_invested_capital_negative(self) -> None:
        """Example 3: Equity=100, Treasury=500 -> IC = -400 (negative).

        Returns (None, True) when IC <= 0.
        """
        ic, negative = calculate_invested_capital(
            {
                "TOTAL_PARENT_EQUITY": 100,
                "SHORT_LOAN": 0,
                "LONG_LOAN": 0,
                "BOND_PAYABLE": 0,
                "TREASURY_SHARES": 500,
            }
        )
        assert ic is None
        assert negative is True


# ---------------------------------------------------------------------------
# ROIC calculation
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1ROIC:
    """L1 tests for ROIC calculation.

    Reference: Damodaran (2012).
    Formula: ROIC = NOPAT / Invested Capital
    """

    def test_roic_example_1(self) -> None:
        """Example 1: NOPAT=825, IC=8300 -> ROIC = 825/8300 = 0.099398."""
        roic = calculate_roic(825.0, 8300.0, negative_ic=False)
        assert roic is not None
        assert roic == pytest.approx(0.099398, rel=0.01)

    def test_roic_example_2(self) -> None:
        """Example 2: NOPAT=640, IC=10000 -> ROIC = 0.064."""
        roic = calculate_roic(640.0, 10000.0, negative_ic=False)
        assert roic is not None
        assert roic == pytest.approx(0.064, rel=0.01)

    def test_roic_none_inputs(self) -> None:
        """Example 3: None NOPAT -> returns None."""
        roic = calculate_roic(None, 8300.0, negative_ic=False)
        assert roic is None

    def test_roic_negative_ic(self) -> None:
        """Example 4: negative_ic=True -> returns None regardless of NOPAT."""
        roic = calculate_roic(825.0, 8300.0, negative_ic=True)
        assert roic is None


# ---------------------------------------------------------------------------
# ROIC-WACC spread
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1ROICWACCSpread:
    """L1 tests for ROIC-WACC spread and classification.

    Spread = ROIC - WACC
    """

    def test_spread_value_creating(self) -> None:
        """Example 1: ROIC=0.12, WACC=0.09 -> spread=0.03, VALUE_CREATING."""
        spread, cls = calculate_roic_wacc_spread(0.12, 0.09)
        assert spread is not None
        assert spread == pytest.approx(0.03, abs=1e-6)
        assert cls == SpreadClassification.VALUE_CREATING

    def test_spread_value_destroying(self) -> None:
        """Example 2: ROIC=0.05, WACC=0.10 -> spread=-0.05, VALUE_DESTROYING."""
        spread, cls = calculate_roic_wacc_spread(0.05, 0.10)
        assert spread is not None
        assert spread == pytest.approx(-0.05, abs=1e-6)
        assert cls == SpreadClassification.VALUE_DESTROYING

    def test_spread_insufficient_data(self) -> None:
        """Example 3: ROIC=None -> INSUFFICIENT_DATA."""
        spread, cls = calculate_roic_wacc_spread(None, 0.09)
        assert spread is None
        assert cls == SpreadClassification.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# ROIC trend
# ---------------------------------------------------------------------------


@pytest.mark.l1_formula
class TestL1ROICTrend:
    """L1 tests for ROIC trend analysis using linear regression.

    Classification based on slope:
    - slope > 0.005: COMPETITIVE_ADVANTAGE
    - slope < -0.005: DETERIORATING
    - otherwise: STABLE
    - < 3 valid points: INSUFFICIENT_DATA
    """

    def test_trend_increasing(self) -> None:
        """Increasing spreads [0.01, 0.03, 0.05] -> COMPETITIVE_ADVANTAGE."""
        result = analyze_roic_trend([0.01, 0.03, 0.05], [2021, 2022, 2023])
        assert result["trend"] == MoatTrend.COMPETITIVE_ADVANTAGE
        assert result["data_points"] == 3

    def test_trend_decreasing(self) -> None:
        """Decreasing spreads [0.05, 0.03, 0.01] -> DETERIORATING."""
        result = analyze_roic_trend([0.05, 0.03, 0.01], [2021, 2022, 2023])
        assert result["trend"] == MoatTrend.DETERIORATING
        assert result["data_points"] == 3

    def test_trend_stable(self) -> None:
        """Stable spreads [0.03, 0.03, 0.03] -> STABLE."""
        result = analyze_roic_trend([0.03, 0.03, 0.03], [2021, 2022, 2023])
        assert result["trend"] == MoatTrend.STABLE
        assert result["data_points"] == 3

    def test_trend_insufficient_data(self) -> None:
        """Fewer than 3 data points -> INSUFFICIENT_DATA."""
        result = analyze_roic_trend([0.01, 0.03], [2021, 2022])
        assert result["trend"] == MoatTrend.INSUFFICIENT_DATA
        assert result["data_points"] == 2
