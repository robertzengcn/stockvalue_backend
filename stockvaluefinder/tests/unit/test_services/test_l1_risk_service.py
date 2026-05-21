"""L1 formula verification tests for risk_service pure calculate_* functions.

These tests verify mathematical correctness of financial risk analysis
formulas against published paper reference values and hand-computed
boundary conditions. They serve as CI gates that catch formula regressions.

Reference:
    - Beneish, M. D. (1999). The detection of earnings manipulation.
      Financial Analysts Journal, 55(5), 24-36.
    - Piotroski, J. D. (2000). Value investing: The use of historical
      financial statement information to separate winners from losers.
      Journal of Accounting Research, 38, 1-41.
"""

from decimal import Decimal

import pytest

from stockvaluefinder.models.enums import RiskLevel
from stockvaluefinder.services.risk_service import (
    calculate_beneish_m_score,
    calculate_goodwill_ratio,
    calculate_mscore_indices,
    calculate_piotroski_f_score,
    detect_profit_cash_divergence,
    determine_risk_level,
)
from stockvaluefinder.services.risk_service import (
    detect_存贷双高 as detect_cundai_shuanggao,
)
from stockvaluefinder.validation.comparators import compare_within_tolerance
from stockvaluefinder.validation.schema import Tolerance


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MSCORE_ABS_TOL = Tolerance(absolute=0.05)


def _make_mscore_reports() -> tuple[dict, dict]:
    """Return (current_report, previous_report) with all required M-Score fields.

    Values are chosen so each sub-index has a hand-verifiable expected result:
        DSRI = (200/1000) / (150/900) = 0.2 / 0.1667 = 1.2
        GMI  = ((900-500)/900) / ((1000-600)/1000) = 0.4444 / 0.4 = 1.1111
        AQI  = (1-(500-300)/2000) / (1-(400-250)/1800) = 0.9 / 0.9167 = 0.9818
        SGI  = 1000 / 900 = 1.1111
        DEPI = 1.0 (MVP hardcoded)
        SGAI = (80/1000) / (60/900) = 0.08 / 0.0667 = 1.2
        LVGI = (800/2000) / (700/1800) = 0.4 / 0.3889 = 1.0286
        TATA = (100-60)/2000 = 0.02
    """
    current = {
        "accounts_receivable": 200,
        "revenue": 1000,
        "cost_of_goods": 600,
        "total_current_assets": 500,
        "ppe": 300,
        "total_assets": 2000,
        "sga_expense": 80,
        "total_liabilities": 800,
        "net_income": 100,
        "operating_cash_flow": 60,
    }
    previous = {
        "accounts_receivable": 150,
        "revenue": 900,
        "cost_of_goods": 500,
        "total_current_assets": 400,
        "ppe": 250,
        "total_assets": 1800,
        "sga_expense": 60,
        "total_liabilities": 700,
        "net_income": 80,
        "operating_cash_flow": 50,
    }
    return current, previous


# ===================================================================
# Test class: Beneish M-Score composite from pre-computed indices
# ===================================================================


