"""Market scanner configuration settings.

This module contains the MarketScannerConfig and ScoringWeightsConfig frozen
dataclasses that control screening thresholds, scoring weights, concurrency
limits, and cache settings for the Market Index Value Scanner.

Follows the same frozen dataclass pattern as PipelineConfig in
stockvaluefinder/pipeline/config.py and the weight validation pattern from
stockvaluefinder/services/alpha_service.py.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringWeightsConfig:
    """Configuration for the 5-dimension composite scoring weights.

    Weights are applied to normalized (0-100) component scores:
        - safety_margin: DCF margin of safety dimension (default 35%)
        - alpha: Forward-looking Alpha composite dimension (default 25%)
        - risk_penalty: Risk level penalty dimension (default 20%)
        - yield_gap: Dividend yield gap dimension (default 10%)
        - valuation_percentile: Relative valuation percentile dimension (default 10%)

    All weights must sum to approximately 1.0 (epsilon tolerance 0.01),
    matching the validation pattern in alpha_service.py.

    Attributes:
        safety_margin_weight: Weight for margin of safety dimension.
        alpha_weight: Weight for Alpha composite dimension.
        risk_penalty_weight: Weight for risk penalty dimension.
        yield_gap_weight: Weight for yield gap dimension.
        valuation_percentile_weight: Weight for valuation percentile dimension.

    Raises:
        ValueError: If weights are negative, wrong count, or do not sum to ~1.0.
    """

    safety_margin_weight: float = 0.35
    alpha_weight: float = 0.25
    risk_penalty_weight: float = 0.20
    yield_gap_weight: float = 0.10
    valuation_percentile_weight: float = 0.10

    def __post_init__(self) -> None:
        """Validate weights after initialization."""
        weights = (
            self.safety_margin_weight,
            self.alpha_weight,
            self.risk_penalty_weight,
            self.yield_gap_weight,
            self.valuation_percentile_weight,
        )
        if len(weights) != 5:
            raise ValueError(
                f"weights must have exactly 5 elements, got {len(weights)}"
            )
        if any(w < 0 for w in weights):
            raise ValueError(
                f"all weights must be non-negative, got {weights}"
            )
        if abs(sum(weights) - 1.0) > 0.01:
            raise ValueError(
                f"weights must sum to approximately 1.0, got {sum(weights)}"
            )

    @property
    def weights_tuple(self) -> tuple[float, float, float, float, float]:
        """Return all 5 weights as a tuple for indexed access."""
        return (
            self.safety_margin_weight,
            self.alpha_weight,
            self.risk_penalty_weight,
            self.yield_gap_weight,
            self.valuation_percentile_weight,
        )


@dataclass(frozen=True)
class MarketScannerConfig:
    """Configuration for the Market Index Value Scanner.

    Controls index pool selection, screening thresholds, scoring weights,
    concurrency limits, and cache settings. All thresholds are validated at
    instantiation time via __post_init__ to prevent invalid configurations
    from propagating.

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
        min_turnover_ratio: Minimum daily turnover ratio for liquidity filtering.
        min_ocf_positive_years: Minimum consecutive years of positive operating cash flow.
        min_market_cap: Minimum market capitalization in CNY for size filtering.
        scoring_weights: Weighted scoring configuration for composite score calculation.

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
    min_turnover_ratio: float = 0.01
    min_ocf_positive_years: int = 2
    min_market_cap: float = 1_000_000_000
    scoring_weights: ScoringWeightsConfig = field(
        default_factory=ScoringWeightsConfig
    )

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
        if self.min_turnover_ratio <= 0:
            raise ValueError(
                f"min_turnover_ratio must be > 0, "
                f"got {self.min_turnover_ratio}"
            )
        if self.min_ocf_positive_years < 0:
            raise ValueError(
                f"min_ocf_positive_years must be >= 0, "
                f"got {self.min_ocf_positive_years}"
            )
        if self.min_market_cap <= 0:
            raise ValueError(
                f"min_market_cap must be > 0, got {self.min_market_cap}"
            )


__all__ = ["MarketScannerConfig", "ScoringWeightsConfig"]
