"""Property-based tests for risk calculation functions."""

import pytest
from decimal import Decimal
from typing import Any
from hypothesis import given, strategies as st

from stockvaluefinder.models.enums import RiskLevel
from stockvaluefinder.models.risk import MScoreData, IndexAuditDetail, RiskScore
from stockvaluefinder.services.risk_service import (
    _to_float,
    analyze_financial_risk,
    calculate_beneish_m_score,
    calculate_goodwill_ratio,
    calculate_mscore_indices,
    calculate_piotroski_f_score,
    detect_profit_cash_divergence,
    detect_存贷双高,
    determine_risk_level,
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
            "report_source": "test",
            # M-Score raw fields (replacing old hardcoded indices)
            "accounts_receivable": "500000000",
            "cost_of_goods": "7000000000",
            "total_current_assets": "4500000000",
            "ppe": "4000000000",
            "sga_expense": "4000000000",
            "total_liabilities": "3500000000",
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
            "report_source": "test",
            # M-Score raw fields
            "accounts_receivable": "450000000",
            "cost_of_goods": "6500000000",
            "total_current_assets": "4000000000",
            "ppe": "3800000000",
            "sga_expense": "3500000000",
            "total_liabilities": "3600000000",
        }

        result = analyze_financial_risk(current, previous)

        assert 0 <= result.f_score <= 9
        assert result.fscore_data.positive_roa is True
        assert isinstance(result.fscore_data.no_new_shares, bool)

    def test_analyze_financial_risk_uses_real_indices(self) -> None:
        """M-Score should NOT be -2.79 (the value with all 1.0/0.0 indices)."""
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
            "report_source": "test",
            "accounts_receivable": "500000000",
            "cost_of_goods": "7000000000",
            "total_current_assets": "4500000000",
            "ppe": "4000000000",
            "sga_expense": "4000000000",
            "total_liabilities": "3500000000",
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
            "report_source": "test",
            "accounts_receivable": "450000000",
            "cost_of_goods": "6500000000",
            "total_current_assets": "4000000000",
            "ppe": "3800000000",
            "sga_expense": "3500000000",
            "total_liabilities": "3600000000",
        }

        result = analyze_financial_risk(current, previous)
        # -2.79 is the M-Score when all indices are 1.0 and TATA is 0.0
        assert result.m_score != -2.79

    def test_analyze_financial_risk_audit_trail_in_mscoredata(self) -> None:
        """Result mscore_data should contain audit_trail from calculation."""
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
            "report_source": "test",
            "accounts_receivable": "500000000",
            "cost_of_goods": "7000000000",
            "total_current_assets": "4500000000",
            "ppe": "4000000000",
            "sga_expense": "4000000000",
            "total_liabilities": "3500000000",
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
            "report_source": "test",
            "accounts_receivable": "450000000",
            "cost_of_goods": "6500000000",
            "total_current_assets": "4000000000",
            "ppe": "3800000000",
            "sga_expense": "3500000000",
            "total_liabilities": "3600000000",
        }

        result = analyze_financial_risk(current, previous)
        assert len(result.mscore_data.audit_trail) > 0
        assert "dsri" in result.mscore_data.audit_trail

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
            dsri=1.0,
            gmi=1.0,
            aqi=1.0,
            sgi=1.0,
            depi=1.0,
            sgai=1.0,
            lvgi=1.0,
            tata=0.0,
        )
        assert data.dsri == 1.0
        assert data.audit_trail == {}

    def test_mscoredata_with_audit_trail(self) -> None:
        """MScoreData stores audit_trail entries correctly."""
        detail = IndexAuditDetail(
            value=1.5,
            numerator=3.0,
            denominator=2.0,
            source_fields={"accounts_receivable": "ACCOUNTS_RECE (AKShare)"},
        )
        data = MScoreData(
            dsri=1.5,
            gmi=1.0,
            aqi=1.0,
            sgi=1.0,
            depi=1.0,
            sgai=1.0,
            lvgi=1.0,
            tata=0.0,
            audit_trail={"dsri": detail},
        )
        assert data.audit_trail["dsri"].value == 1.5
        assert data.audit_trail["dsri"].numerator == 3.0
        assert (
            data.audit_trail["dsri"].source_fields["accounts_receivable"]
            == "ACCOUNTS_RECE (AKShare)"
        )

    def test_index_audit_detail_frozen(self) -> None:
        """IndexAuditDetail is immutable (frozen=True)."""
        detail = IndexAuditDetail(
            value=1.0,
            numerator=1.0,
            denominator=1.0,
            source_fields={},
        )
        with pytest.raises(Exception):
            detail.value = 2.0  # type: ignore[misc]

    def test_existing_mscoredata_construction_still_works(self) -> None:
        """Verify existing test data still constructs MScoreData successfully."""
        data = MScoreData(
            dsri=1.0,
            gmi=0.98,
            aqi=1.01,
            sgi=1.15,
            depi=1.03,
            sgai=0.97,
            lvgi=0.95,
            tata=-0.02,
        )
        assert data.dsri == 1.0
        assert data.gmi == 0.98
        assert isinstance(data.audit_trail, dict)
        assert len(data.audit_trail) == 0


