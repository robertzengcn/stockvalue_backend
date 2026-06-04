"""Tests for deterministic reason generator (SCR-06).

Tests verify that generate_reasons() produces structured selection reasons
and risk flags from computed metrics using deterministic templates with
actual metric values. No LLM involvement.

Compliance requirement: Every candidate must have at least one risk flag.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4


from stockvaluefinder.market_scanner.models import (
    CompositeScore,
    CompositeScoreComponents,
)
from stockvaluefinder.market_scanner.reason_generator import generate_reasons
from stockvaluefinder.models.enums import (
    RiskLevel,
    ValuationLevel,
    YieldRecommendation,
    Market,
)
from stockvaluefinder.models.risk import RiskScore
from stockvaluefinder.models.valuation import ValuationResult
from stockvaluefinder.models.yield_gap import YieldGap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_composite(composite: float = 75.0) -> CompositeScore:
    """Create a CompositeScore with sensible defaults."""
    return CompositeScore(
        composite=composite,
        components=CompositeScoreComponents(
            safety_margin=50.0,
            alpha=50.0,
            risk_penalty=50.0,
            yield_gap=50.0,
            valuation_percentile=50.0,
        ),
        passed_threshold=composite >= 60.0,
    )


def _make_risk_score(
    risk_level: RiskLevel = RiskLevel.LOW,
    m_score: float = -2.50,
    f_score: int = 7,
    red_flags: list[str] | None = None,
    profit_cash_divergence: bool = False,
    goodwill_excessive: bool = False,
    存贷双高: bool = False,
) -> RiskScore:
    """Create a RiskScore with configurable fields."""
    from stockvaluefinder.models.risk import MScoreData, FScoreData

    return RiskScore(
        score_id=uuid4(),
        calculated_at=datetime(2024, 1, 15),
        ticker="600519.SH",
        report_id=uuid4(),
        risk_level=risk_level,
        m_score=m_score,
        mscore_data=MScoreData(
            dsri=1.0,
            gmi=1.0,
            aqi=1.0,
            sgi=1.0,
            depi=1.0,
            sgai=1.0,
            lvgi=1.0,
            tata=0.0,
        ),
        f_score=f_score,
        fscore_data=FScoreData(
            positive_roa=True,
            positive_cfo=True,
            improving_roa=True,
            cfo_exceeds_roa=True,
            lower_leverage=True,
            higher_liquidity=True,
            no_new_shares=True,
            improving_margin=True,
            improving_turnover=True,
        ),
        存贷双高=存贷双高,
        cash_amount=Decimal("1000000"),
        debt_amount=Decimal("500000"),
        cash_growth_rate=0.05,
        debt_growth_rate=0.02,
        goodwill_ratio=0.10,
        goodwill_excessive=goodwill_excessive,
        profit_cash_divergence=profit_cash_divergence,
        profit_growth=0.10,
        ocf_growth=0.08,
        red_flags=red_flags if red_flags is not None else [],
    )


def _make_valuation(margin_of_safety: float = 0.35) -> ValuationResult:
    """Create a ValuationResult with configurable margin of safety."""
    from stockvaluefinder.models.valuation import DCFParams

    return ValuationResult(
        valuation_id=uuid4(),
        calculated_at=datetime(2024, 1, 15),
        ticker="600519.SH",
        current_price=Decimal("1800.00"),
        intrinsic_value=Decimal("2430.00"),
        wacc=0.085,
        margin_of_safety=margin_of_safety,
        valuation_level=ValuationLevel.UNDERVALUED,
        dcf_params=DCFParams(
            growth_rate_stage1=0.05,
            growth_rate_stage2=0.03,
            years_stage1=5,
            years_stage2=5,
            terminal_growth=0.025,
            risk_free_rate=0.028,
            beta=0.9,
            market_risk_premium=0.063,
        ),
        audit_trail={"method": "2-stage DCF"},
    )


def _make_yield_gap(yield_gap: float = 0.015) -> YieldGap:
    """Create a YieldGap with configurable yield gap value."""
    return YieldGap(
        analysis_id=uuid4(),
        calculated_at=datetime(2024, 1, 15),
        ticker="600519.SH",
        cost_basis=Decimal("1800.00"),
        current_price=Decimal("1800.00"),
        gross_dividend_yield=0.02,
        net_dividend_yield=0.016,
        risk_free_bond_rate=0.028,
        risk_free_deposit_rate=0.025,
        yield_gap=yield_gap,
        recommendation=YieldRecommendation.ATTRACTIVE,
        market=Market.A_SHARE,
    )


# ---------------------------------------------------------------------------
# Test 1: Safety margin >= 0.30 generates reason
# ---------------------------------------------------------------------------


def test_safety_margin_above_threshold_generates_reason() -> None:
    """Test 1: Safety margin >= 0.30 generates a positive selection reason."""
    result = generate_reasons(
        composite_score=_make_composite(),
        valuation_result=_make_valuation(margin_of_safety=0.35),
    )

    assert any(
        "Safety margin" in r and "above 30% threshold" in r for r in result.reasons
    )
    # Verify actual metric value in the reason string
    assert any("35%" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Test 2: Safety margin < 0.30 but >= 0 generates risk flag
# ---------------------------------------------------------------------------


def test_safety_margin_below_threshold_generates_risk_flag() -> None:
    """Test 2: Safety margin < 0.30 but >= 0 generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        valuation_result=_make_valuation(margin_of_safety=0.15),
    )

    assert any(
        "Safety margin" in f and "below 30% threshold" in f for f in result.risk_flags
    )
    assert any("15%" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 3: No ValuationResult generates risk flag
# ---------------------------------------------------------------------------


def test_no_valuation_result_generates_risk_flag() -> None:
    """Test 3: Missing ValuationResult generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        valuation_result=None,
    )

    assert any("DCF valuation not available" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 4: RiskLevel HIGH generates risk flag with M-Score
# ---------------------------------------------------------------------------


def test_high_risk_level_generates_risk_flag() -> None:
    """Test 4: RiskLevel HIGH generates risk flag with M-Score value."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(risk_level=RiskLevel.HIGH, m_score=-1.50),
    )

    assert any("Risk level HIGH" in f and "M-Score=" in f for f in result.risk_flags)
    assert any("-1.50" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 5: RiskLevel CRITICAL generates risk flag with M-Score
# ---------------------------------------------------------------------------


def test_critical_risk_level_generates_risk_flag() -> None:
    """Test 5: RiskLevel CRITICAL generates risk flag with M-Score value."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(risk_level=RiskLevel.CRITICAL, m_score=-0.50),
    )

    assert any(
        "Risk level CRITICAL" in f and "M-Score=" in f for f in result.risk_flags
    )
    assert any("-0.50" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 6: RiskLevel LOW generates reason
# ---------------------------------------------------------------------------


def test_low_risk_level_generates_reason() -> None:
    """Test 6: RiskLevel LOW generates a positive reason with M-Score."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(risk_level=RiskLevel.LOW, m_score=-2.80),
    )

    assert any("Low risk profile" in r and "M-Score=" in r for r in result.reasons)
    assert any("-2.80" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Test 7: RiskScore with red_flags generates risk flag
# ---------------------------------------------------------------------------


def test_red_flags_generate_risk_flag() -> None:
    """Test 7: RiskScore with red_flags generates aggregated risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(
            risk_level=RiskLevel.MEDIUM,
            red_flags=["Anomaly A", "Anomaly B"],
        ),
    )

    assert any(
        "2 risk indicator(s)" in f and "Anomaly A" in f and "Anomaly B" in f
        for f in result.risk_flags
    )


def test_red_flags_truncated_to_max_3() -> None:
    """Test 7 extended: More than 3 red_flags are truncated to first 3."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(
            risk_level=RiskLevel.MEDIUM,
            red_flags=["Flag A", "Flag B", "Flag C", "Flag D"],
        ),
    )

    flag_str = [f for f in result.risk_flags if "risk indicator(s)" in f][0]
    assert "Flag A" in flag_str
    assert "Flag B" in flag_str
    assert "Flag C" in flag_str
    assert "Flag D" not in flag_str


