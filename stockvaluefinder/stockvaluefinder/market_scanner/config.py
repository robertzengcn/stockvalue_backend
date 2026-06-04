"""Market scanner configuration settings.

This module contains the MarketScannerConfig frozen dataclass that controls
screening thresholds, concurrency limits, and cache settings for the
Market Index Value Scanner.

Follows the same frozen dataclass pattern as PipelineConfig in
stockvaluefinder/pipeline/config.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketScannerConfig:
    """Configuration for the Market Index Value Scanner.

    Controls index pool selection, screening thresholds, concurrency limits,
    and cache settings. All thresholds are validated at instantiation time
    via __post_init__ to prevent invalid configurations from propagating.

    Attributes:
        index_codes: Tuple of index pool identifiers to scan (e.g., CSI300, CSI500).
        rules_version: Version string for the screening rules snapshot.
        daily_top_n: Maximum candidates to return for daily scans.
        weekly_top_n: Maximum candidates to return for weekly scans.
            Must be >= daily_top_n.
        min_margin_of_safety: Minimum DCF margin of safety threshold (0.0 to 1.0).
        min_composite_score: Minimum composite score threshold (0.0 to 100.0).
        deep_analysis_concurrency: Maximum concurrent deep analysis tasks.
        request_delay_seconds: Minimum delay between external API requests (rate limiting).
        max_price_cache_age_minutes: Maximum age of cached price data in minutes.
        alpha_max_age_days: Maximum age of Alpha scores in days before recalculation.

    Raises:
        ValueError: If any configuration value is invalid.
    """

    index_codes: tuple[str, ...] = ("CSI300", "CSI500")
    rules_version: str = "v1"
    daily_top_n: int = 50
    weekly_top_n: int = 100
    min_margin_of_safety: float = 0.30
    min_composite_score: float = 60.0
    deep_analysis_concurrency: int = 5
    request_delay_seconds: float = 0.5
    max_price_cache_age_minutes: int = 30
    alpha_max_age_days: int = 30

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if not self.index_codes:
            raise ValueError("index_codes must not be empty")
        if self.daily_top_n <= 0:
            raise ValueError(f"daily_top_n must be > 0, got {self.daily_top_n}")
        if self.weekly_top_n < self.daily_top_n:
            raise ValueError(
                f"weekly_top_n ({self.weekly_top_n}) must be >= "
                f"daily_top_n ({self.daily_top_n})"
            )
        if not (0 <= self.min_margin_of_safety <= 1):
            raise ValueError(
                f"min_margin_of_safety must be in [0, 1], "
                f"got {self.min_margin_of_safety}"
            )
        if not (0 <= self.min_composite_score <= 100):
            raise ValueError(
                f"min_composite_score must be in [0, 100], "
                f"got {self.min_composite_score}"
            )
        if self.deep_analysis_concurrency < 1:
            raise ValueError(
                f"deep_analysis_concurrency must be >= 1, "
                f"got {self.deep_analysis_concurrency}"
            )


__all__ = ["MarketScannerConfig"]