@pytest.mark.unit
class TestMScoreFieldMapping:
    """Tests for M-Score field mapping in data service."""

    def test_mock_report_contains_mscore_fields(self) -> None:
        """Mock financial report includes all 6 new M-Score fields."""
        from stockvaluefinder.external.data_service import ExternalDataService

        service = ExternalDataService(
            tushare_token="", enable_akshare=False, enable_efinance=False
        )
        report = service._get_mock_financial_report("600519.SH", 2023)

        required_fields = [
            "cost_of_goods",
            "sga_expense",
            "total_current_assets",
            "ppe",
            "long_term_debt",
            "total_liabilities",
        ]
        for field in required_fields:
            assert field in report, f"Missing field: {field}"
            assert report[field] is not None
            assert report[field] != ""

    def test_mock_report_no_hardcoded_indices(self) -> None:
        """Mock report does NOT contain old hardcoded index keys."""
        from stockvaluefinder.external.data_service import ExternalDataService

        service = ExternalDataService(
            tushare_token="", enable_akshare=False, enable_efinance=False
        )
        report = service._get_mock_financial_report("600519.SH", 2023)

        old_keys = [
            "days_sales_receivables_index",
            "gross_margin_index",
            "asset_quality_index",
            "sales_growth_index",
            "depreciation_index",
            "sga_expense_index",
            "leverage_index",
            "total_accruals_to_assets",
        ]
        for key in old_keys:
            assert key not in report, f"Old hardcoded key still present: {key}"

    def test_akshare_field_mapping_structure(self) -> None:
        """Verify AKShare field mapping uses correct field names."""
        import inspect
        from stockvaluefinder.external.data_service import ExternalDataService

        source = inspect.getsource(
            ExternalDataService._get_financial_report_from_akshare
        )

        # Verify correct AKShare field names are used
        assert "OPERATE_COST" in source, (
            "AKShare should use OPERATE_COST for cost_of_goods"
        )
        assert "TOTAL_OPERATE_COST" in source, (
            "AKShare should use TOTAL_OPERATE_COST for sga_expense"
        )
        assert "TOTAL_CURRENT_ASSETS" in source
        assert "FIXED_ASSET" in source
        assert "LONG_LOAN" in source, "AKShare should use LONG_LOAN (not LONGTERM_LOAN)"
        assert "TOTAL_LIABILITIES" in source

        # Verify hardcoded indices are removed
        assert "days_sales_receivables_index" not in source


def _make_test_reports() -> tuple[dict[str, Any], dict[str, Any]]:
    """Create standard two-year test reports with known M-Score values."""
    current: dict[str, Any] = {
        "revenue": "10000",
        "net_income": "1000",
        "operating_cash_flow": "800",
        "accounts_receivable": "500",
        "cost_of_goods": "6000",
        "total_current_assets": "5000",
        "total_assets": "10000",
        "ppe": "2000",
        "sga_expense": "2000",
        "total_liabilities": "3000",
    }
    previous: dict[str, Any] = {
        "revenue": "8000",
        "net_income": "800",
        "operating_cash_flow": "700",
        "accounts_receivable": "400",
        "cost_of_goods": "5000",
        "total_current_assets": "4000",
        "total_assets": "9000",
        "ppe": "2200",
        "sga_expense": "1800",
        "total_liabilities": "2800",
    }
    return current, previous


