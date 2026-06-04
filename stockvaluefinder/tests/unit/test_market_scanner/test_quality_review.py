"""Unit tests for quality review gate (SCR-03).

Tests the review_stock_quality pure function that evaluates whether a
value-confirmed stock passes the quality bar before entering the
candidate list. Covers all 6 quality checks, graceful degradation,
and boundary conditions.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from stockvaluefinder.market_scanner.quality_review import (
    QualityReviewResult,
    review_stock_quality,
)
from stockvaluefinder.models.enums import RiskLevel, ValuationLevel, YieldRecommendation
from stockvaluefinder.models.risk import FScoreData, MScoreData, RiskScore
from stockvaluefinder.models.valuation import DCFParams, ValuationResult
from stockvaluefinder.models.yield_gap import YieldGap


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_mscore_data() -> MScoreData:
    """Create a default MScoreData instance for testing."""
    return MScoreData(
        dsri=1.0,
        gmi=1.0,
        aqi=1.0,
        sgi=1.0,
        depi=1.0,
        sgai=1.0,
        lvgi=1.0,
        tata=0.0,
    )


def _make_fscore_data() -> FScoreData:
    """Create a default FScoreData instance for testing."""
    return FScoreData(
        positive_roa=True,
        positive_cfo=True,
        improving_roa=True,
        cfo_exceeds_roa=True,
        lower_leverage=True,
        higher_liquidity=True,
        no_new_shares=True,
        improving_margin=True,
        improving_turnover=True,
    )


def _make_risk_score(
    m_score: float = -2.5,
    risk_level: RiskLevel = RiskLevel.LOW,
    profit_cash_divergence: bool = False,
    cun_dai_shuang_gao: bool = False,
    f_score: int = 7,
) -> RiskScore:
    """Create a RiskScore instance with configurable test parameters."""
    return RiskScore(
        score_id=uuid4(),
        calculated_at=datetime.now(timezone.utc),
        ticker="600519.SH",
        report_id=uuid4(),
        risk_level=risk_level,
        m_score=m_score,
        mscore_data=_make_mscore_data(),
        f_score=f_score,
        fscore_data=_make_fscore_data(),
        存贷双高=cun_dai_shuang_gao,
        cash_amount=Decimal("500000000"),
        debt_amount=Decimal("300000000"),
        cash_growth_rate=0.1,
        debt_growth_rate=0.05,
        goodwill_ratio=0.05,
        goodwill_excessive=False,
        profit_cash_divergence=profit_cash_divergence,
        profit_growth=0.15,
        ocf_growth=0.12,
        red_flags=[],
    )


def _make_valuation_result(
    margin_of_safety: float = 0.35,
    wacc: float = 0.08,
) -> ValuationResult:
    """Create a ValuationResult instance with configurable test parameters."""
    return ValuationResult(
        valuation_id=uuid4(),
        calculated_at=datetime.now(timezone.utc),
        ticker="600519.SH",
        current_price=Decimal("1800.00"),
        intrinsic_value=Decimal("2800.00"),
        wacc=wacc,
        margin_of_safety=margin_of_safety,
        valuation_level=ValuationLevel.UNDERVALUED,
        dcf_params=DCFParams(
            growth_rate_stage1=0.05,
            growth_rate_stage2=0.03,
            years_stage1=5,
            years_stage2=5,
            terminal_growth=0.025,
            risk_free_rate=0.03,
            beta=1.0,
            market_risk_premium=0.06,
        ),
        audit_trail={},
    )


def _make_yield_gap(yield_gap: float = 0.01) -> YieldGap:
    """Create a YieldGap instance with configurable test parameters."""
    return YieldGap(
        analysis_id=uuid4(),
        calculated_at=datetime.now(timezone.utc),
        ticker="600519.SH",
        cost_basis=Decimal("1800.00"),
        current_price=Decimal("1900.00"),
        gross_dividend_yield=0.03,
        net_dividend_yield=0.024,
        risk_free_bond_rate=0.028,
        risk_free_deposit_rate=0.025,
        yield_gap=yield_gap,
        recommendation=YieldRecommendation.ATTRACTIVE,
        market="A_SHARE",  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Tests: All checks pass
# ---------------------------------------------------------------------------


class TestAllPass:
    """Verify that a stock meeting all criteria passes quality review."""

    def test_all_pass(self) -> None:
        """Stock with all valid inputs should pass."""
        result = review_stock_quality(
            valuation_result=_make_valuation_result(),
            risk_score=_make_risk_score(),
            yield_gap=_make_yield_gap(),
            roic_wacc_spread=0.05,
        )

        assert result.passed is True
        assert result.failure_reasons == []
        assert result.checks_detail["roic_wacc_spread"] is True
        assert result.checks_detail["m_score"] is True
        assert result.checks_detail["cash_flow_divergence"] is True
        assert result.checks_detail["risk_level"] is True
        assert result.checks_detail["leverage"] is True
        assert result.checks_detail["dividend_sustainability"] is True


# ---------------------------------------------------------------------------
# Tests: Check 1 - ROIC-WACC spread
# ---------------------------------------------------------------------------


class TestROICWACCSpread:
    """Verify ROIC-WACC spread quality check."""

    def test_roic_wacc_negative(self) -> None:
        """Negative ROIC-WACC spread should fail."""
        result = review_stock_quality(
            roic_wacc_spread=-0.01,
        )

        assert result.passed is False
        assert any("ROIC-WACC" in r for r in result.failure_reasons)
        assert result.checks_detail["roic_wacc_spread"] is False

    def test_roic_wacc_zero(self) -> None:
        """Zero ROIC-WACC spread should fail (non-positive)."""
        result = review_stock_quality(
            roic_wacc_spread=0.0,
        )

        assert result.passed is False
        assert any("ROIC-WACC" in r for r in result.failure_reasons)
        assert result.checks_detail["roic_wacc_spread"] is False

    def test_roic_wacc_positive(self) -> None:
        """Positive ROIC-WACC spread should pass."""
        result = review_stock_quality(
            roic_wacc_spread=0.05,
        )

        assert result.passed is True
        assert result.checks_detail["roic_wacc_spread"] is True


# ---------------------------------------------------------------------------
# Tests: Check 2 - M-Score manipulation threshold
# ---------------------------------------------------------------------------


class TestMScoreThreshold:
    """Verify M-Score manipulation threshold check."""

    def test_mscore_above_threshold(self) -> None:
        """M-Score above -1.78 (e.g., -1.0) should fail."""
        risk = _make_risk_score(m_score=-1.0)
        result = review_stock_quality(risk_score=risk)

        assert result.passed is False
        assert any("M-Score" in r for r in result.failure_reasons)
        assert result.checks_detail["m_score"] is False

    def test_mscore_at_threshold(self) -> None:
        """M-Score exactly at -1.78 should fail (>= -1.78)."""
        risk = _make_risk_score(m_score=-1.78)
        result = review_stock_quality(risk_score=risk)

        assert result.passed is False
        assert any("M-Score" in r for r in result.failure_reasons)

    def test_mscore_below_threshold(self) -> None:
        """M-Score well below -1.78 (e.g., -2.5) should pass."""
        risk = _make_risk_score(m_score=-2.5)
        result = review_stock_quality(risk_score=risk)

        assert result.checks_detail["m_score"] is True


# ---------------------------------------------------------------------------
# Tests: Check 3 - Cash flow divergence
# ---------------------------------------------------------------------------


class TestCashFlowDivergence:
    """Verify cash flow divergence check."""

    def test_cash_flow_divergence_detected(self) -> None:
        """Profit-cash flow divergence should cause failure."""
        risk = _make_risk_score(profit_cash_divergence=True)
        result = review_stock_quality(risk_score=risk)

        assert result.passed is False
        assert any("divergence" in r.lower() for r in result.failure_reasons)
        assert result.checks_detail["cash_flow_divergence"] is False

    def test_no_cash_flow_divergence(self) -> None:
        """No divergence should pass."""
        risk = _make_risk_score(profit_cash_divergence=False)
        result = review_stock_quality(risk_score=risk)

        assert result.checks_detail["cash_flow_divergence"] is True


# ---------------------------------------------------------------------------
# Tests: Check 4 - Risk level gate
# ---------------------------------------------------------------------------


class TestRiskLevelGate:
    """Verify risk level quality check."""

    def test_risk_level_high(self) -> None:
        """HIGH risk level should fail."""
        risk = _make_risk_score(risk_level=RiskLevel.HIGH)
        result = review_stock_quality(risk_score=risk)

        assert result.passed is False
        assert any("Risk level" in r for r in result.failure_reasons)
        assert result.checks_detail["risk_level"] is False

    def test_risk_level_critical(self) -> None:
        """CRITICAL risk level should fail."""
        risk = _make_risk_score(risk_level=RiskLevel.CRITICAL)
        result = review_stock_quality(risk_score=risk)

        assert result.passed is False
        assert any("Risk level" in r for r in result.failure_reasons)
        assert result.checks_detail["risk_level"] is False

    def test_risk_level_medium(self) -> None:
        """MEDIUM risk level should pass (acceptable)."""
        risk = _make_risk_score(risk_level=RiskLevel.MEDIUM)
        result = review_stock_quality(risk_score=risk)

        assert result.checks_detail["risk_level"] is True

    def test_risk_level_low(self) -> None:
        """LOW risk level should pass."""
        risk = _make_risk_score(risk_level=RiskLevel.LOW)
        result = review_stock_quality(risk_score=risk)

        assert result.checks_detail["risk_level"] is True


# ---------------------------------------------------------------------------
# Tests: Check 5 - Leverage (cun-dai-shuang-gao)
# ---------------------------------------------------------------------------


class TestLeverage:
    """Verify leverage / cun-dai-shuang-gao check."""

    def test_leverage_cun_dai_shuang_gao(self) -> None:
        """High cash + high debt anomaly should fail."""
        risk = _make_risk_score(cun_dai_shuang_gao=True)
        result = review_stock_quality(risk_score=risk)

        assert result.passed is False
        assert any("cun-dai-shuang-gao" in r for r in result.failure_reasons)
        assert result.checks_detail["leverage"] is False

    def test_no_leverage_anomaly(self) -> None:
        """No leverage anomaly should pass."""
        risk = _make_risk_score(cun_dai_shuang_gao=False)
        result = review_stock_quality(risk_score=risk)

        assert result.checks_detail["leverage"] is True


# ---------------------------------------------------------------------------
# Tests: Check 6 - Dividend sustainability
# ---------------------------------------------------------------------------


class TestDividendSustainability:
    """Verify dividend sustainability check."""

    def test_dividend_unsustainable(self) -> None:
        """Yield gap below -0.02 should fail."""
        yg = _make_yield_gap(yield_gap=-0.03)
        result = review_stock_quality(yield_gap=yg)

        assert result.passed is False
        assert any(
            "dividend" in r.lower() or "yield" in r.lower()
            for r in result.failure_reasons
        )
        assert result.checks_detail["dividend_sustainability"] is False

    def test_dividend_marginal(self) -> None:
        """Yield gap exactly at -0.02 should pass (boundary)."""
        yg = _make_yield_gap(yield_gap=-0.02)
        result = review_stock_quality(yield_gap=yg)

        assert result.checks_detail["dividend_sustainability"] is True


# ---------------------------------------------------------------------------
# Tests: Graceful degradation (None inputs)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Verify graceful degradation when data sources are None."""

    def test_no_risk_score_graceful(self) -> None:
        """When risk_score is None, checks 2-5 should be recorded as True."""
        result = review_stock_quality(
            risk_score=None,
            roic_wacc_spread=0.05,
        )

        # Checks 2-5 should be True (graceful)
        assert result.checks_detail["m_score"] is True
        assert result.checks_detail["cash_flow_divergence"] is True
        assert result.checks_detail["risk_level"] is True
        assert result.checks_detail["leverage"] is True
        # Overall should pass (no failures)
        assert result.passed is True

    def test_no_yield_gap_graceful(self) -> None:
        """When yield_gap is None, check 6 should be recorded as True."""
        result = review_stock_quality(yield_gap=None)

        assert result.checks_detail["dividend_sustainability"] is True
        assert result.passed is True

    def test_no_roic_spread_graceful(self) -> None:
        """When roic_wacc_spread is None, check 1 should be recorded as True."""
        result = review_stock_quality(roic_wacc_spread=None)

        assert result.checks_detail["roic_wacc_spread"] is True
        assert result.passed is True

    def test_all_none_graceful(self) -> None:
        """All data sources None should result in passed=True (no failures)."""
        result = review_stock_quality(
            valuation_result=None,
            risk_score=None,
            yield_gap=None,
            roic_wacc_spread=None,
        )

        assert result.passed is True
        assert result.failure_reasons == []
        # All checks should be True (graceful degradation)
        assert all(v is True for v in result.checks_detail.values())


