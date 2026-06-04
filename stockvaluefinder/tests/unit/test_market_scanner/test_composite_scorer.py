"""Unit tests for composite_scorer module.

Tests cover all 5 normalization functions and the composite score calculation,
including None handling, NaN guards, clamping, and weighted sum computation.
"""

import math

import pytest

from stockvaluefinder.market_scanner.composite_scorer import (
    calculate_composite_score,
    normalize_alpha_score,
    normalize_risk_penalty,
    normalize_safety_margin,
    normalize_valuation_percentile,
    normalize_yield_gap,
)
from stockvaluefinder.market_scanner.config import (
    MarketScannerConfig,
    ScoringWeightsConfig,
)
from stockvaluefinder.models.enums import RiskLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_config() -> MarketScannerConfig:
    """Return a default MarketScannerConfig."""
    return MarketScannerConfig()


# ---------------------------------------------------------------------------
# normalize_safety_margin tests
# ---------------------------------------------------------------------------


class TestNormalizeSafetyMargin:
    """Safety margin normalization: 0% -> 0, 30% -> 50, 60% -> 100."""

    def test_zero_returns_zero(self) -> None:
        assert normalize_safety_margin(0.0) == 0.0

    def test_30_percent_returns_50(self) -> None:
        assert normalize_safety_margin(0.30) == 50.0

    def test_60_percent_returns_100(self) -> None:
        assert normalize_safety_margin(0.60) == 100.0

    def test_negative_returns_zero(self) -> None:
        assert normalize_safety_margin(-0.10) == 0.0

    def test_none_returns_zero(self) -> None:
        assert normalize_safety_margin(None) == 0.0

    def test_nan_returns_zero(self) -> None:
        assert normalize_safety_margin(float("nan")) == 0.0

    def test_above_60_clamped_to_100(self) -> None:
        assert normalize_safety_margin(0.80) == 100.0

    def test_small_positive(self) -> None:
        result = normalize_safety_margin(0.15)
        expected = round((0.15 / 0.60) * 100.0, 2)
        assert result == expected


# ---------------------------------------------------------------------------
# normalize_alpha_score tests
# ---------------------------------------------------------------------------


class TestNormalizeAlphaScore:
    """Alpha score normalization: pass-through with clamp to [0, 100]."""

    def test_zero_returns_zero(self) -> None:
        assert normalize_alpha_score(0.0) == 0.0

    def test_100_returns_100(self) -> None:
        assert normalize_alpha_score(100.0) == 100.0

    def test_none_returns_zero(self) -> None:
        assert normalize_alpha_score(None) == 0.0

    def test_75_returns_75(self) -> None:
        assert normalize_alpha_score(75.0) == 75.0

    def test_negative_clamped_to_zero(self) -> None:
        assert normalize_alpha_score(-10.0) == 0.0

    def test_above_100_clamped(self) -> None:
        assert normalize_alpha_score(150.0) == 100.0

    def test_nan_returns_zero(self) -> None:
        assert normalize_alpha_score(float("nan")) == 0.0


# ---------------------------------------------------------------------------
# normalize_risk_penalty tests
# ---------------------------------------------------------------------------


class TestNormalizeRiskPenalty:
    """Risk penalty normalization: LOW=100, MEDIUM=50, HIGH=0, CRITICAL=0."""

    def test_low_returns_100(self) -> None:
        assert normalize_risk_penalty(RiskLevel.LOW) == 100.0

    def test_medium_returns_50(self) -> None:
        assert normalize_risk_penalty(RiskLevel.MEDIUM) == 50.0

    def test_high_returns_0(self) -> None:
        assert normalize_risk_penalty(RiskLevel.HIGH) == 0.0

    def test_critical_returns_0(self) -> None:
        assert normalize_risk_penalty(RiskLevel.CRITICAL) == 0.0

    def test_none_returns_zero(self) -> None:
        assert normalize_risk_penalty(None) == 0.0


# ---------------------------------------------------------------------------
# normalize_yield_gap tests
# ---------------------------------------------------------------------------