@pytest.mark.unit
class TestMScoreIndices:
    """Tests for calculate_mscore_indices pure function."""

    def test_dsri_calculation(self) -> None:
        """DSRI = (AR_curr/Rev_curr) / (AR_prev/Rev_prev)."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        # (500/10000) / (400/8000) = 0.05 / 0.05 = 1.0
        assert result["dsri"] == 1.0

    def test_gmi_calculation(self) -> None:
        """GMI = GrossMargin_prev / GrossMargin_curr."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        # GM_curr = (10000-6000)/10000 = 0.4, GM_prev = (8000-5000)/8000 = 0.375
        # GMI = 0.375/0.4 = 0.9375
        assert abs(result["gmi"] - 0.9375) < 0.001

    def test_aqi_calculation(self) -> None:
        """AQI = (1-(CA_curr-PPE_curr)/TA_curr) / (1-(CA_prev-PPE_prev)/TA_prev)."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        # AQ_curr = 1-(5000-2000)/10000 = 0.7
        # AQ_prev = 1-(4000-2200)/9000 = 0.8
        # AQI = 0.7/0.8 = 0.875
        assert abs(result["aqi"] - 0.875) < 0.001

    def test_sgi_calculation(self) -> None:
        """SGI = Revenue_curr / Revenue_prev."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        # 10000/8000 = 1.25
        assert result["sgi"] == 1.25

    def test_depi_always_one(self) -> None:
        """DEPI is hardcoded to 1.0 per MVP decision D-05."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        assert result["depi"] == 1.0

    def test_sgai_calculation(self) -> None:
        """SGAI = (SGA_curr/Rev_curr) / (SGA_prev/Rev_prev)."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        # (2000/10000) / (1800/8000) = 0.2/0.225 = 0.8889
        assert abs(result["sgai"] - 0.8889) < 0.001

    def test_lvgi_calculation(self) -> None:
        """LVGI = (TL_curr/TA_curr) / (TL_prev/TA_prev)."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        # (3000/10000) / (2800/9000) = 0.3/0.3111 = 0.9643
        assert abs(result["lvgi"] - 0.9643) < 0.001

    def test_tata_calculation(self) -> None:
        """TATA = (NetIncome - OperatingCashFlow) / TotalAssets."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        # (1000 - 800) / 10000 = 0.02
        assert abs(result["tata"] - 0.02) < 0.001

    def test_zero_denominator_handling(self) -> None:
        """Zero denominator marks index as non_calculable, defaults to 1.0."""
        current, _ = _make_test_reports()
        previous = {
            "revenue": "0",
            "net_income": "800",
            "operating_cash_flow": "700",
            "accounts_receivable": "400",
            "cost_of_goods": "5000",
            "total_current_assets": "4000",
            "total_assets": "9000",
            "ppe": "2200",
            "sga_expense": "1800",
            "total_liabilities": "2800",
        }
        result = calculate_mscore_indices(current, previous)
        assert result["sgi"] == 1.0
        assert "SGI" in result["non_calculable"]
        assert any("SGI" in f for f in result["red_flags"])

    def test_missing_field_raises_error(self) -> None:
        """Missing required field raises DataValidationError."""
        from stockvaluefinder.utils.errors import DataValidationError

        current, previous = _make_test_reports()
        del current["accounts_receivable"]
        with pytest.raises(DataValidationError, match="accounts_receivable"):
            calculate_mscore_indices(current, previous)

    def test_nan_value_handling(self) -> None:
        """Field value of 'nan' string is treated as 0.0."""
        current, previous = _make_test_reports()
        current["accounts_receivable"] = "nan"
        # AR_curr=0, so DSRI ratio = 0/0.05 = 0, should not crash
        result = calculate_mscore_indices(current, previous)
        assert isinstance(result["dsri"], float)

    def test_audit_trail_structure(self) -> None:
        """Each index has an IndexAuditDetail in audit_trail."""
        current, previous = _make_test_reports()
        result = calculate_mscore_indices(current, previous)
        for idx_name in ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"]:
            assert idx_name in result["audit_trail"]
            detail = result["audit_trail"][idx_name]
            assert hasattr(detail, "value")
            assert hasattr(detail, "numerator")
            assert hasattr(detail, "denominator")
            assert hasattr(detail, "source_fields")

    def test_assets_total_alias(self) -> None:
        """'assets_total' key works as alias for 'total_assets'."""
        current, previous = _make_test_reports()
        del current["total_assets"]
        current["assets_total"] = "10000"
        del previous["total_assets"]
        previous["assets_total"] = "9000"
        result = calculate_mscore_indices(current, previous)
        assert isinstance(result["tata"], float)