# ---------------------------------------------------------------------------
# Tests: Multiple failures and detail tracking
# ---------------------------------------------------------------------------


class TestMultipleFailures:
    """Verify handling of multiple simultaneous failures."""

    def test_multiple_failures(self) -> None:
        """Multiple failing checks should all be listed in failure_reasons."""
        risk = _make_risk_score(
            m_score=-1.0,  # fails M-Score check
            risk_level=RiskLevel.HIGH,  # fails risk level check
            profit_cash_divergence=True,  # fails cash flow check
            cun_dai_shuang_gao=True,  # fails leverage check
        )
        yg = _make_yield_gap(yield_gap=-0.05)  # fails dividend sustainability

        result = review_stock_quality(
            risk_score=risk,
            yield_gap=yg,
            roic_wacc_spread=-0.01,  # fails ROIC-WACC check
        )

        assert result.passed is False
        assert len(result.failure_reasons) == 6
        assert result.checks_detail["roic_wacc_spread"] is False
        assert result.checks_detail["m_score"] is False
        assert result.checks_detail["cash_flow_divergence"] is False
        assert result.checks_detail["risk_level"] is False
        assert result.checks_detail["leverage"] is False
        assert result.checks_detail["dividend_sustainability"] is False

    def test_checks_detail_populated(self) -> None:
        """checks_detail should have all 6 check names with bool values."""
        result = review_stock_quality(
            risk_score=_make_risk_score(),
            yield_gap=_make_yield_gap(),
            roic_wacc_spread=0.05,
        )

        expected_keys = {
            "roic_wacc_spread",
            "m_score",
            "cash_flow_divergence",
            "risk_level",
            "leverage",
            "dividend_sustainability",
        }
        assert set(result.checks_detail.keys()) == expected_keys
        assert all(isinstance(v, bool) for v in result.checks_detail.values())


# ---------------------------------------------------------------------------
# Tests: Model immutability
# ---------------------------------------------------------------------------


class TestQualityReviewResultModel:
    """Verify QualityReviewResult Pydantic model properties."""

    def test_frozen_model(self) -> None:
        """QualityReviewResult should be frozen (immutable)."""
        result = review_stock_quality()
        with pytest.raises(Exception):
            result.passed = False  # type: ignore[misc]

    def test_default_failure_reasons(self) -> None:
        """QualityReviewResult should default to empty failure_reasons."""
        result = QualityReviewResult(passed=True)
        assert result.failure_reasons == []

    def test_default_checks_detail(self) -> None:
        """QualityReviewResult should default to empty checks_detail."""
        result = QualityReviewResult(passed=True)
        assert result.checks_detail == {}