@pytest.mark.l1_formula
class TestL1BeneishMScoreComposite:
    """Verify composite M-Score against Beneish (1999) Table 3 reference.

    Reference: Beneish, M. D. (1999). The detection of earnings manipulation.
    Financial Analysts Journal, 55(5), 24-36, Table 3.

    M-Score = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI
              + 0.892*SGI + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI

    With the given sub-indices:
        Expected M-Score = -4.84 + 0.92*1.465 + 0.528*1.193 + 0.404*1.254
                           + 0.892*1.134 + 0.115*0.974 - 0.172*0.685
                           + 4.679*0.032 - 0.327*0.945
                         = -1.509  (formula-derived)

    NOTE: The metric_registry.yaml lists expected -2.22 for the same inputs,
    which is incorrect. The L1 test uses the formula-derived value -1.509.
    """

    def test_composite_m_score_within_tolerance(self) -> None:
        """Composite M-Score matches formula-derived value within abs 0.05."""
        current = {
            "days_sales_receivables_index": 1.465,
            "gross_margin_index": 1.193,
            "asset_quality_index": 1.254,
            "sales_growth_index": 1.134,
            "depreciation_index": 0.974,
            "sga_expense_index": 0.685,
            "leverage_index": 0.945,
            "total_accruals_to_assets": 0.032,
        }
        result = calculate_beneish_m_score(current, {})
        expected_m_score = -1.509

        cmp = compare_within_tolerance(
            expected_m_score, result["m_score"], _MSCORE_ABS_TOL
        )
        assert cmp.passed, (
            f"M-Score expected {expected_m_score}, got {result['m_score']}, "
            f"delta={cmp.delta:.4f} exceeds tolerance 0.05"
        )

    def test_sub_indices_pass_through(self) -> None:
        """Each returned sub-index equals the input value (pass-through)."""
        inputs = {
            "days_sales_receivables_index": 1.465,
            "gross_margin_index": 1.193,
            "asset_quality_index": 1.254,
            "sales_growth_index": 1.134,
            "depreciation_index": 0.974,
            "sga_expense_index": 0.685,
            "leverage_index": 0.945,
            "total_accruals_to_assets": 0.032,
        }
        result = calculate_beneish_m_score(inputs, {})

        key_map = {
            "days_sales_receivables_index": "dsri",
            "gross_margin_index": "gmi",
            "asset_quality_index": "aqi",
            "sales_growth_index": "sgi",
            "depreciation_index": "depi",
            "sga_expense_index": "sgai",
            "leverage_index": "lvgi",
            "total_accruals_to_assets": "tata",
        }
        for input_key, output_key in key_map.items():
            assert result[output_key] == round(inputs[input_key], 4), (
                f"Sub-index {output_key}: expected {inputs[input_key]}, "
                f"got {result[output_key]}"
            )


# ===================================================================
# Test class: M-Score sub-indices from raw financials
# ===================================================================


@pytest.mark.l1_formula
class TestL1MScoreIndices:
    """Verify each M-Score sub-index against hand-computed values.

    Reference: Beneish, M. D. (1999). The detection of earnings manipulation.
    Financial Analysts Journal, 55(5), 24-36.
    """

    def test_dsri(self) -> None:
        """DSRI = (AR_t/Rev_t) / (AR_t-1/Rev_t-1) = 1.2.

        (200/1000) / (150/900) = 0.2 / 0.1667 = 1.2
        """
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        cmp = compare_within_tolerance(1.2, result["dsri"], _MSCORE_ABS_TOL)
        assert cmp.passed, (
            f"DSRI expected 1.2, got {result['dsri']}, delta={cmp.delta:.4f}"
        )

    def test_gmi(self) -> None:
        """GMI = GM_prev / GM_curr = 0.4444 / 0.4 = 1.1111.

        GM_curr = (1000-600)/1000 = 0.4
        GM_prev = (900-500)/900 = 0.4444
        """
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        cmp = compare_within_tolerance(1.1111, result["gmi"], _MSCORE_ABS_TOL)
        assert cmp.passed, (
            f"GMI expected 1.1111, got {result['gmi']}, delta={cmp.delta:.4f}"
        )

    def test_aqi(self) -> None:
        """AQI = AQ_curr / AQ_prev = 0.9 / 0.9167 = 0.9818.

        AQ_curr = 1 - (500-300)/2000 = 0.9
        AQ_prev = 1 - (400-250)/1800 = 0.9167
        """
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        cmp = compare_within_tolerance(0.9818, result["aqi"], _MSCORE_ABS_TOL)
        assert cmp.passed, (
            f"AQI expected 0.9818, got {result['aqi']}, delta={cmp.delta:.4f}"
        )

    def test_sgi(self) -> None:
        """SGI = Rev_t / Rev_t-1 = 1000 / 900 = 1.1111."""
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        cmp = compare_within_tolerance(1.1111, result["sgi"], _MSCORE_ABS_TOL)
        assert cmp.passed, (
            f"SGI expected 1.1111, got {result['sgi']}, delta={cmp.delta:.4f}"
        )

    def test_depi(self) -> None:
        """DEPI is hardcoded to 1.0 (MVP simplification, per D-05)."""
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        assert result["depi"] == 1.0, (
            f"DEPI expected 1.0 (MVP hardcoded), got {result['depi']}"
        )

    def test_sgai(self) -> None:
        """SGAI = (SGA_t/Rev_t) / (SGA_t-1/Rev_t-1) = 1.2.

        (80/1000) / (60/900) = 0.08 / 0.0667 = 1.2
        """
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        cmp = compare_within_tolerance(1.2, result["sgai"], _MSCORE_ABS_TOL)
        assert cmp.passed, (
            f"SGAI expected 1.2, got {result['sgai']}, delta={cmp.delta:.4f}"
        )

    def test_lvgi(self) -> None:
        """LVGI = (TL_t/TA_t) / (TL_t-1/TA_t-1) = 1.0286.

        (800/2000) / (700/1800) = 0.4 / 0.3889 = 1.0286
        """
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        cmp = compare_within_tolerance(1.0286, result["lvgi"], _MSCORE_ABS_TOL)
        assert cmp.passed, (
            f"LVGI expected 1.0286, got {result['lvgi']}, delta={cmp.delta:.4f}"
        )

    def test_tata(self) -> None:
        """TATA = (NI_t - OCF_t) / TA_t = (100-60)/2000 = 0.02."""
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        cmp = compare_within_tolerance(0.02, result["tata"], _MSCORE_ABS_TOL)
        assert cmp.passed, (
            f"TATA expected 0.02, got {result['tata']}, delta={cmp.delta:.4f}"
        )

    def test_no_non_calculable_with_valid_data(self) -> None:
        """All indices should be calculable with valid input data."""
        current, previous = _make_mscore_reports()
        result = calculate_mscore_indices(current, previous, source_name="test")
        assert result["non_calculable"] == [], (
            f"Expected no non-calculable indices, got: {result['non_calculable']}"
        )