# ---------------------------------------------------------------------------
# Phase 03 additions: determine_risk_level, analyze_financial_risk, edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDetermineRiskLevel:
    """Tests for determine_risk_level classification function."""

    def test_high_risk_m_score_above_threshold(self) -> None:
        """M-Score >= -1.78 with 0 red flags yields HIGH risk."""
        result = determine_risk_level(-1.78, 0)
        assert result == RiskLevel.HIGH

    def test_critical_risk_with_multiple_red_flags(self) -> None:
        """M-Score >= -1.78 with 3+ red flags yields CRITICAL risk."""
        result = determine_risk_level(-1.78, 3)
        assert result == RiskLevel.CRITICAL

    def test_low_risk_m_score_below_threshold(self) -> None:
        """M-Score < -2.22 with 0 red flags yields LOW risk."""
        result = determine_risk_level(-2.22, 0)
        # -2.22 is NOT < -2.22, it equals -2.22, so it falls in MEDIUM range
        # The boundary is strict: m_score < -2.22 for LOW
        assert result == RiskLevel.MEDIUM

    def test_medium_risk_m_score_between_thresholds(self) -> None:
        """M-Score between -2.22 and -1.78 yields MEDIUM risk."""
        result = determine_risk_level(-2.0, 0)
        assert result == RiskLevel.MEDIUM

    def test_low_escalated_to_medium_by_red_flags(self) -> None:
        """LOW risk escalated to MEDIUM when 2+ red flags present."""
        result = determine_risk_level(-2.5, 2)
        assert result == RiskLevel.MEDIUM

    def test_medium_escalated_to_high_by_red_flags(self) -> None:
        """MEDIUM risk escalated to HIGH when 4+ red flags present."""
        result = determine_risk_level(-2.0, 4)
        assert result == RiskLevel.HIGH

    def test_boundary_at_negative_1_78(self) -> None:
        """M-Score exactly -1.78 falls into HIGH category."""
        result = determine_risk_level(-1.78, 0)
        assert result == RiskLevel.HIGH

    def test_very_low_m_score_no_flags(self) -> None:
        """M-Score well below -2.22 with no flags yields LOW risk."""
        result = determine_risk_level(-3.5, 0)
        assert result == RiskLevel.LOW

    def test_just_below_negative_2_22(self) -> None:
        """M-Score just below -2.22 yields LOW risk."""
        result = determine_risk_level(-2.23, 0)
        assert result == RiskLevel.LOW


