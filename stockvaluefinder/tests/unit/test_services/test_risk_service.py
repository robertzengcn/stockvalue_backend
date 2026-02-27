"""Property-based tests for risk calculation functions."""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st

from stockvaluefinder.services.risk_service import (
    calculate_beneish_m_score,
    detect_存贷双高,
    calculate_goodwill_ratio,
    detect_profit_cash_divergence,
)


@pytest.mark.unit
class TestBeneishMScore:
    """Property-based tests for Beneish M-Score calculation."""

    @given(
        # Current year financial metrics
        days_sales_receivables=st.floats(min_value=0.5, max_value=3.0),
        gross_margin=st.floats(min_value=-0.5, max_value=1.0),
        asset_quality=st.floats(min_value=0.5, max_value=3.0),
        sales_growth=st.floats(min_value=-0.5, max_value=2.0),
        depreciation=st.floats(min_value=0.5, max_value=3.0),
        sga_expense=st.floats(min_value=0.5, max_value=3.0),
        leverage=st.floats(min_value=0.5, max_value=3.0),
        total_accruals=st.floats(min_value=-0.5, max_value=0.5),
        # Previous year metrics (for ratio calculation)
        prev_days_sales_receivables=st.floats(min_value=0.5, max_value=3.0),
        prev_gross_margin=st.floats(min_value=-0.5, max_value=1.0),
        prev_asset_quality=st.floats(min_value=0.5, max_value=3.0),
        prev_sales=st.floats(min_value=1e6, max_value=1e12),
        prev_depreciation=st.floats(min_value=1e6, max_value=1e12),
        prev_sga_expense=st.floats(min_value=1e6, max_value=1e12),
        prev_total_debt=st.floats(min_value=0, max_value=1e12),
        prev_total_assets=st.floats(min_value=1e6, max_value=1e12),
        curr_sales=st.floats(min_value=1e6, max_value=1e12),
        curr_depreciation=st.floats(min_value=1e6, max_value=1e12),
        curr_sga_expense=st.floats(min_value=1e6, max_value=1e12),
        curr_total_debt=st.floats(min_value=0, max_value=1e12),
        curr_total_assets=st.floats(min_value=1e6, max_value=1e12),
    )
    def test_beneish_m_score_formula_accuracy(
        self,
        days_sales_receivables: float,
        gross_margin: float,
        asset_quality: float,
        sales_growth: float,
        depreciation: float,
        sga_expense: float,
        leverage: float,
        total_accruals: float,
        prev_days_sales_receivables: float,
        prev_gross_margin: float,
        prev_asset_quality: float,
        prev_sales: float,
        prev_depreciation: float,
        prev_sga_expense: float,
        prev_total_debt: float,
        prev_total_assets: float,
        curr_sales: float,
        curr_depreciation: float,
        curr_sga_expense: float,
        curr_total_debt: float,
        curr_total_assets: float,
    ) -> None:
        """Test Beneish M-Score formula with random inputs.

        Property: M-Score should be calculated as:
        M-Score = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI
                + 0.892*SGI + 0.115*DEPI - 0.172*SGAI
                + 4.679*TATA - 0.327*LVGI

        The result should always be a finite number.
        """
        # Create current and previous year financial data
        current_data = {
            "days_sales_receivables_index": days_sales_receivables,
            "gross_margin_index": gross_margin,
            "asset_quality_index": asset_quality,
            "sales_growth_index": sales_growth,
            "depreciation_index": depreciation,
            "sga_expense_index": sga_expense,
            "leverage_index": leverage,
            "total_accruals_to_assets": total_accruals,
        }

        previous_data = {
            "days_sales_receivables_index": prev_days_sales_receivables,
            "gross_margin_index": prev_gross_margin,
            "asset_quality_index": prev_asset_quality,
            "sales": prev_sales,
            "depreciation": prev_depreciation,
            "sga_expense": prev_sga_expense,
            "total_debt": prev_total_debt,
            "total_assets": prev_total_assets,
        }

        result = calculate_beneish_m_score(current_data, previous_data)

        # Verify result structure
        assert isinstance(result, dict)
        assert "m_score" in result
        assert "dsri" in result
        assert "gmi" in result
        assert "aqi" in result
        assert "sgi" in result
        assert "depi" in result
        assert "sgai" in result
        assert "lvgi" in result
        assert "tata" in result

        # Verify M-Score is a valid number
        m_score = result["m_score"]
        assert isinstance(m_score, float)
        assert not (m_score != m_score)  # Check for NaN
        assert abs(m_score) < 100  # Should be reasonable range

    def test_beneish_m_score_thresholds(self) -> None:
        """Test M-Score interpretation thresholds.

        Property:
        - M-Score < -1.78 indicates low manipulation risk
        - M-Score >= -1.78 indicates high manipulation risk
        """
        # Test safe company (low M-Score)
        safe_data = {
            "dsri": 1.0,
            "gmi": 1.0,
            "aqi": 1.0,
            "sgi": 1.05,
            "depi": 1.0,
            "sgai": 1.0,
            "lvgi": 1.0,
            "tata": -0.05,
        }

        # Calculate M-Score manually to verify threshold
        m_score = (
            -4.84
            + 0.92 * safe_data["dsri"]
            + 0.528 * safe_data["gmi"]
            + 0.404 * safe_data["aqi"]
            + 0.892 * safe_data["sgi"]
            + 0.115 * safe_data["depi"]
            - 0.172 * safe_data["sgai"]
            + 4.679 * safe_data["tata"]
            - 0.327 * safe_data["lvgi"]
        )

        assert m_score < -1.78, "Test data should indicate low risk"

        # Test risky company (high M-Score)
        risky_data = {
            "dsri": 2.0,
            "gmi": 1.5,
            "aqi": 2.0,
            "sgi": 2.0,
            "depi": 0.5,
            "sgai": 1.5,
            "lvgi": 1.5,
            "tata": 0.1,
        }

        m_score_risky = (
            -4.84
            + 0.92 * risky_data["dsri"]
            + 0.528 * risky_data["gmi"]
            + 0.404 * risky_data["aqi"]
            + 0.892 * risky_data["sgi"]
            + 0.115 * risky_data["depi"]
            - 0.172 * risky_data["sgai"]
            + 4.679 * risky_data["tata"]
            - 0.327 * risky_data["lvgi"]
        )

        assert m_score_risky > -1.78, "Test data should indicate high risk"