# ===================================================================
# Test class: Piotroski F-Score 9 binary components
# ===================================================================


@pytest.mark.l1_formula
class TestL1PiotroskiFScore:
    """Verify all 9 F-Score binary components at boundary conditions.

    Reference: Piotroski, J. D. (2000). Value investing: The use of
    historical financial statement information to separate winners from
    losers. Journal of Accounting Research, 38, 1-41.
    """

    def test_positive_roa_score_1(self) -> None:
        """positive_roa = 1 when ROA > 0 (net_income=100, assets=1000 => ROA=0.1)."""
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "net_income": 100},
            {"assets_total": 1000, "net_income": 80},
        )
        assert result["positive_roa"] is True

    def test_positive_roa_score_0(self) -> None:
        """positive_roa = 0 when ROA < 0 (net_income=-50, assets=1000 => ROA=-0.05)."""
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "net_income": -50},
            {"assets_total": 1000, "net_income": 80},
        )
        assert result["positive_roa"] is False

    def test_positive_cfo_score_1(self) -> None:
        """positive_cfo = 1 when operating_cash_flow > 0."""
        result = calculate_piotroski_f_score(
            {"operating_cash_flow": 200, "assets_total": 1000},
            {"assets_total": 1000},
        )
        assert result["positive_cfo"] is True

    def test_positive_cfo_score_0(self) -> None:
        """positive_cfo = 0 when operating_cash_flow < 0."""
        result = calculate_piotroski_f_score(
            {"operating_cash_flow": -100, "assets_total": 1000},
            {"assets_total": 1000},
        )
        assert result["positive_cfo"] is False

    def test_improving_roa_score_1(self) -> None:
        """improving_roa = 1 when current ROA > previous ROA.

        current: NI=150, assets=1000 => ROA=0.15
        previous: NI=100, assets=1000 => ROA=0.10
        """
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "net_income": 150},
            {"assets_total": 1000, "net_income": 100},
        )
        assert result["improving_roa"] is True

    def test_improving_roa_score_0(self) -> None:
        """improving_roa = 0 when current ROA < previous ROA."""
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "net_income": 80},
            {"assets_total": 1000, "net_income": 100},
        )
        assert result["improving_roa"] is False

    def test_cfo_exceeds_roa_score_1(self) -> None:
        """cfo_exceeds_roa = 1 when CFO/assets > ROA.

        CFO=200, assets=1000 => CFO ratio=0.2
        NI=100, assets=1000 => ROA=0.1
        """
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "net_income": 100, "operating_cash_flow": 200},
            {"assets_total": 1000, "net_income": 80},
        )
        assert result["cfo_exceeds_roa"] is True

    def test_cfo_exceeds_roa_score_0(self) -> None:
        """cfo_exceeds_roa = 0 when CFO/assets < ROA."""
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "net_income": 200, "operating_cash_flow": 50},
            {"assets_total": 1000, "net_income": 80},
        )
        assert result["cfo_exceeds_roa"] is False

    def test_lower_leverage_score_1(self) -> None:
        """lower_leverage = 1 when debt/assets decreases YoY.

        current: debt=300, assets=1000 => 0.3
        previous: debt=400, assets=1000 => 0.4
        """
        result = calculate_piotroski_f_score(
            {
                "assets_total": 1000,
                "long_term_debt": 300,
            },
            {
                "assets_total": 1000,
                "long_term_debt": 400,
            },
        )
        assert result["lower_leverage"] is True

    def test_lower_leverage_score_0(self) -> None:
        """lower_leverage = 0 when debt/assets increases YoY."""
        result = calculate_piotroski_f_score(
            {
                "assets_total": 1000,
                "long_term_debt": 500,
            },
            {
                "assets_total": 1000,
                "long_term_debt": 400,
            },
        )
        assert result["lower_leverage"] is False

    def test_higher_liquidity_score_1(self) -> None:
        """higher_liquidity = 1 when cash/liabilities increases YoY.

        current: cash=300, liabilities=1000 => 0.3
        previous: cash=200, liabilities=1000 => 0.2
        """
        result = calculate_piotroski_f_score(
            {
                "assets_total": 1000,
                "cash_and_equivalents": 300,
                "liabilities_total": 1000,
            },
            {
                "assets_total": 1000,
                "cash_and_equivalents": 200,
                "liabilities_total": 1000,
            },
        )
        assert result["higher_liquidity"] is True

    def test_higher_liquidity_score_0(self) -> None:
        """higher_liquidity = 0 when cash/liabilities decreases YoY."""
        result = calculate_piotroski_f_score(
            {
                "assets_total": 1000,
                "cash_and_equivalents": 100,
                "liabilities_total": 1000,
            },
            {
                "assets_total": 1000,
                "cash_and_equivalents": 200,
                "liabilities_total": 1000,
            },
        )
        assert result["higher_liquidity"] is False

    def test_no_new_shares_score_1(self) -> None:
        """no_new_shares = 1 when shares outstanding stays same or decreases."""
        result = calculate_piotroski_f_score(
            {
                "assets_total": 1000,
                "shares_outstanding": 900,
            },
            {
                "assets_total": 1000,
                "shares_outstanding": 1000,
            },
        )
        assert result["no_new_shares"] is True

    def test_no_new_shares_score_0(self) -> None:
        """no_new_shares = 0 when shares outstanding increases."""
        result = calculate_piotroski_f_score(
            {
                "assets_total": 1000,
                "shares_outstanding": 1100,
            },
            {
                "assets_total": 1000,
                "shares_outstanding": 1000,
            },
        )
        assert result["no_new_shares"] is False

    def test_improving_margin_score_1(self) -> None:
        """improving_margin = 1 when gross_margin increases."""
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "gross_margin": 0.45},
            {"assets_total": 1000, "gross_margin": 0.40},
        )
        assert result["improving_margin"] is True

    def test_improving_margin_score_0(self) -> None:
        """improving_margin = 0 when gross_margin decreases."""
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "gross_margin": 0.35},
            {"assets_total": 1000, "gross_margin": 0.40},
        )
        assert result["improving_margin"] is False

    def test_improving_turnover_score_1(self) -> None:
        """improving_turnover = 1 when revenue/assets increases.

        current: revenue=1200, assets=1000 => 1.2
        previous: revenue=1000, assets=1000 => 1.0
        """
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "revenue": 1200},
            {"assets_total": 1000, "revenue": 1000},
        )
        assert result["improving_turnover"] is True

    def test_improving_turnover_score_0(self) -> None:
        """improving_turnover = 0 when revenue/assets decreases."""
        result = calculate_piotroski_f_score(
            {"assets_total": 1000, "revenue": 800},
            {"assets_total": 1000, "revenue": 1000},
        )
        assert result["improving_turnover"] is False

    def test_perfect_company_f_score_9(self) -> None:
        """A perfect company should score F-Score = 9.

        All 9 signals true: positive ROA, positive CFO, improving ROA,
        CFO > ROA, lower leverage, higher liquidity, no new shares,
        improving margin, improving turnover.
        """
        current = {
            "assets_total": 1000,
            "net_income": 200,  # positive ROA (0.2)
            "operating_cash_flow": 300,  # positive CFO, CFO/assets > ROA
            "long_term_debt": 200,  # lower leverage than prev (0.2 < 0.3)
            "cash_and_equivalents": 500,  # higher liquidity (0.5 > 0.3)
            "liabilities_total": 1000,
            "shares_outstanding": 900,  # no new shares (900 <= 1000)
            "gross_margin": 0.50,  # improving margin (0.5 > 0.4)
            "revenue": 1200,  # improving turnover (1.2 > 1.0)
        }
        previous = {
            "assets_total": 1000,
            "net_income": 100,  # ROA=0.1 < current 0.2
            "operating_cash_flow": 200,
            "long_term_debt": 300,  # leverage=0.3 > current 0.2
            "cash_and_equivalents": 300,  # liquidity=0.3 < current 0.5
            "liabilities_total": 1000,
            "shares_outstanding": 1000,  # shares increased
            "gross_margin": 0.40,  # margin lower
            "revenue": 1000,  # turnover lower
        }
        result = calculate_piotroski_f_score(current, previous)
        assert result["f_score"] == 9, (
            f"Perfect company expected F-Score=9, got {result['f_score']}. "
            f"Signals: {result}"
        )

    def test_worst_company_f_score_0(self) -> None:
        """A worst company should score F-Score = 0.

        All 9 signals false: negative ROA, negative CFO, declining ROA,
        CFO < ROA, higher leverage, lower liquidity, new shares issued,
        declining margin, declining turnover.
        """
        current = {
            "assets_total": 1000,
            "net_income": -50,  # negative ROA (-0.05)
            "operating_cash_flow": -100,  # negative CFO
            "long_term_debt": 500,  # higher leverage than prev (0.5 > 0.3)
            "cash_and_equivalents": 100,  # lower liquidity (0.1 < 0.3)
            "liabilities_total": 1000,
            "shares_outstanding": 1200,  # new shares issued (1200 > 1000)
            "gross_margin": 0.30,  # declining margin (0.3 < 0.4)
            "revenue": 800,  # declining turnover (0.8 < 1.0)
        }
        previous = {
            "assets_total": 1000,
            "net_income": 100,  # ROA=0.1 > current -0.05
            "operating_cash_flow": 200,
            "long_term_debt": 300,  # leverage=0.3 < current 0.5
            "cash_and_equivalents": 300,  # liquidity=0.3 > current 0.1
            "liabilities_total": 1000,
            "shares_outstanding": 1000,
            "gross_margin": 0.40,  # margin higher
            "revenue": 1000,  # turnover higher
        }
        result = calculate_piotroski_f_score(current, previous)
        assert result["f_score"] == 0, (
            f"Worst company expected F-Score=0, got {result['f_score']}. "
            f"Signals: {result}"
        )