class TestNormalizeYieldGap:
    """Yield gap normalization: linear clamp [-2%, +4%] -> [0, 100]."""

    def test_negative_2_percent_returns_zero(self) -> None:
        assert normalize_yield_gap(-0.02) == 0.0

    def test_positive_4_percent_returns_100(self) -> None:
        assert normalize_yield_gap(0.04) == 100.0

    def test_midpoint_1_percent_returns_50(self) -> None:
        assert normalize_yield_gap(0.01) == 50.0

    def test_none_returns_zero(self) -> None:
        assert normalize_yield_gap(None) == 0.0

    def test_nan_returns_zero(self) -> None:
        assert normalize_yield_gap(float("nan")) == 0.0

    def test_below_min_clamped(self) -> None:
        assert normalize_yield_gap(-0.05) == 0.0

    def test_above_max_clamped(self) -> None:
        assert normalize_yield_gap(0.10) == 100.0


# ---------------------------------------------------------------------------
# normalize_valuation_percentile tests
# ---------------------------------------------------------------------------


class TestNormalizeValuationPercentile:
    """Valuation percentile normalization: inverted (lower = cheaper = higher score)."""

    def test_zero_returns_100(self) -> None:
        assert normalize_valuation_percentile(0.0) == 100.0

    def test_100_returns_zero(self) -> None:
        assert normalize_valuation_percentile(100.0) == 0.0

    def test_50_returns_50(self) -> None:
        assert normalize_valuation_percentile(50.0) == 50.0

    def test_none_returns_50(self) -> None:
        """None valuation percentile defaults to neutral 50.0."""
        assert normalize_valuation_percentile(None) == 50.0

    def test_nan_returns_50(self) -> None:
        assert normalize_valuation_percentile(float("nan")) == 50.0

    def test_above_100_clamped(self) -> None:
        assert normalize_valuation_percentile(120.0) == 0.0

    def test_negative_clamped(self) -> None:
        assert normalize_valuation_percentile(-10.0) == 100.0


# ---------------------------------------------------------------------------
# calculate_composite_score tests
# ---------------------------------------------------------------------------


