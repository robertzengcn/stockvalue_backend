"""Unit tests for ROIC-WACC spread analysis service (TDD RED phase)."""

from stockvaluefinder.models.roic import MoatTrend, SpreadClassification
from stockvaluefinder.services.roic_service import (
    analyze_roic_trend,
    calculate_invested_capital,
    calculate_nopat,
    calculate_roic,
    calculate_roic_wacc_spread,
    is_financial_sector,
)
from stockvaluefinder.services.valuation_service import calculate_wacc


class TestIsFinancialSector:
    """Tests for is_financial_sector() sector detection (D-09)."""

    def test_bank(self) -> None:
        """Bank sector keyword detected."""
        assert is_financial_sector("银行II") is True

    def test_securities(self) -> None:
        """Securities sector keyword detected."""
        assert is_financial_sector("证券II") is True

    def test_insurance(self) -> None:
        """Insurance sector keyword detected."""
        assert is_financial_sector("保险II") is True

    def test_non_financial(self) -> None:
        """Baijiu (non-financial) sector not detected."""
        assert is_financial_sector("白酒II") is False

    def test_empty(self) -> None:
        """Empty string returns False."""
        assert is_financial_sector("") is False

    def test_manufacturing(self) -> None:
        """Food & beverage sector not detected."""
        assert is_financial_sector("食品饮料II") is False


class TestCalculateNopat:
    """Tests for calculate_nopat() dual formula (D-10)."""

    def test_non_financial(self) -> None:
        """Non-financial NOPAT = (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - T)."""
        profit_data = {
            "TOTAL_PROFIT": 100,
            "FINANCE_EXPENSE": 10,
            "INCOME_TAX": 25,
        }
        nopat, audit = calculate_nopat(profit_data, is_financial=False)
        # (100 + 10) * (1 - 25/100) = 110 * 0.75 = 82.5
        assert nopat is not None
        assert abs(nopat - 82.5) < 1e-6
        assert audit["tax_rate"] == 0.25
        assert audit["nopat"] == nopat

    def test_financial(self) -> None:
        """Financial NOPAT = OPERATE_PROFIT * (1 - T)."""
        profit_data = {
            "OPERATE_PROFIT": 200,
            "INCOME_TAX": 50,
            "TOTAL_PROFIT": 150,
        }
        nopat, audit = calculate_nopat(profit_data, is_financial=True)
        # 200 * (1 - 50/150) = 200 * (2/3) = 133.33...
        assert nopat is not None
        assert abs(nopat - 200 * (1 - 50 / 150)) < 1e-4

    def test_zero_tax(self) -> None:
        """Zero tax rate: NOPAT = operating profit unchanged."""
        profit_data = {
            "TOTAL_PROFIT": 100,
            "FINANCE_EXPENSE": 10,
            "INCOME_TAX": 0,
        }
        nopat, audit = calculate_nopat(profit_data, is_financial=False)
        # (100 + 10) * (1 - 0) = 110
        assert nopat is not None
        assert abs(nopat - 110.0) < 1e-6
        assert audit["tax_rate"] == 0.0

    def test_returns_audit_trail(self) -> None:
        """Audit trail contains required keys: nopat, tax_rate, formula, inputs."""
        profit_data = {
            "TOTAL_PROFIT": 100,
            "FINANCE_EXPENSE": 10,
            "INCOME_TAX": 25,
        }
        _, audit = calculate_nopat(profit_data, is_financial=False)
        assert "nopat" in audit
        assert "tax_rate" in audit
        assert "formula" in audit
        assert "inputs" in audit