# ===================================================================
# Test class: detect_存贷双高 (high cash + high debt anomaly)
# ===================================================================


@pytest.mark.l1_formula
class TestL1CunDaiShuangGao:
    """Verify detect_存贷双高 at 1 billion / 50% growth thresholds.

    The function flags anomaly when:
    - cash > 1B AND debt > 1B AND (cash_growth > 50% OR debt_growth > 50%)
    """

    def test_anomaly_triggered(self) -> None:
        """Both cash and debt > 1B, both growing 100%. Anomaly flagged."""
        result = detect_cundai_shuanggao(
            {
                "cash_and_equivalents": 2_000_000_000,
                "interest_bearing_debt": 2_000_000_000,
            },
            {
                "cash_and_equivalents": 1_000_000_000,
                "interest_bearing_debt": 1_000_000_000,
            },
        )
        assert result["存贷双高"] is True

    def test_no_anomaly_low_amounts(self) -> None:
        """Cash and debt below 1B threshold. No anomaly."""
        result = detect_cundai_shuanggao(
            {"cash_and_equivalents": 500_000_000, "interest_bearing_debt": 500_000_000},
            {"cash_and_equivalents": 250_000_000, "interest_bearing_debt": 250_000_000},
        )
        assert result["存贷双高"] is False

    def test_no_anomaly_high_amounts_low_growth(self) -> None:
        """Cash and debt > 1B but growth ~5% (< 50%). No anomaly."""
        result = detect_cundai_shuanggao(
            {
                "cash_and_equivalents": 2_000_000_000,
                "interest_bearing_debt": 2_000_000_000,
            },
            {
                "cash_and_equivalents": 1_900_000_000,
                "interest_bearing_debt": 1_900_000_000,
            },
        )
        assert result["存贷双高"] is False

    def test_asymmetric_or_case(self) -> None:
        """Cash growth high but debt growth low. OR logic triggers anomaly.

        current cash=2B, debt=2B, previous cash=1B, debt=1.9B
        cash_growth = 100% (> 50%), debt_growth ~ 5.3% (< 50%)
        """
        result = detect_cundai_shuanggao(
            {
                "cash_and_equivalents": 2_000_000_000,
                "interest_bearing_debt": 2_000_000_000,
            },
            {
                "cash_and_equivalents": 1_000_000_000,
                "interest_bearing_debt": 1_900_000_000,
            },
        )
        assert result["存贷双高"] is True

    def test_cash_growth_rate_value(self) -> None:
        """Verify cash growth rate computation within abs 0.01."""
        result = detect_cundai_shuanggao(
            {
                "cash_and_equivalents": 2_000_000_000,
                "interest_bearing_debt": 2_000_000_000,
            },
            {
                "cash_and_equivalents": 1_000_000_000,
                "interest_bearing_debt": 1_000_000_000,
            },
        )
        tol = Tolerance(absolute=0.01)
        cmp = compare_within_tolerance(1.0, result["cash_growth_rate"], tol)
        assert cmp.passed, (
            f"Cash growth rate expected 1.0, got {result['cash_growth_rate']}, "
            f"delta={cmp.delta:.4f}"
        )

    def test_debt_growth_rate_value(self) -> None:
        """Verify debt growth rate computation within abs 0.01."""
        result = detect_cundai_shuanggao(
            {
                "cash_and_equivalents": 2_000_000_000,
                "interest_bearing_debt": 2_000_000_000,
            },
            {
                "cash_and_equivalents": 1_000_000_000,
                "interest_bearing_debt": 1_000_000_000,
            },
        )
        tol = Tolerance(absolute=0.01)
        cmp = compare_within_tolerance(1.0, result["debt_growth_rate"], tol)
        assert cmp.passed, (
            f"Debt growth rate expected 1.0, got {result['debt_growth_rate']}, "
            f"delta={cmp.delta:.4f}"
        )