# ---------------------------------------------------------------------------
# Test 8: profit_cash_divergence generates risk flag
# ---------------------------------------------------------------------------


def test_profit_cash_divergence_generates_risk_flag() -> None:
    """Test 8: profit_cash_divergence=True generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(profit_cash_divergence=True),
    )

    assert any("Profit-cash flow divergence detected" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 9: goodwill_excessive generates risk flag
# ---------------------------------------------------------------------------


def test_goodwill_excessive_generates_risk_flag() -> None:
    """Test 9: goodwill_excessive=True generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(goodwill_excessive=True),
    )

    assert any("Excessive goodwill ratio" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 10: 存贷双高 generates risk flag
# ---------------------------------------------------------------------------


def test_cun_dai_shuang_gao_generates_risk_flag() -> None:
    """Test 10: 存贷双高=True generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(存贷双高=True),
    )

    assert any("cun-dai-shuang-gao" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 11: CompositeScore >= 70 generates reason
# ---------------------------------------------------------------------------


def test_high_composite_score_generates_reason() -> None:
    """Test 11: CompositeScore >= 70 generates strong ranking reason."""
    result = generate_reasons(
        composite_score=_make_composite(composite=85.0),
    )

    assert any(
        "Composite score 85.0" in r and "strong overall ranking" in r
        for r in result.reasons
    )


def test_moderate_composite_score_generates_reason() -> None:
    """Test 11 extended: CompositeScore >= 50 generates moderate ranking reason."""
    result = generate_reasons(
        composite_score=_make_composite(composite=55.0),
    )

    assert any(
        "Composite score 55.0" in r and "moderate overall ranking" in r
        for r in result.reasons
    )
    assert not any("strong overall ranking" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Test 12: Negative yield_gap generates risk flag
# ---------------------------------------------------------------------------


def test_negative_yield_gap_generates_risk_flag() -> None:
    """Test 12: Negative yield_gap generates risk flag with value."""
    result = generate_reasons(
        composite_score=_make_composite(),
        yield_gap=_make_yield_gap(yield_gap=-0.005),
    )

    assert any(
        "Negative yield gap" in f and "dividend below risk-free rate" in f
        for f in result.risk_flags
    )


# ---------------------------------------------------------------------------
# Test 13: Positive yield_gap generates reason
# ---------------------------------------------------------------------------


def test_positive_yield_gap_generates_reason() -> None:
    """Test 13: Positive yield_gap generates reason with value."""
    result = generate_reasons(
        composite_score=_make_composite(),
        yield_gap=_make_yield_gap(yield_gap=0.015),
    )

    assert any(
        "Positive yield gap" in r and "dividend exceeds risk-free rate" in r
        for r in result.reasons
    )


# ---------------------------------------------------------------------------
# Test 14: No YieldGap provided generates risk flag
# ---------------------------------------------------------------------------


def test_no_yield_gap_generates_risk_flag() -> None:
    """Test 14: Missing YieldGap generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        yield_gap=None,
    )

    assert any(
        "Dividend yield gap analysis not available" in f for f in result.risk_flags
    )