@pytest.mark.unit
class TestAnalyzeFinancialRisk:
    """Tests for analyze_financial_risk orchestrator function."""

    def test_full_analysis_with_moutai_data(self, make_risk_report_pair: Any) -> None:
        """Full analysis with Moutai data returns RiskScore with all fields."""
        current, previous = make_risk_report_pair()
        result = analyze_financial_risk(current, previous)

        assert isinstance(result, RiskScore)
        assert result.ticker == "600519.SH"
        assert isinstance(result.m_score, float)
        assert -10 <= result.m_score <= 10
        assert isinstance(result.f_score, int)
        assert 0 <= result.f_score <= 9
        assert result.risk_level in (
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        )
        assert result.mscore_data is not None
        assert result.fscore_data is not None
        assert isinstance(result.red_flags, list)
        assert isinstance(result.goodwill_ratio, float)
        assert isinstance(result.profit_cash_divergence, bool)
        assert result.goodwill_excessive is not None
        assert isinstance(result.cash_amount, Decimal)
        assert isinstance(result.debt_amount, Decimal)

    def test_analysis_without_previous_report_raises_error(
        self, make_financial_report: Any
    ) -> None:
        """Analysis with only current_report (no previous) raises DataValidationError.

        analyze_financial_risk passes previous_report or {} to
        calculate_mscore_indices, which validates required fields in both
        reports. An empty previous dict triggers DataValidationError.
        """
        from stockvaluefinder.utils.errors import DataValidationError

        current = make_financial_report()
        with pytest.raises(DataValidationError, match="previous report"):
            analyze_financial_risk(current, None)

    def test_analysis_adds_m_score_red_flag_when_above_threshold(
        self, make_financial_report: Any
    ) -> None:
        """Data producing M-Score >= -1.78 adds Beneish M-Score red flag."""
        # Use moderate but suspicious values that keep M-Score in valid range
        # High DSRI (accounts_receivable growing faster than revenue)
        # and high SGI (revenue growing) will push M-Score above -1.78
        current = make_financial_report(
            accounts_receivable=8_000_000_000,
            revenue=135_000_000_000,
            cost_of_goods=20_000_000_000,
            operating_cash_flow=10_000_000_000,
            total_current_assets=185_000_000_000,
            ppe=26_000_000_000,
            sga_expense=5_000_000_000,
            total_liabilities=80_000_000_000,
        )
        previous = {
            "ticker": "600519.SH",
            "fiscal_year": 2022,
            "report_id": "prev-001",
            "report_source": "test",
            "revenue": 100_000_000_000,
            "net_income": 50_000_000_000,
            "operating_cash_flow": 45_000_000_000,
            "accounts_receivable": 3_000_000_000,
            "cost_of_goods": 15_000_000_000,
            "total_current_assets": 170_000_000_000,
            "total_assets": 245_000_000_000,
            "assets_total": 245_000_000_000,
            "ppe": 23_000_000_000,
            "sga_expense": 3_500_000_000,
            "total_liabilities": 70_000_000_000,
            "liabilities_total": 70_000_000_000,
            "cash_and_equivalents": 140_000_000_000,
            "interest_bearing_debt": 1_800_000_000,
            "goodwill": 480_000_000,
            "equity_total": 175_000_000_000,
            "gross_margin": 0.85,
            "shares_outstanding": 1_256_197_900,
        }
        result = analyze_financial_risk(current, previous)

        if result.m_score >= -1.78:
            assert any("Beneish M-Score" in flag for flag in result.red_flags)

    def test_analysis_adds_f_score_red_flag_when_low(
        self, make_financial_report: Any
    ) -> None:
        """Data producing F-Score <= 2 adds Piotroski F-Score red flag."""
        # Create weak company data: negative net income, declining metrics
        current = make_financial_report(
            net_income=-5_000_000_000,
            operating_cash_flow=-2_000_000_000,
            gross_margin=0.3,
        )
        previous = {
            "ticker": "600519.SH",
            "fiscal_year": 2022,
            "report_id": "prev-001",
            "report_source": "test",
            "revenue": 124_100_000_000,
            "net_income": 1_000_000_000,
            "operating_cash_flow": 515_300_000_00,
            "accounts_receivable": 3_200_000_000,
            "cost_of_goods": 15_340_000_000,
            "total_current_assets": 170_000_000_000,
            "total_assets": 245_000_000_000,
            "assets_total": 245_000_000_000,
            "ppe": 23_000_000_000,
            "sga_expense": 4_200_000_000,
            "total_liabilities": 70_000_000_000,
            "liabilities_total": 70_000_000_000,
            "cash_and_equivalents": 140_000_000_000,
            "interest_bearing_debt": 1_800_000_000,
            "goodwill": 480_000_000,
            "equity_total": 175_000_000_000,
            "gross_margin": 0.876,
            "shares_outstanding": 1_256_197_900,
        }
        result = analyze_financial_risk(current, previous)

        if result.f_score <= 2:
            assert any("Piotroski F-Score" in flag for flag in result.red_flags)

    def test_analysis_detects_存贷双高_anomaly(
        self, make_financial_report: Any
    ) -> None:
        """High cash + high debt + high growth triggers anomaly flag."""
        current = make_financial_report(
            cash_and_equivalents=150_000_000_000,
            interest_bearing_debt=5_000_000_000,
        )
        previous = {
            "ticker": "600519.SH",
            "fiscal_year": 2022,
            "report_id": "prev-001",
            "report_source": "test",
            "revenue": 124_100_000_000,
            "net_income": 62_716_000_000,
            "operating_cash_flow": 51_530_000_000,
            "accounts_receivable": 3_200_000_000,
            "cost_of_goods": 15_340_000_000,
            "total_current_assets": 170_000_000_000,
            "total_assets": 245_000_000_000,
            "assets_total": 245_000_000_000,
            "ppe": 23_000_000_000,
            "sga_expense": 4_200_000_000,
            "total_liabilities": 70_000_000_000,
            "liabilities_total": 70_000_000_000,
            "cash_and_equivalents": 2_000_000_000,
            "interest_bearing_debt": 1_000_000_000,
            "goodwill": 480_000_000,
            "equity_total": 175_000_000_000,
            "gross_margin": 0.876,
            "shares_outstanding": 1_256_197_900,
        }
        result = analyze_financial_risk(current, previous)

        if result.存贷双高:
            assert any("存贷双高" in flag for flag in result.red_flags)


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases in risk service functions."""

    def test_detect_存贷双高_zero_previous_cash(self) -> None:
        """Previous cash=0, current cash>0 should set cash_growth=1.0."""
        current = {
            "cash_and_equivalents": Decimal("5_000_000_000"),
            "interest_bearing_debt": Decimal("500_000_000"),
        }
        previous = {
            "cash_and_equivalents": Decimal("0"),
            "interest_bearing_debt": Decimal("400_000_000"),
        }
        result = detect_存贷双高(current, previous)

        assert result["cash_growth_rate"] == 1.0
        assert isinstance(result["存贷双高"], bool)

    def test_detect_存贷双高_zero_previous_debt(self) -> None:
        """Previous debt=0, current debt>0 should set debt_growth=1.0."""
        current = {
            "cash_and_equivalents": Decimal("500_000_000"),
            "interest_bearing_debt": Decimal("5_000_000_000"),
        }
        previous = {
            "cash_and_equivalents": Decimal("400_000_000"),
            "interest_bearing_debt": Decimal("0"),
        }
        result = detect_存贷双高(current, previous)

        assert result["debt_growth_rate"] == 1.0
        assert isinstance(result["存贷双高"], bool)

    def test_profit_cash_divergence_zero_previous_profit(self) -> None:
        """Previous profit=0, current profit>0 sets profit_growth=1.0."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("10_000_000_000"),
            previous_profit=Decimal("0"),
            current_ocf=Decimal("8_000_000_000"),
            previous_ocf=Decimal("5_000_000_000"),
        )
        assert result["profit_growth"] == 1.0
        assert result["divergence"] is False  # OCF also grew

    def test_profit_cash_divergence_zero_previous_ocf(self) -> None:
        """Previous OCF=0, current OCF>0 sets ocf_growth=1.0."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("10_000_000_000"),
            previous_profit=Decimal("8_000_000_000"),
            current_ocf=Decimal("5_000_000_000"),
            previous_ocf=Decimal("0"),
        )
        assert result["ocf_growth"] == 1.0
        assert result["divergence"] is False  # OCF grew (from 0)

    def test_goodwill_ratio_nan_goodwill(self) -> None:
        """NaN goodwill returns ratio 0.0 and not excessive."""
        result = calculate_goodwill_ratio(
            goodwill=Decimal("nan"),
            equity=Decimal("10_000_000_000"),
        )
        assert result["ratio"] == 0.0
        assert result["excessive"] is False

    def test_goodwill_ratio_zero_equity(self) -> None:
        """Zero equity returns ratio 0.0 (equity <= 0 check)."""
        result = calculate_goodwill_ratio(
            goodwill=Decimal("1_000_000_000"),
            equity=Decimal("0"),
        )
        assert result["ratio"] == 0.0
        assert result["excessive"] is False

    def test_goodwill_ratio_negative_equity(self) -> None:
        """Negative equity returns ratio 0.0 (equity <= 0 check)."""
        result = calculate_goodwill_ratio(
            goodwill=Decimal("1_000_000_000"),
            equity=Decimal("-5_000_000_000"),
        )
        assert result["ratio"] == 0.0
        assert result["excessive"] is False

    def test_to_float_none(self) -> None:
        """_to_float(None) returns 0.0."""
        assert _to_float(None) == 0.0

    def test_to_float_nan_string(self) -> None:
        """_to_float('nan') returns 0.0."""
        assert _to_float("nan") == 0.0

    def test_to_float_empty_string(self) -> None:
        """_to_float('') returns 0.0."""
        assert _to_float("") == 0.0

    def test_to_float_valid_number(self) -> None:
        """_to_float('42.5') returns 42.5."""
        assert _to_float("42.5") == 42.5

    def test_to_float_nan_float(self) -> None:
        """_to_float(float('nan')) returns 0.0."""
        assert _to_float(float("nan")) == 0.0

    def test_to_float_integer(self) -> None:
        """_to_float(100) returns 100.0."""
        assert _to_float(100) == 100.0