# ===================================================================
# Test class: calculate_goodwill_ratio
# ===================================================================


@pytest.mark.l1_formula
class TestL1GoodwillRatio:
    """Verify calculate_goodwill_ratio at the 30% excessive boundary."""

    def test_ratio_30_percent_not_excessive(self) -> None:
        """goodwill=300M, equity=1000M => ratio=0.3, NOT excessive (<= 30%)."""
        result = calculate_goodwill_ratio(Decimal("300000000"), Decimal("1000000000"))
        assert result["ratio"] == 0.3, f"Expected ratio 0.3, got {result['ratio']}"
        assert result["excessive"] is False, (
            "30% should NOT be excessive (>30% triggers)"
        )

    def test_ratio_31_percent_excessive(self) -> None:
        """goodwill=310M, equity=1000M => ratio=0.31, excessive (> 30%)."""
        result = calculate_goodwill_ratio(Decimal("310000000"), Decimal("1000000000"))
        assert result["ratio"] == 0.31, f"Expected ratio 0.31, got {result['ratio']}"
        assert result["excessive"] is True, "31% should be excessive"

    def test_zero_goodwill(self) -> None:
        """goodwill=0, equity=1000M => ratio=0.0, not excessive."""
        result = calculate_goodwill_ratio(Decimal("0"), Decimal("1000000000"))
        assert result["ratio"] == 0.0, f"Expected ratio 0.0, got {result['ratio']}"
        assert result["excessive"] is False

    def test_zero_equity_edge_case(self) -> None:
        """goodwill=100M, equity=0 => ratio=0.0, not excessive (zero equity guard)."""
        result = calculate_goodwill_ratio(Decimal("100000000"), Decimal("0"))
        assert result["ratio"] == 0.0, f"Expected ratio 0.0, got {result['ratio']}"
        assert result["excessive"] is False