class TestCalculateInvestedCapital:
    """Tests for calculate_invested_capital() (D-08, D-11)."""

    def test_normal(self) -> None:
        """Normal case: IC = equity + short_debt + long_debt + bonds - treasury."""
        balance_sheet = {
            "TOTAL_PARENT_EQUITY": 500,
            "SHORT_LOAN": 100,
            "LONG_LOAN": 200,
            "BOND_PAYABLE": 50,
            "TREASURY_SHARES": 20,
        }
        ic, negative_flag = calculate_invested_capital(balance_sheet)
        # 500 + 100 + 200 + 50 - 20 = 830
        assert ic is not None
        assert abs(ic - 830) < 1e-6
        assert negative_flag is False

    def test_negative_ic(self) -> None:
        """Negative invested capital returns None with flag (D-08)."""
        balance_sheet = {
            "TOTAL_PARENT_EQUITY": -100,
            "SHORT_LOAN": 50,
            "LONG_LOAN": 30,
            "BOND_PAYABLE": 0,
            "TREASURY_SHARES": 0,
        }
        ic, negative_flag = calculate_invested_capital(balance_sheet)
        # -100 + 50 + 30 + 0 - 0 = -20
        assert ic is None
        assert negative_flag is True

    def test_nan_debt_fields(self) -> None:
        """NaN debt fields normalize to 0.0 (D-11)."""
        balance_sheet = {
            "TOTAL_PARENT_EQUITY": 500,
            "SHORT_LOAN": float("nan"),
            "LONG_LOAN": float("nan"),
            "BOND_PAYABLE": float("nan"),
            "TREASURY_SHARES": 0,
        }
        ic, negative_flag = calculate_invested_capital(balance_sheet)
        # 500 + 0 + 0 + 0 - 0 = 500
        assert ic is not None
        assert abs(ic - 500) < 1e-6
        assert negative_flag is False

    def test_none_debt_fields(self) -> None:
        """None debt fields normalize to 0.0."""
        balance_sheet = {
            "TOTAL_PARENT_EQUITY": 500,
            "SHORT_LOAN": None,
            "LONG_LOAN": None,
            "BOND_PAYABLE": None,
            "TREASURY_SHARES": 0,
        }
        ic, negative_flag = calculate_invested_capital(balance_sheet)
        # 500 + 0 + 0 + 0 - 0 = 500
        assert ic is not None
        assert abs(ic - 500) < 1e-6
        assert negative_flag is False


class TestCalculateROIC:
    """Tests for calculate_roic()."""

    def test_valid(self) -> None:
        """Valid NOPAT/IC returns correct ROIC."""
        roic = calculate_roic(nopat=82.5, invested_capital=830, negative_ic=False)
        assert roic is not None
        # 82.5 / 830 = 0.099398...
        assert abs(roic - 0.099398) < 0.001

    def test_negative_ic(self) -> None:
        """Negative IC returns None (D-08)."""
        roic = calculate_roic(nopat=82.5, invested_capital=-100, negative_ic=True)
        assert roic is None

    def test_zero_ic(self) -> None:
        """Zero IC returns None to avoid division by zero."""
        roic = calculate_roic(nopat=82.5, invested_capital=0, negative_ic=False)
        assert roic is None


class TestCalculateROICWACCSpread:
    """Tests for calculate_roic_wacc_spread()."""

    def test_value_creating(self) -> None:
        """Positive spread = VALUE_CREATING."""
        spread, classification = calculate_roic_wacc_spread(roic=0.12, wacc=0.09)
        assert spread is not None
        assert abs(spread - 0.03) < 1e-10
        assert classification == SpreadClassification.VALUE_CREATING

    def test_value_destroying(self) -> None:
        """Negative spread = VALUE_DESTROYING."""
        spread, classification = calculate_roic_wacc_spread(roic=0.06, wacc=0.09)
        assert spread is not None
        assert abs(spread - (-0.03)) < 1e-10
        assert classification == SpreadClassification.VALUE_DESTROYING

    def test_none_roic(self) -> None:
        """None ROIC = INSUFFICIENT_DATA."""
        spread, classification = calculate_roic_wacc_spread(roic=None, wacc=0.09)
        assert spread is None
        assert classification == SpreadClassification.INSUFFICIENT_DATA

    def test_equal(self) -> None:
        """ROIC == WACC = VALUE_CREATING (>= threshold)."""
        spread, classification = calculate_roic_wacc_spread(roic=0.09, wacc=0.09)
        assert spread is not None
        assert abs(spread - 0.0) < 1e-10
        assert classification == SpreadClassification.VALUE_CREATING


