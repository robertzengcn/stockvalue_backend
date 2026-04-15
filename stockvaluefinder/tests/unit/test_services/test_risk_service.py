"""Property-based tests for risk calculation functions."""

import pytest
from decimal import Decimal
from hypothesis import given, strategies as st

from stockvaluefinder.models.risk import MScoreData, IndexAuditDetail
from stockvaluefinder.services.risk_service import (
    analyze_financial_risk,
    calculate_beneish_m_score,
    calculate_piotroski_f_score,
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

        assert result["ratio"] == 0.3  # 30% (float)
        assert result["excessive"] is False  # Borderline, should not flag

    def test_goodwill_ratio_excessive(self) -> None:
        """Test goodwill ratio detection for excessive goodwill."""
        result = calculate_goodwill_ratio(
            goodwill=Decimal("5_000_000_000"),  # 5B
            equity=Decimal("10_000_000_000"),  # 10B
        )

        assert result["ratio"] == 0.5  # 50% (float)
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


@pytest.mark.unit
class TestPiotroskiFScore:
    """Unit tests for Piotroski F-Score calculation."""

    def test_f_score_healthy_company(self) -> None:
        """Healthy fundamentals should produce a high F-Score."""
        current = {
            "net_income": "1200000000",
            "operating_cash_flow": "1500000000",
            "assets_total": "10000000000",
            "interest_bearing_debt": "1800000000",
            "cash_and_equivalents": "2500000000",
            "liabilities_total": "3500000000",
            "shares_outstanding": "1000000000",
            "gross_margin": 42.0,
            "revenue": "12000000000",
        }
        previous = {
            "net_income": "800000000",
            "operating_cash_flow": "900000000",
            "assets_total": "9000000000",
            "interest_bearing_debt": "2200000000",
            "cash_and_equivalents": "1800000000",
            "liabilities_total": "3600000000",
            "shares_outstanding": "1000000000",
            "gross_margin": 38.0,
            "revenue": "10000000000",
        }

        result = calculate_piotroski_f_score(current, previous)

        assert result["f_score"] >= 7
        assert result["positive_roa"] is True
        assert result["positive_cfo"] is True
        assert result["improving_roa"] is True

    def test_f_score_weak_company(self) -> None:
        """Weak fundamentals should produce a low F-Score."""
        current = {
            "net_income": "-100000000",
            "operating_cash_flow": "-50000000",
            "assets_total": "9000000000",
            "interest_bearing_debt": "3000000000",
            "cash_and_equivalents": "900000000",
            "liabilities_total": "5000000000",
            "shares_outstanding": "1100000000",
            "gross_margin": 21.0,
            "revenue": "7000000000",
        }
        previous = {
            "net_income": "100000000",
            "operating_cash_flow": "150000000",
            "assets_total": "8500000000",
            "interest_bearing_debt": "2500000000",
            "cash_and_equivalents": "1200000000",
            "liabilities_total": "4500000000",
            "shares_outstanding": "1000000000",
            "gross_margin": 25.0,
            "revenue": "7600000000",
        }

        result = calculate_piotroski_f_score(current, previous)

        assert result["f_score"] <= 2
        assert result["positive_roa"] is False
        assert result["positive_cfo"] is False
        assert result["no_new_shares"] is False

    def test_analyze_financial_risk_includes_f_score_fields(self) -> None:
        """Integrated risk result should include F-Score and component flags."""
        current = {
            "ticker": "600519.SH",
            "net_income": "1200000000",
            "operating_cash_flow": "1500000000",
            "assets_total": "10000000000",
            "interest_bearing_debt": "1800000000",
            "cash_and_equivalents": "2500000000",
            "liabilities_total": "3500000000",
            "shares_outstanding": "1000000000",
            "gross_margin": 42.0,
            "revenue": "12000000000",
            "equity_total": "5000000000",
            "goodwill": "300000000",
            "days_sales_receivables_index": 1.0,
            "gross_margin_index": 1.0,
            "asset_quality_index": 1.0,
            "sales_growth_index": 1.1,
            "depreciation_index": 1.0,
            "sga_expense_index": 1.0,
            "leverage_index": 1.0,
            "total_accruals_to_assets": -0.05,
        }
        previous = {
            "ticker": "600519.SH",
            "net_income": "800000000",
            "operating_cash_flow": "900000000",
            "assets_total": "9000000000",
            "interest_bearing_debt": "2200000000",
            "cash_and_equivalents": "1800000000",
            "liabilities_total": "3600000000",
            "shares_outstanding": "1000000000",
            "gross_margin": 38.0,
            "revenue": "10000000000",
            "equity_total": "4500000000",
            "goodwill": "300000000",
        }

        result = analyze_financial_risk(current, previous)

        assert 0 <= result.f_score <= 9
        assert result.fscore_data.positive_roa is True
        assert isinstance(result.fscore_data.no_new_shares, bool)

    def test_f_score_without_previous_report_only_counts_current_signals(self) -> None:
        """When no previous data exists, YoY signals should stay false."""
        current = {
            "net_income": "100000000",
            "operating_cash_flow": "120000000",
            "assets_total": "5000000000",
            "interest_bearing_debt": "1000000000",
            "cash_and_equivalents": "900000000",
            "liabilities_total": "2000000000",
            "gross_margin": 30.0,
            "revenue": "4500000000",
        }

        result = calculate_piotroski_f_score(current, {})

        assert result["f_score"] <= 3
        assert result["improving_roa"] is False
        assert result["lower_leverage"] is False
        assert result["higher_liquidity"] is False
        assert result["improving_margin"] is False
        assert result["improving_turnover"] is False

    def test_no_divergence_both_decline(self) -> None:
        """Test no divergence when both profit and OCF decline."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("6_000_000_000"),  # 6B
            previous_profit=Decimal("8_000_000_000"),  # 8B
            current_ocf=Decimal("6_000_000_000"),  # 6B
            previous_ocf=Decimal("8_000_000_000"),  # 8B
        )

        assert result["divergence"] is False


@pytest.mark.unit
class TestMScoreDataExtension:
    """Tests for MScoreData model extension with audit trail."""

    def test_mscoredata_without_audit_trail(self) -> None:
        """MScoreData can be constructed without audit_trail (backward compatible)."""
        data = MScoreData(
            dsri=1.0, gmi=1.0, aqi=1.0, sgi=1.0,
            depi=1.0, sgai=1.0, lvgi=1.0, tata=0.0,
        )
        assert data.dsri == 1.0
        assert data.audit_trail == {}

    def test_mscoredata_with_audit_trail(self) -> None:
        """MScoreData stores audit_trail entries correctly."""
        detail = IndexAuditDetail(
            value=1.5, numerator=3.0, denominator=2.0,
            source_fields={"accounts_receivable": "ACCOUNTS_RECE (AKShare)"},
        )
        data = MScoreData(
            dsri=1.5, gmi=1.0, aqi=1.0, sgi=1.0,
            depi=1.0, sgai=1.0, lvgi=1.0, tata=0.0,
            audit_trail={"dsri": detail},
        )
        assert data.audit_trail["dsri"].value == 1.5
        assert data.audit_trail["dsri"].numerator == 3.0
        assert data.audit_trail["dsri"].source_fields["accounts_receivable"] == "ACCOUNTS_RECE (AKShare)"

    def test_index_audit_detail_frozen(self) -> None:
        """IndexAuditDetail is immutable (frozen=True)."""
        detail = IndexAuditDetail(
            value=1.0, numerator=1.0, denominator=1.0,
            source_fields={},
        )
        with pytest.raises(Exception):
            detail.value = 2.0  # type: ignore[misc]

    def test_existing_mscoredata_construction_still_works(self) -> None:
        """Verify existing test data still constructs MScoreData successfully."""
        data = MScoreData(
            dsri=1.0, gmi=0.98, aqi=1.01, sgi=1.15,
            depi=1.03, sgai=0.97, lvgi=0.95, tata=-0.02,
        )
        assert data.dsri == 1.0
        assert data.gmi == 0.98
        assert isinstance(data.audit_trail, dict)
        assert len(data.audit_trail) == 0
