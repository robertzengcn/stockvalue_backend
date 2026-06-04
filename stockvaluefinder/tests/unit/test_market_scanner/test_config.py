"""Tests for MarketScannerConfig and ScoringWeightsConfig frozen dataclasses.

TDD: Tests written before implementation (RED), implementation added (GREEN).
Covers: default instantiation, validation of all fields, frozen enforcement,
        scoring weight validation, and coarse screen threshold validation.
"""

import dataclasses

import pytest

from stockvaluefinder.market_scanner.config import (
    MarketScannerConfig,
    ScoringWeightsConfig,
)


# ---------------------------------------------------------------------------
# ScoringWeightsConfig tests
# ---------------------------------------------------------------------------


class TestScoringWeightsConfigDefaults:
    """Test that ScoringWeightsConfig creates with valid default weights."""

    def test_creates_with_valid_defaults(self) -> None:
        """ScoringWeightsConfig() should create with default weights summing to 1.0."""
        weights = ScoringWeightsConfig()

        assert weights.safety_margin_weight == pytest.approx(0.35)
        assert weights.alpha_weight == pytest.approx(0.25)
        assert weights.risk_penalty_weight == pytest.approx(0.20)
        assert weights.yield_gap_weight == pytest.approx(0.10)
        assert weights.valuation_percentile_weight == pytest.approx(0.10)

    def test_default_weights_sum_to_one(self) -> None:
        """Default weights must sum to approximately 1.0."""
        weights = ScoringWeightsConfig()
        total = (
            weights.safety_margin_weight
            + weights.alpha_weight
            + weights.risk_penalty_weight
            + weights.yield_gap_weight
            + weights.valuation_percentile_weight
        )
        assert total == pytest.approx(1.0, abs=0.01)

    def test_weights_tuple_property(self) -> None:
        """weights_tuple property returns all 5 weights as a tuple."""
        weights = ScoringWeightsConfig()
        result = weights.weights_tuple

        assert isinstance(result, tuple)
        assert len(result) == 5
        assert result == (
            weights.safety_margin_weight,
            weights.alpha_weight,
            weights.risk_penalty_weight,
            weights.yield_gap_weight,
            weights.valuation_percentile_weight,
        )


class TestScoringWeightsConfigValidation:
    """Test that ScoringWeightsConfig rejects invalid weight configurations."""

    def test_rejects_weights_not_summing_to_one(self) -> None:
        """Weights must sum to approximately 1.0 (epsilon tolerance 0.01)."""
        with pytest.raises(ValueError, match="sum to approximately 1.0"):
            ScoringWeightsConfig(
                safety_margin_weight=0.50,
                alpha_weight=0.30,
                risk_penalty_weight=0.20,
                yield_gap_weight=0.10,
                valuation_percentile_weight=0.10,
            )

    def test_rejects_negative_weight(self) -> None:
        """Weights must all be non-negative."""
        with pytest.raises(ValueError, match="non-negative"):
            ScoringWeightsConfig(
                safety_margin_weight=-0.10,
                alpha_weight=0.45,
                risk_penalty_weight=0.30,
                yield_gap_weight=0.20,
                valuation_percentile_weight=0.15,
            )

    def test_frozen_rejects_assignment(self) -> None:
        """ScoringWeightsConfig must be frozen."""
        weights = ScoringWeightsConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            weights.safety_margin_weight = 0.50  # type: ignore[misc]

    def test_accepts_custom_valid_weights(self) -> None:
        """Custom weights summing to 1.0 should be accepted."""
        weights = ScoringWeightsConfig(
            safety_margin_weight=0.40,
            alpha_weight=0.30,
            risk_penalty_weight=0.15,
            yield_gap_weight=0.10,
            valuation_percentile_weight=0.05,
        )
        assert weights.safety_margin_weight == pytest.approx(0.40)
        assert weights.weights_tuple[0] == pytest.approx(0.40)


# ---------------------------------------------------------------------------
# MarketScannerConfig: extended fields tests
# ---------------------------------------------------------------------------