class TestAnalyzeROICTrend:
    """Tests for analyze_roic_trend() (D-06)."""

    def test_competitive_advantage(self) -> None:
        """Widening spreads -> COMPETITIVE_ADVANTAGE."""
        result = analyze_roic_trend(
            spreads=[0.01, 0.03, 0.05], years=[2021, 2022, 2023]
        )
        assert result["trend"] == MoatTrend.COMPETITIVE_ADVANTAGE
        assert result["slope"] is not None
        assert result["slope"] > 0.005

    def test_deteriorating(self) -> None:
        """Narrowing spreads -> DETERIORATING."""
        result = analyze_roic_trend(
            spreads=[0.05, 0.03, 0.01], years=[2021, 2022, 2023]
        )
        assert result["trend"] == MoatTrend.DETERIORATING
        assert result["slope"] is not None
        assert result["slope"] < -0.005

    def test_stable(self) -> None:
        """Flat spreads -> STABLE."""
        result = analyze_roic_trend(
            spreads=[0.03, 0.031, 0.029], years=[2021, 2022, 2023]
        )
        assert result["trend"] == MoatTrend.STABLE

    def test_with_none_values(self) -> None:
        """Fewer than 3 valid points -> INSUFFICIENT_DATA."""
        result = analyze_roic_trend(
            spreads=[0.03, None, 0.05], years=[2021, 2022, 2023]
        )
        assert result["trend"] == MoatTrend.INSUFFICIENT_DATA

    def test_insufficient_data(self) -> None:
        """Single data point -> INSUFFICIENT_DATA."""
        result = analyze_roic_trend(spreads=[0.03], years=[2023])
        assert result["trend"] == MoatTrend.INSUFFICIENT_DATA

    def test_returns_slope_and_pvalue(self) -> None:
        """Result contains slope and p_value keys."""
        result = analyze_roic_trend(
            spreads=[0.01, 0.02, 0.03], years=[2021, 2022, 2023]
        )
        assert "slope" in result
        assert "p_value" in result
        assert result["slope"] is not None
        assert result["p_value"] is not None


class TestWACCBackwardCompat:
    """Tests for backward-compatible WACC calculation."""

    def test_existing_3arg(self) -> None:
        """Original 3-arg call returns same result."""
        assert calculate_wacc(0.03, 1.0, 0.06) == 0.09

    def test_existing_3arg_2(self) -> None:
        """Another 3-arg call returns same result."""
        assert abs(calculate_wacc(0.025, 1.2, 0.05) - 0.085) < 1e-10

    def test_true_wacc(self) -> None:
        """6-arg call computes true WACC = We*Ke + Wd*Kd*(1-T)."""
        # Ke = 0.03 + 1.0*0.06 = 0.09
        # WACC = 0.7*0.09 + 0.3*0.05*0.75 = 0.063 + 0.01125 = 0.07425
        # Wait, let me recalculate: 0.7*0.09 = 0.063, 0.3*0.05*(1-0.25) = 0.3*0.05*0.75 = 0.01125
        # Total = 0.063 + 0.01125 = 0.07425
        result = calculate_wacc(0.03, 1.0, 0.06, 0.3, 0.05, 0.25)
        assert abs(result - 0.07425) < 1e-10

    def test_debt_free_company(self) -> None:
        """Debt-free company WACC equals Ke-only."""
        result = calculate_wacc(0.03, 1.0, 0.06, 0.0, 0.0, 0.0)
        assert result == 0.09