# ---------------------------------------------------------------------------
# Test 15: Generic compliance flag when no specific risk flags
# ---------------------------------------------------------------------------


def test_generic_compliance_flag_when_no_specific_risks() -> None:
    """Test 15: Generic compliance flag appended when no specific risk flags."""
    # Use a scenario where all metrics are positive but no specific risk flags triggered
    result = generate_reasons(
        composite_score=_make_composite(composite=45.0),
        valuation_result=_make_valuation(margin_of_safety=0.50),
        risk_score=_make_risk_score(risk_level=RiskLevel.LOW, m_score=-2.50),
        yield_gap=_make_yield_gap(yield_gap=0.02),
    )

    # Should have at least one risk flag (compliance requirement)
    assert len(result.risk_flags) >= 1
    assert any("Standard risk factors apply" in f for f in result.risk_flags)


# ---------------------------------------------------------------------------
# Test 16: Output always has >= 1 risk_flags
# ---------------------------------------------------------------------------


def test_always_at_least_one_risk_flag() -> None:
    """Test 16: CandidateReasons validation ensures >= 1 risk_flags."""
    # Minimal input - no risk data at all, should still produce risk flags
    result = generate_reasons(
        composite_score=_make_composite(),
    )

    assert len(result.risk_flags) >= 1


def test_all_positive_scenario_still_has_risk_flags() -> None:
    """Test 16 extended: Even with all-positive metrics, risk_flags is non-empty."""
    result = generate_reasons(
        composite_score=_make_composite(composite=90.0),
        valuation_result=_make_valuation(margin_of_safety=0.55),
        risk_score=_make_risk_score(risk_level=RiskLevel.LOW, m_score=-2.50, f_score=9),
        yield_gap=_make_yield_gap(yield_gap=0.03),
    )

    assert len(result.risk_flags) >= 1


# ---------------------------------------------------------------------------
# Test 17: All reasons use actual metric values
# ---------------------------------------------------------------------------


def test_reasons_use_actual_metric_values() -> None:
    """Test 17: No placeholder text in reasons; all use actual values."""
    result = generate_reasons(
        composite_score=_make_composite(composite=82.3),
        valuation_result=_make_valuation(margin_of_safety=0.42),
        risk_score=_make_risk_score(risk_level=RiskLevel.LOW, m_score=-3.12),
        yield_gap=_make_yield_gap(yield_gap=0.018),
    )

    all_texts = result.reasons + result.risk_flags
    for text in all_texts:
        # Should not contain placeholder-like text
        assert "TODO" not in text
        assert "FIXME" not in text
        assert "placeholder" not in text.lower()
        assert "N/A" not in text