class TestMarketScannerConfigExtendedDefaults:
    """Test extended MarketScannerConfig with new coarse screen thresholds."""

    def test_new_fields_have_defaults(self) -> None:
        """MarketScannerConfig defaults must include new coarse screen fields."""
        config = MarketScannerConfig()

        assert config.min_turnover_ratio == pytest.approx(0.01)
        assert config.min_ocf_positive_years == 2
        assert config.min_market_cap == pytest.approx(1_000_000_000)

    def test_scoring_weights_field_holds_instance(self) -> None:
        """scoring_weights field must hold a ScoringWeightsConfig instance."""
        config = MarketScannerConfig()

        assert isinstance(config.scoring_weights, ScoringWeightsConfig)
        assert config.scoring_weights.safety_margin_weight == pytest.approx(0.35)

    def test_custom_scoring_weights_accepted(self) -> None:
        """MarketScannerConfig should accept custom ScoringWeightsConfig."""
        custom_weights = ScoringWeightsConfig(
            safety_margin_weight=0.50,
            alpha_weight=0.20,
            risk_penalty_weight=0.15,
            yield_gap_weight=0.10,
            valuation_percentile_weight=0.05,
        )
        config = MarketScannerConfig(scoring_weights=custom_weights)

        assert config.scoring_weights.safety_margin_weight == pytest.approx(0.50)


class TestMarketScannerConfigExtendedValidation:
    """Test that MarketScannerConfig rejects invalid new threshold values."""

    def test_rejects_min_turnover_ratio_zero(self) -> None:
        """min_turnover_ratio must be > 0."""
        with pytest.raises(ValueError, match="min_turnover_ratio"):
            MarketScannerConfig(min_turnover_ratio=0.0)

    def test_rejects_min_turnover_ratio_negative(self) -> None:
        """min_turnover_ratio must be > 0."""
        with pytest.raises(ValueError, match="min_turnover_ratio"):
            MarketScannerConfig(min_turnover_ratio=-0.01)

    def test_rejects_min_ocf_positive_years_negative(self) -> None:
        """min_ocf_positive_years must be >= 0."""
        with pytest.raises(ValueError, match="min_ocf_positive_years"):
            MarketScannerConfig(min_ocf_positive_years=-1)

    def test_accepts_min_ocf_positive_years_zero(self) -> None:
        """min_ocf_positive_years == 0 should be valid."""
        config = MarketScannerConfig(min_ocf_positive_years=0)
        assert config.min_ocf_positive_years == 0

    def test_rejects_min_market_cap_zero(self) -> None:
        """min_market_cap must be > 0."""
        with pytest.raises(ValueError, match="min_market_cap"):
            MarketScannerConfig(min_market_cap=0.0)

    def test_rejects_min_market_cap_negative(self) -> None:
        """min_market_cap must be > 0."""
        with pytest.raises(ValueError, match="min_market_cap"):
            MarketScannerConfig(min_market_cap=-1.0)

    def test_existing_validation_still_works_with_new_fields(self) -> None:
        """All existing validations must still pass when new fields are present."""
        # Existing validation: empty index_codes
        with pytest.raises(ValueError, match="index_codes"):
            MarketScannerConfig(index_codes=())

        # Existing validation: daily_top_n <= 0
        with pytest.raises(ValueError, match="daily_top_n"):
            MarketScannerConfig(daily_top_n=0)


# ---------------------------------------------------------------------------
# Original MarketScannerConfig tests (preserved from Phase 25)
# ---------------------------------------------------------------------------


class TestMarketScannerConfigDefaults:
    """Test that MarketScannerConfig creates with valid defaults."""

    def test_creates_with_valid_defaults(self) -> None:
        """Config() should create with all default values."""
        config = MarketScannerConfig()

        assert config.index_codes == ("CSI300", "CSI500")
        assert config.rules_version == "v1"
        assert config.daily_top_n == 50
        assert config.weekly_top_n == 100
        assert config.min_margin_of_safety == pytest.approx(0.30)
        assert config.min_composite_score == pytest.approx(60.0)
        assert config.deep_analysis_concurrency == 5
        assert config.request_delay_seconds == pytest.approx(0.5)
        assert config.max_price_cache_age_minutes == 30
        assert config.alpha_max_age_days == 30