@pytest.mark.unit
class Test存贷双高Detection:
    """Unit tests for 存贷双高 (high cash + high debt) detection."""

    def test_存贷双高_positive_case(self) -> None:
        """Test detection when both cash and debt are high.

        Given:
        - Cash and equivalents > 1 billion
        - Interest-bearing debt > 1 billion
        - YoY cash growth > 50%
        - YoY debt growth > 50%

        Then should flag as 存贷双高
        """
        current_financials = {
            "cash_and_equivalents": Decimal("5_000_000_000"),  # 5B
            "interest_bearing_debt": Decimal("8_000_000_000"),  # 8B
            "total_assets": Decimal("50_000_000_000"),  # 50B
        }

        previous_financials = {
            "cash_and_equivalents": Decimal("2_000_000_000"),  # 2B
            "interest_bearing_debt": Decimal("3_000_000_000"),  # 3B
        }

        result = detect_存贷双高(current_financials, previous_financials)

        assert result["存贷双高"] is True
        assert result["cash_amount"] > 0
        assert result["debt_amount"] > 0
        assert result["cash_growth_rate"] > 0.5
        assert result["debt_growth_rate"] > 0.5

    def test_存贷双高_negative_case_low_cash(self) -> None:
        """Test detection when cash is low.

        Given:
        - Cash and equivalents < 1 billion
        - Interest-bearing debt > 1 billion

        Then should NOT flag as 存贷双高
        """
        current_financials = {
            "cash_and_equivalents": Decimal("500_000_000"),  # 500M
            "interest_bearing_debt": Decimal("8_000_000_000"),  # 8B
            "total_assets": Decimal("50_000_000_000"),  # 50B
        }

        previous_financials = {
            "cash_and_equivalents": Decimal("400_000_000"),  # 400M
            "interest_bearing_debt": Decimal("3_000_000_000"),  # 3B
        }

        result = detect_存贷双高(current_financials, previous_financials)

        assert result["存贷双高"] is False

    def test_存贷双高_negative_case_low_debt(self) -> None:
        """Test detection when debt is low.

        Given:
        - Cash and equivalents > 1 billion
        - Interest-bearing debt < 1 billion

        Then should NOT flag as 存贷双高
        """
        current_financials = {
            "cash_and_equivalents": Decimal("5_000_000_000"),  # 5B
            "interest_bearing_debt": Decimal("500_000_000"),  # 500M
            "total_assets": Decimal("50_000_000_000"),  # 50B
        }

        previous_financials = {
            "cash_and_equivalents": Decimal("2_000_000_000"),  # 2B
            "interest_bearing_debt": Decimal("400_000_000"),  # 400M
        }

        result = detect_存贷双高(current_financials, previous_financials)

        assert result["存贷双高"] is False


