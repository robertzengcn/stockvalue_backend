"""Tests for MarketScannerConfig frozen dataclass.

TDD RED phase: Tests written before implementation.
Covers: default instantiation, validation of all fields, frozen enforcement.
"""

import dataclasses

import pytest

from stockvaluefinder.market_scanner.config import MarketScannerConfig


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