class TestMarketScannerConfigValidation:
    """Test that MarketScannerConfig rejects invalid values."""

    def test_rejects_empty_index_codes(self) -> None:
        """Config must reject empty index_codes tuple."""
        with pytest.raises(ValueError, match="index_codes"):
            MarketScannerConfig(index_codes=())

    def test_rejects_daily_top_n_zero(self) -> None:
        """Config must reject daily_top_n <= 0."""
        with pytest.raises(ValueError, match="daily_top_n"):
            MarketScannerConfig(daily_top_n=0)

    def test_rejects_daily_top_n_negative(self) -> None:
        """Config must reject negative daily_top_n."""
        with pytest.raises(ValueError, match="daily_top_n"):
            MarketScannerConfig(daily_top_n=-1)

    def test_rejects_weekly_top_n_less_than_daily(self) -> None:
        """Config must reject weekly_top_n < daily_top_n."""
        with pytest.raises(ValueError, match="weekly_top_n"):
            MarketScannerConfig(daily_top_n=100, weekly_top_n=50)

    def test_rejects_min_margin_of_safety_below_zero(self) -> None:
        """Config must reject min_margin_of_safety outside [0, 1]."""
        with pytest.raises(ValueError, match="min_margin_of_safety"):
            MarketScannerConfig(min_margin_of_safety=-0.01)

    def test_rejects_min_margin_of_safety_above_one(self) -> None:
        """Config must reject min_margin_of_safety above 1."""
        with pytest.raises(ValueError, match="min_margin_of_safety"):
            MarketScannerConfig(min_margin_of_safety=1.01)

    def test_rejects_min_composite_score_below_zero(self) -> None:
        """Config must reject min_composite_score outside [0, 100]."""
        with pytest.raises(ValueError, match="min_composite_score"):
            MarketScannerConfig(min_composite_score=-1.0)

    def test_rejects_min_composite_score_above_100(self) -> None:
        """Config must reject min_composite_score above 100."""
        with pytest.raises(ValueError, match="min_composite_score"):
            MarketScannerConfig(min_composite_score=101.0)

    def test_rejects_deep_analysis_concurrency_zero(self) -> None:
        """Config must reject deep_analysis_concurrency < 1."""
        with pytest.raises(ValueError, match="deep_analysis_concurrency"):
            MarketScannerConfig(deep_analysis_concurrency=0)

    def test_rejects_deep_analysis_concurrency_negative(self) -> None:
        """Config must reject negative deep_analysis_concurrency."""
        with pytest.raises(ValueError, match="deep_analysis_concurrency"):
            MarketScannerConfig(deep_analysis_concurrency=-1)


class TestMarketScannerConfigCustomValues:
    """Test that Config accepts custom valid values."""

    def test_accepts_custom_valid_values(self) -> None:
        """Config should accept valid custom values without error."""
        config = MarketScannerConfig(
            index_codes=("CSI300",),
            rules_version="v2",
            daily_top_n=10,
            weekly_top_n=20,
            min_margin_of_safety=0.50,
            min_composite_score=75.0,
            deep_analysis_concurrency=3,
            request_delay_seconds=1.0,
            max_price_cache_age_minutes=60,
            alpha_max_age_days=7,
        )

        assert config.index_codes == ("CSI300",)
        assert config.rules_version == "v2"
        assert config.daily_top_n == 10
        assert config.weekly_top_n == 20
        assert config.min_margin_of_safety == pytest.approx(0.50)
        assert config.min_composite_score == pytest.approx(75.0)
        assert config.deep_analysis_concurrency == 3


class TestMarketScannerConfigFrozen:
    """Test that Config is frozen (immutable)."""

    def test_frozen_rejects_assignment_to_index_codes(self) -> None:
        """Assigning to any field must raise FrozenInstanceError."""
        config = MarketScannerConfig()

        with pytest.raises(dataclasses.FrozenInstanceError):
            config.index_codes = ("CSI300",)  # type: ignore[misc]

    def test_frozen_rejects_assignment_to_daily_top_n(self) -> None:
        """Assigning to daily_top_n must raise FrozenInstanceError."""
        config = MarketScannerConfig()

        with pytest.raises(dataclasses.FrozenInstanceError):
            config.daily_top_n = 99  # type: ignore[misc]

    def test_frozen_rejects_assignment_to_min_margin_of_safety(self) -> None:
        """Assigning to min_margin_of_safety must raise FrozenInstanceError."""
        config = MarketScannerConfig()

        with pytest.raises(dataclasses.FrozenInstanceError):
            config.min_margin_of_safety = 0.99  # type: ignore[misc]