class TestCalculateCompositeScore:
    """Composite score: weighted sum of 5 normalized components."""

    def test_all_100s_returns_100(self) -> None:
        """All components at 100 should produce composite 100."""
        result = calculate_composite_score(
            margin_of_safety=0.60,
            alpha_score=100.0,
            risk_level=RiskLevel.LOW,
            yield_gap_value=0.04,
            valuation_percentile=0.0,
            config=_default_config(),
        )
        assert result.composite == 100.0
        assert result.passed_threshold is True

    def test_all_zeros_returns_0(self) -> None:
        """All components at minimum should produce composite 0."""
        result = calculate_composite_score(
            margin_of_safety=0.0,
            alpha_score=0.0,
            risk_level=RiskLevel.HIGH,
            yield_gap_value=-0.02,
            valuation_percentile=100.0,
            config=_default_config(),
        )
        assert result.composite == 0.0
        assert result.passed_threshold is False

    def test_default_weights_produce_correct_weighted_sum(self) -> None:
        """Verify weighted sum with default 35/25/20/10/10 weights."""
        # safety_margin: normalize_safety_margin(0.30) = 50.0
        # alpha: normalize_alpha_score(75.0) = 75.0
        # risk: normalize_risk_penalty(RiskLevel.MEDIUM) = 50.0
        # yield_gap: normalize_yield_gap(0.01) = 50.0
        # valuation: normalize_valuation_percentile(50.0) = 50.0
        # Expected: 50*0.35 + 75*0.25 + 50*0.20 + 50*0.10 + 50*0.10
        #         = 17.5 + 18.75 + 10.0 + 5.0 + 5.0 = 56.25
        result = calculate_composite_score(
            margin_of_safety=0.30,
            alpha_score=75.0,
            risk_level=RiskLevel.MEDIUM,
            yield_gap_value=0.01,
            valuation_percentile=50.0,
            config=_default_config(),
        )
        assert result.composite == 56.25

    def test_custom_weights_work(self) -> None:
        """Custom weights from ScoringWeightsConfig are applied correctly."""
        custom_weights = ScoringWeightsConfig(
            safety_margin_weight=0.20,
            alpha_weight=0.20,
            risk_penalty_weight=0.20,
            yield_gap_weight=0.20,
            valuation_percentile_weight=0.20,
        )
        config = MarketScannerConfig(scoring_weights=custom_weights)
        # All components normalized to 50.0:
        # safety_margin(0.30) = 50.0, alpha(50.0) = 50.0, risk(MEDIUM) = 50.0
        # yield_gap(0.01) = 50.0, valuation(50.0) = 50.0
        # Expected: 50*0.20 * 5 = 50.0
        result = calculate_composite_score(
            margin_of_safety=0.30,
            alpha_score=50.0,
            risk_level=RiskLevel.MEDIUM,
            yield_gap_value=0.01,
            valuation_percentile=50.0,
            config=config,
        )
        assert result.composite == 50.0

    def test_none_components_default_to_zero(self) -> None:
        """None component values default to 0.0 without crashing."""
        result = calculate_composite_score(
            margin_of_safety=None,
            alpha_score=None,
            risk_level=None,
            yield_gap_value=None,
            valuation_percentile=None,
            config=_default_config(),
        )
        # safety_margin(None) = 0.0, alpha(None) = 0.0, risk(None) = 0.0
        # yield_gap(None) = 0.0, valuation(None) = 50.0
        # Expected: 0*0.35 + 0*0.25 + 0*0.20 + 0*0.10 + 50*0.10 = 5.0
        assert result.composite == 5.0

    def test_passed_threshold_true_when_above_min(self) -> None:
        """passed_threshold is True when composite >= min_composite_score."""
        config = MarketScannerConfig(min_composite_score=50.0)
        result = calculate_composite_score(
            margin_of_safety=0.30,
            alpha_score=75.0,
            risk_level=RiskLevel.LOW,
            yield_gap_value=0.01,
            valuation_percentile=25.0,
            config=config,
        )
        assert result.composite >= 50.0
        assert result.passed_threshold is True

    def test_passed_threshold_false_when_below_min(self) -> None:
        """passed_threshold is False when composite < min_composite_score."""
        config = MarketScannerConfig(min_composite_score=80.0)
        result = calculate_composite_score(
            margin_of_safety=0.10,
            alpha_score=30.0,
            risk_level=RiskLevel.MEDIUM,
            yield_gap_value=-0.01,
            valuation_percentile=75.0,
            config=config,
        )
        assert result.composite < 80.0
        assert result.passed_threshold is False

    def test_components_populated_correctly(self) -> None:
        """CompositeScoreComponents holds individual normalized values."""
        result = calculate_composite_score(
            margin_of_safety=0.30,
            alpha_score=75.0,
            risk_level=RiskLevel.LOW,
            yield_gap_value=0.01,
            valuation_percentile=0.0,
            config=_default_config(),
        )
        assert result.components.safety_margin == 50.0
        assert result.components.alpha == 75.0
        assert result.components.risk_penalty == 100.0
        assert result.components.yield_gap == 50.0
        assert result.components.valuation_percentile == 100.0

    def test_composite_score_is_frozen(self) -> None:
        """CompositeScore model is frozen and immutable."""
        result = calculate_composite_score(
            margin_of_safety=0.30,
            alpha_score=75.0,
            risk_level=RiskLevel.LOW,
            yield_gap_value=0.01,
            valuation_percentile=50.0,
            config=_default_config(),
        )
        with pytest.raises((Exception,)):
            result.composite = 99.0  # type: ignore[misc]

    def test_composite_rounded_to_2dp(self) -> None:
        """Composite score is rounded to 2 decimal places."""
        # Use values that produce a non-terminating decimal
        result = calculate_composite_score(
            margin_of_safety=0.123,
            alpha_score=33.0,
            risk_level=RiskLevel.MEDIUM,
            yield_gap_value=0.005,
            valuation_percentile=33.0,
            config=_default_config(),
        )
        assert result.composite == round(result.composite, 2)