# ===================================================================
# Test class: detect_profit_cash_divergence
# ===================================================================


@pytest.mark.l1_formula
class TestL1ProfitCashDivergence:
    """Verify detect_profit_cash_divergence with growth/decline scenarios."""

    def test_divergence_detected(self) -> None:
        """Profit grows 50% but OCF declines 20%. Divergence flagged.

        profit: 100 -> 150 = +50%
        OCF: 200 -> 160 = -20%
        """
        result = detect_profit_cash_divergence(
            current_profit=Decimal("150"),
            previous_profit=Decimal("100"),
            current_ocf=Decimal("160"),
            previous_ocf=Decimal("200"),
        )
        assert result["divergence"] is True

    def test_no_divergence_both_grow(self) -> None:
        """Both profit and OCF grow. No divergence."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("150"),
            previous_profit=Decimal("100"),
            current_ocf=Decimal("220"),
            previous_ocf=Decimal("200"),
        )
        assert result["divergence"] is False

    def test_no_divergence_both_decline(self) -> None:
        """Both profit and OCF decline. No divergence."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("80"),
            previous_profit=Decimal("100"),
            current_ocf=Decimal("160"),
            previous_ocf=Decimal("200"),
        )
        assert result["divergence"] is False

    def test_profit_growth_value(self) -> None:
        """Verify profit growth rate matches hand-computed 0.5 (50%)."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("150"),
            previous_profit=Decimal("100"),
            current_ocf=Decimal("160"),
            previous_ocf=Decimal("200"),
        )
        tol = Tolerance(absolute=0.01)
        cmp = compare_within_tolerance(0.5, result["profit_growth"], tol)
        assert cmp.passed, (
            f"Profit growth expected 0.5, got {result['profit_growth']}, "
            f"delta={cmp.delta:.4f}"
        )

    def test_ocf_growth_value(self) -> None:
        """Verify OCF growth rate matches hand-computed -0.2 (-20%)."""
        result = detect_profit_cash_divergence(
            current_profit=Decimal("150"),
            previous_profit=Decimal("100"),
            current_ocf=Decimal("160"),
            previous_ocf=Decimal("200"),
        )
        tol = Tolerance(absolute=0.01)
        cmp = compare_within_tolerance(-0.2, result["ocf_growth"], tol)
        assert cmp.passed, (
            f"OCF growth expected -0.2, got {result['ocf_growth']}, "
            f"delta={cmp.delta:.4f}"
        )


# ===================================================================
# Test class: determine_risk_level
# ===================================================================


@pytest.mark.l1_formula
class TestL1DetermineRiskLevel:
    """Verify determine_risk_level at M-Score and red flag boundaries.

    Thresholds:
        - M-Score >= -1.78: HIGH (or CRITICAL with 3+ red flags)
        - M-Score < -2.22: LOW
        - Otherwise: MEDIUM
    Adjustments:
        - LOW + 2+ red flags -> MEDIUM
        - MEDIUM + 4+ red flags -> HIGH
    """

    def test_high_risk_no_flags(self) -> None:
        """M-Score >= -1.78, 0 red flags => HIGH."""
        assert determine_risk_level(-1.78, 0) == RiskLevel.HIGH

    def test_critical_risk_many_flags(self) -> None:
        """M-Score >= -1.78, 3 red flags => CRITICAL."""
        assert determine_risk_level(-1.78, 3) == RiskLevel.CRITICAL

    def test_low_risk(self) -> None:
        """M-Score < -2.22, 0 red flags => LOW."""
        assert determine_risk_level(-2.5, 0) == RiskLevel.LOW

    def test_medium_risk(self) -> None:
        """M-Score between -2.22 and -1.78 => MEDIUM."""
        assert determine_risk_level(-2.0, 0) == RiskLevel.MEDIUM

    def test_low_upgraded_to_medium(self) -> None:
        """LOW with >= 2 red flags => upgraded to MEDIUM."""
        assert determine_risk_level(-2.5, 2) == RiskLevel.MEDIUM

    def test_medium_upgraded_to_high(self) -> None:
        """MEDIUM with >= 4 red flags => upgraded to HIGH."""
        assert determine_risk_level(-2.0, 4) == RiskLevel.HIGH