# ---------------------------------------------------------------------------
# Test 18: F-Score <= 3 generates risk flag
# ---------------------------------------------------------------------------


def test_low_f_score_generates_risk_flag() -> None:
    """Test 18: F-Score <= 3 generates risk flag about fundamental weakness."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(
            risk_level=RiskLevel.MEDIUM,
            f_score=2,
        ),
    )

    assert any(
        "Low Piotroski F-Score" in f and "2/9" in f and "fundamental weakness" in f
        for f in result.risk_flags
    )


# ---------------------------------------------------------------------------
# Test 19: F-Score >= 7 generates reason
# ---------------------------------------------------------------------------


def test_high_f_score_generates_reason() -> None:
    """Test 19: F-Score >= 7 generates reason about solid fundamentals."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(
            risk_level=RiskLevel.LOW,
            f_score=8,
        ),
    )

    assert any(
        "Strong Piotroski F-Score" in r and "8/9" in r and "solid fundamentals" in r
        for r in result.reasons
    )


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------


def test_negative_margin_of_safety_generates_risk_flag() -> None:
    """Edge: Negative margin of safety generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        valuation_result=_make_valuation(margin_of_safety=-0.10),
    )

    assert any(
        "No safety margin" in f and "intrinsic value below market price" in f
        for f in result.risk_flags
    )


def test_zero_margin_of_safety_generates_risk_flag() -> None:
    """Edge: Zero margin of safety generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        valuation_result=_make_valuation(margin_of_safety=0.0),
    )

    assert any("No safety margin" in f for f in result.risk_flags)


def test_moderate_risk_level_generates_risk_flag() -> None:
    """Edge: MEDIUM risk level generates moderate risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(risk_level=RiskLevel.MEDIUM, m_score=-2.00),
    )

    assert any(
        "Moderate risk level" in f and "M-Score=" in f for f in result.risk_flags
    )


def test_no_risk_score_generates_risk_flag() -> None:
    """Edge: Missing RiskScore generates risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=None,
    )

    assert any("Risk analysis not available" in f for f in result.risk_flags)


def test_zero_yield_gap_generates_risk_flag() -> None:
    """Edge: Zero yield gap generates breakeven risk flag."""
    result = generate_reasons(
        composite_score=_make_composite(),
        yield_gap=_make_yield_gap(yield_gap=0.0),
    )

    assert any("Yield gap at breakeven" in f for f in result.risk_flags)


def test_low_composite_score_no_composite_reason() -> None:
    """Edge: CompositeScore < 50 generates no composite reason."""
    result = generate_reasons(
        composite_score=_make_composite(composite=35.0),
    )

    assert not any("Composite score" in r for r in result.reasons)


def test_combined_scenario_all_domains() -> None:
    """Integration: All domains contribute reasons and risk flags."""
    result = generate_reasons(
        composite_score=_make_composite(composite=78.5),
        valuation_result=_make_valuation(margin_of_safety=0.38),
        risk_score=_make_risk_score(
            risk_level=RiskLevel.LOW,
            m_score=-2.90,
            f_score=8,
            profit_cash_divergence=False,
        ),
        yield_gap=_make_yield_gap(yield_gap=0.012),
    )

    # Should have reasons from all positive domains
    assert any("Safety margin" in r for r in result.reasons)
    assert any("Low risk profile" in r for r in result.reasons)
    assert any("Strong Piotroski F-Score" in r for r in result.reasons)
    assert any("Composite score" in r for r in result.reasons)
    assert any("Positive yield gap" in r for r in result.reasons)

    # Compliance: still has risk flags
    assert len(result.risk_flags) >= 1


def test_multiple_risk_indicators_combined() -> None:
    """Integration: Multiple risk indicators all appear as risk flags."""
    result = generate_reasons(
        composite_score=_make_composite(),
        risk_score=_make_risk_score(
            risk_level=RiskLevel.HIGH,
            m_score=-1.00,
            f_score=2,
            red_flags=["Anomaly detected"],
            profit_cash_divergence=True,
            goodwill_excessive=True,
            存贷双高=True,
        ),
    )

    assert any("Risk level HIGH" in f for f in result.risk_flags)
    assert any("risk indicator(s)" in f for f in result.risk_flags)
    assert any("Profit-cash flow divergence" in f for f in result.risk_flags)
    assert any("Excessive goodwill" in f for f in result.risk_flags)
    assert any("cun-dai-shuang-gao" in f for f in result.risk_flags)
    assert any("Low Piotroski F-Score" in f for f in result.risk_flags)