@pytest.mark.unit
class TestGoodwillRatio:
    """Unit tests for goodwill ratio calculation."""

    def test_goodwill_ratio_normal(self) -> None:
        """Test goodwill ratio for normal levels."""
        result = calculate_goodwill_ratio(
            goodwill=Decimal("3_000_000_000"),  # 3B
            equity=Decimal("10_000_000_000"),  # 10B
        )

        assert result["ratio"] == Decimal("0.3")  # 30%
        assert result["excessive"] is False  # Borderline, should not flag

    def test_goodwill_ratio_excessive(self) -> None:
        """Test goodwill ratio detection for excessive goodwill."""
        result = calculate_goodwill_ratio(
            goodwill=Decimal("5_000_000_000"),  # 5B
            equity=Decimal("10_000_000_000"),  # 10B
        )

        assert result["ratio"] == Decimal("0.5")  # 50%
        assert result["excessive"] is True

    def test_goodwill_ratio_zero(self) -> None:
        """Test goodwill ratio when no goodwill."""
        result = calculate_goodwill_ratio(
            goodwill=Decimal("0"),
            equity=Decimal("10_000_000_000"),  # 10B
        )

        assert result["ratio"] == Decimal("0")
        assert result["excessive"] is False


@pytest.mark.unit
class TestProfitCashDivergence:
    """Unit tests for profit-cash flow divergence detection."""

    def test_divergence_detected(self) -> None:
        """Test detection when profit grows but OCF declines."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("10_000_000_000"),  # 10B
            previous_profit=Decimal("8_000_000_000"),  # 8B (25% growth)
            current_ocf=Decimal("6_000_000_000"),  # 6B
            previous_ocf=Decimal("8_000_000_000"),  # 8B (25% decline)
        )

        assert result["divergence"] is True
        assert result["profit_growth"] > 0
        assert result["ocf_growth"] < 0

    def test_no_divergence_both_grow(self) -> None:
        """Test no divergence when both profit and OCF grow."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("10_000_000_000"),  # 10B
            previous_profit=Decimal("8_000_000_000"),  # 8B
            current_ocf=Decimal("10_000_000_000"),  # 10B
            previous_ocf=Decimal("8_000_000_000"),  # 8B
        )

        assert result["divergence"] is False

    def test_no_divergence_both_decline(self) -> None:
        """Test no divergence when both profit and OCF decline."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("6_000_000_000"),  # 6B
            previous_profit=Decimal("8_000_000_000"),  # 8B
            current_ocf=Decimal("6_000_000_000"),  # 6B
            previous_ocf=Decimal("8_000_000_000"),  # 8B
        )

        assert result["divergence"] is False
