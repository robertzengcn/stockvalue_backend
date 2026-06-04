"""Screening and scoring domain models (Pydantic).

This module defines Pydantic models for the screening and scoring engine,
covering coarse screening input/output, composite score components, and
structured candidate reasons.

Key model groups:
    - ScreeningSnapshot: Input data for coarse screening (market data snapshot)
    - ScreeningResult: Output of coarse screening (pass/fail, rank, signals)
    - CompositeScoreComponents: Individual normalized scores (0-100 each)
    - CompositeScore: Weighted composite output (frozen)
    - CandidateReasons: Structured selection reasons and risk flags (frozen)
"""

from pydantic import BaseModel, Field


class ScreeningSnapshot(BaseModel):
    """Input data for coarse screening (market data snapshot).

    Populated by Phase 27 from batch market data fetch. All fields are
    structurally validated via Pydantic before the screening engine processes them.

    Attributes:
        ticker: Stock code matching pattern NNNNNN.{SH|SZ}.
        name: Company name.
        index_code: Index pool identifier (e.g., CSI300, CSI500).
        is_st: Whether the stock has ST (Special Treatment) status.
        is_suspended: Whether the stock is currently suspended from trading.
        has_price_data: Whether current price data is available.
        turnover_ratio: Daily turnover ratio (liquidity measure), must be >= 0.
        pe_ttm: Price-to-earnings ratio (trailing 12 months). None if negative earnings.
        pb_ratio: Price-to-book ratio. None if not applicable.
        dividend_yield: Gross dividend yield as decimal (e.g., 0.03 = 3%).
        price_vs_52w_high: Current price / 52-week high, range [0.0, 1.0].
        ocf_positive_years: Consecutive years of positive operating cash flow.
        market_cap: Market capitalization in CNY, must be > 0.
    """

    ticker: str = Field(..., pattern=r"^\d{6}\.(SH|SZ)$")
    name: str
    index_code: str
    is_st: bool
    is_suspended: bool
    has_price_data: bool
    turnover_ratio: float = Field(..., ge=0.0)
    pe_ttm: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float = Field(0.0, ge=0.0)
    price_vs_52w_high: float = Field(..., ge=0.0, le=1.0)
    ocf_positive_years: int = Field(0, ge=0)
    market_cap: float = Field(..., gt=0)


class ScreeningResult(BaseModel):
    """Output of coarse screening for a single stock.

    Reports whether the stock passed screening, why it was excluded,
    its priority rank score, and any soft signals.

    Attributes:
        ticker: Stock code.
        passed: Whether the stock passed all hard-exclusion rules.
        excluded_reason: Semicolon-separated exclusion reasons (None if passed).
        rank_score: Prioritization score for ranking among passed stocks (>= 0).
        signals: Dict of soft signal names to values (e.g., pe_low, dividend_high).
    """

    ticker: str
    passed: bool
    excluded_reason: str | None = None
    rank_score: float = Field(0.0, ge=0.0)
    signals: dict[str, float] = Field(default_factory=dict)


class CompositeScoreComponents(BaseModel):
    """Individual normalized scores (0-100) for each scoring dimension.

    Each component is normalized to [0, 100] before being combined with
    configurable weights in the composite score calculation.

    Attributes:
        safety_margin: Normalized DCF margin of safety score.
        alpha: Normalized Alpha composite score.
        risk_penalty: Normalized risk level penalty (higher = safer).
        yield_gap: Normalized dividend yield gap score.
        valuation_percentile: Normalized valuation percentile score (lower percentile = higher score).
    """

    safety_margin: float = Field(..., ge=0.0, le=100.0)
    alpha: float = Field(..., ge=0.0, le=100.0)
    risk_penalty: float = Field(..., ge=0.0, le=100.0)
    yield_gap: float = Field(..., ge=0.0, le=100.0)
    valuation_percentile: float = Field(..., ge=0.0, le=100.0)


class CompositeScore(BaseModel):
    """Weighted composite score output (frozen).

    Holds the final composite score, individual component breakdown,
    and whether the score passed the minimum threshold.

    Attributes:
        composite: Final weighted composite score (0-100).
        components: Individual normalized component scores.
        passed_threshold: Whether composite >= configured min_composite_score.
    """

    model_config = {"frozen": True}

    composite: float = Field(..., ge=0.0, le=100.0)
    components: CompositeScoreComponents
    passed_threshold: bool


class CandidateReasons(BaseModel):
    """Structured selection reasons and risk flags for a scan candidate.

    Every candidate must have at least one risk flag, even if the stock
    appears strong (per PITFALLS.md Pitfall 6 compliance requirement).

    Attributes:
        reasons: List of selection reasons (why this stock was chosen).
        risk_flags: List of risk flags (at least one required per candidate).
    """

    model_config = {"frozen": True}

    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(..., min_length=1)
