# Phase 26: Screening & Scoring Engine - Research

**Researched:** 2026-06-04
**Domain:** Financial stock screening rules, composite scoring normalization, deterministic reason generation
**Confidence:** HIGH

## Summary

Phase 26 builds three core capabilities on top of the Phase 25 data foundation: (1) a coarse screening engine that filters stocks through hard-exclusion rules (ST status, suspension, missing data, low liquidity, negative cash flow) and prioritization signals (low PE/PB, high dividend yield, price drawdown); (2) a composite scoring engine that normalizes five dimensions to 0-100 and combines them with configurable weights (safety margin 35%, Alpha 25%, risk penalty 20%, yield gap 10%, valuation percentile 10%); (3) a deterministic reason generator that produces structured selection reasons and risk flags from computed metrics without any LLM involvement.

All three components are pure-function services that accept market data and analysis results as input and produce structured outputs. They do not fetch external data or perform I/O -- that orchestration belongs to Phase 27. The existing `MarketScannerConfig` (Phase 25) already defines `min_margin_of_safety`, `min_composite_score`, and `daily_top_n` / `weekly_top_n` thresholds that this phase's services will consume.

**Primary recommendation:** Build three pure-function modules under `stockvaluefinder/market_scanner/` -- `coarse_screener.py`, `composite_scorer.py`, and `reason_generator.py` -- each with comprehensive unit tests. Follow the existing pattern of frozen dataclass config + pure functions + service class wrapper.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SCR-01 | Market Coarse Screening -- filter ST, suspended, missing data, low liquidity, negative OCF; prioritize low PE/PB, high dividend yield, drawdown | Coarse screener module with hard-exclusion rules and soft prioritization ranking; input data from batch market snapshot (Phase 27 fetches) |
| SCR-05 | Composite Candidate Scoring -- 5 weighted dimensions normalized to 0-100 before weighting | Composite scorer module reusing existing normalization patterns from `alpha_service.py`; weight tuple validated via `MarketScannerConfig` |
| SCR-06 | Structured Reason Generation -- deterministic reasons and risk flags from metrics, no LLM | Reason generator module with rule-based templates triggered by metric thresholds; always produces at least one risk flag per candidate |
| SCR-07 | Configurable Scoring Weights -- weights and min composite threshold configurable with defaults | ScoringWeightsConfig frozen dataclass with validation; integrated into existing `MarketScannerConfig` |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Coarse screening rules | API / Backend (pure functions) | -- | Filtering logic is business logic, no I/O needed |
| Composite score calculation | API / Backend (pure functions) | -- | Weighted normalization of numerical inputs |
| Reason generation | API / Backend (pure functions) | -- | Deterministic template-based text from metrics |
| Scoring weight configuration | API / Backend (frozen dataclass) | -- | Config validation, same tier as existing MarketScannerConfig |
| Market data fetching for screening | API / Backend (Phase 27) | -- | External API calls, not this phase |
| Candidate persistence | Database (Phase 25 repos) | -- | Repos already built, this phase produces data for them |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3.12+ | 3.12 | Runtime | Project constraint [VERIFIED: pyproject.toml] |
| Pydantic 2.12+ | 2.12+ | Data validation for screening/scoring models | Existing project standard [VERIFIED: pyproject.toml] |
| pytest 9.0+ | 9.0+ | Unit testing with asyncio support | Existing project standard [VERIFIED: pyproject.toml] |
| pytest-asyncio | latest | Async test support | Existing project standard [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hypothesis 6.15+ | 6.15+ | Property-based testing for normalization edge cases | Scoring normalization boundary testing |
| scipy 1.16.0 | 1.16.0 | Statistical percentile calculation | Valuation percentile normalization [VERIFIED: installed] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom normalization functions | scipy.stats.percentileofscore | scipy is already a dependency; use for percentile ranking only, custom for linear clamp normalization |
| New ScoringWeightsConfig | Extend MarketScannerConfig | Adding weights to existing config is simpler; however, separate config allows independent validation and future user-customization |

**Installation:**
No new packages required -- all dependencies already in pyproject.toml.

**Version verification:**
```
scipy: 1.16.0 (already installed in uv environment)
pydantic: >=2.12.5 (in pyproject.toml)
pytest: >=9.0 (in pyproject.toml)
```

## Architecture Patterns

### System Architecture Diagram

```
                         Phase 25 Data Foundation
                         +---------------------+
                         | MarketScannerConfig  |
                         | (frozen dataclass)   |
                         | thresholds + weights |
                         +---------+-----------+
                                   | consumed by
         +-------------------------+-------------------------+
         |                         |                         |
         v                         v                         v
+-----------------+   +---------------------+   +----------------------+
| CoarseScreener  |   | CompositeScorer     |   | ReasonGenerator     |
| (pure functions)|   | (pure functions)    |   | (pure functions)    |
|                 |   |                     |   |                     |
| Input:          |   | Input:              |   | Input:              |
| - MarketSnapshot|   | - margin_of_safety  |   | - ScreeningResult   |
| - FinancialData |   | - alpha_score       |   | - CompositeScore    |
| - Config        |   | - risk_level        |   | - RiskFlags         |
|                 |   | - yield_gap         |   |                     |
| Output:         |   | - val_percentile    |   | Output:             |
| - ScreeningResult|  | - weights           |   | - reasons: list     |
|   passed: bool  |   |                     |   | - risk_flags: list  |
|   rank_score    |   | Output:             |   |                     |
|   excluded_reason|  | - CompositeScore    |   +----------------------+
|   signals: dict |   |   composite: 0-100  |
+--------+--------+   |   components: dict  |
         |             +----------+----------+
         |                        |
         v                        v
   Phase 27 Scan Orchestrator consumes all three outputs
   to build MarketScanCandidateDB records
```

### Recommended Project Structure
```
stockvaluefinder/market_scanner/
+-- __init__.py                # Package exports (Phase 25)
+-- config.py                  # MarketScannerConfig (Phase 25, extend with ScoringWeightsConfig)
+-- coarse_screener.py         # SCR-01: Hard-exclusion rules + soft prioritization
+-- composite_scorer.py        # SCR-05 + SCR-07: Normalization + weighted scoring
+-- reason_generator.py        # SCR-06: Deterministic reason/flag generation
+-- models.py                  # ScreeningResult, CompositeScore, CandidateReasons (Pydantic)

tests/unit/test_market_scanner/
+-- __init__.py
+-- test_config.py             # Phase 25
+-- test_models.py             # Phase 25
+-- test_orm.py                # Phase 25
+-- test_repositories.py       # Phase 25
+-- test_coarse_screener.py    # Phase 26: SCR-01 tests
+-- test_composite_scorer.py   # Phase 26: SCR-05 + SCR-07 tests
+-- test_reason_generator.py   # Phase 26: SCR-06 tests
+-- test_screening_models.py   # Phase 26: New Pydantic model tests
```

### Pattern 1: Hard-Exclusion + Soft-Prioritization Coarse Screen
**What:** The coarse screen applies hard exclusion rules first (any failure = excluded), then ranks surviving stocks by composite prioritization signals.
**When to use:** Layer 1 of the 3-layer screening funnel.
**Example:**
```python
# Source: Pattern derived from PRD requirements and PITFALLS.md Pitfall 2
@dataclass(frozen=True)
class ScreeningSnapshot:
    """Input data for coarse screening (fetched by Phase 27)."""
    ticker: str
    name: str
    index_code: str
    is_st: bool                  # ST status from market data
    is_suspended: bool           # Suspension status from market data
    has_price_data: bool         # Price data available
    turnover_ratio: float        # Daily turnover ratio (liquidity)
    pe_ttm: float | None         # PE TTM (None = negative earnings)
    pb_ratio: float | None       # PB ratio
    dividend_yield: float        # Gross dividend yield
    price_vs_52w_high: float     # Current price / 52-week high (drawdown)
    ocf_positive_years: int      # Consecutive years of positive OCF
    market_cap: float            # Market cap for liquidity proxy

def screen_stock(
    snapshot: ScreeningSnapshot,
    config: MarketScannerConfig,
) -> ScreeningResult:
    """Apply hard-exclusion rules, then compute prioritization score."""
    # Hard exclusions (any True = excluded)
    exclusions = []
    if snapshot.is_st:
        exclusions.append("ST stock")
    if snapshot.is_suspended:
        exclusions.append("Suspended")
    if not snapshot.has_price_data:
        exclusions.append("Missing price data")
    if snapshot.turnover_ratio < config.min_turnover_ratio:
        exclusions.append("Below minimum liquidity")
    if snapshot.ocf_positive_years < config.min_ocf_positive_years:
        exclusions.append("Persistently negative operating cash flow")

    passed = len(exclusions) == 0

    # Soft prioritization (only meaningful for stocks that passed)
    rank_score = 0.0
    if passed:
        rank_score = _compute_rank_score(snapshot)

    return ScreeningResult(
        ticker=snapshot.ticker,
        passed=passed,
        excluded_reason="; ".join(exclusions) if exclusions else None,
        rank_score=rank_score,
    )
```

### Pattern 2: Component Normalization to 0-100 with Configurable Weights
**What:** Each scoring dimension is normalized to 0-100 using domain-specific mapping functions, then combined with configurable weights.
**When to use:** SCR-05 composite scoring.
**Example:**
```python
# Source: Pattern from existing alpha_service.py normalization functions
def normalize_safety_margin(margin_of_safety: float, min_threshold: float = 0.30) -> float:
    """Map margin of safety to 0-100.

    Linear mapping: 0% -> 0, 30% -> 50, 60% -> 100.
    Negative margins map to 0.
    """
    if margin_of_safety <= 0:
        return 0.0
    return round(min(100.0, (margin_of_safety / 0.60) * 100.0), 2)

def normalize_risk_penalty(risk_level: RiskLevel) -> float:
    """Map risk level to penalty score (inverted: LOW risk = HIGH score).

    LOW=100, MEDIUM=50, HIGH=0, CRITICAL=0.
    """
    mapping = {
        RiskLevel.LOW: 100.0,
        RiskLevel.MEDIUM: 50.0,
        RiskLevel.HIGH: 0.0,
        RiskLevel.CRITICAL: 0.0,
    }
    return mapping[risk_level]

def normalize_yield_gap(yield_gap: float) -> float:
    """Map yield gap to 0-100 using linear clamp [-2%, +4%]."""
    clamped = max(-0.02, min(0.04, yield_gap))
    return round(((clamped + 0.02) / 0.06) * 100.0, 2)

def normalize_valuation_percentile(percentile_rank: float) -> float:
    """Map valuation percentile to 0-100 (lower percentile = cheaper = higher score).

    Inverted: 5th percentile -> 95 score, 95th percentile -> 5 score.
    """
    return round(max(0.0, min(100.0, 100.0 - percentile_rank)), 2)
```

### Pattern 3: Deterministic Reason Generation from Metric Thresholds
**What:** Rule-based templates generate structured reasons and risk flags from computed metrics. No LLM involved.
**When to use:** SCR-06 candidate explanation.
**Example:**
```python
# Source: Pattern from PRD SCR-06 and PITFALLS.md compliance guidance
def generate_reasons(
    screening_result: ScreeningResult,
    composite_score: CompositeScore,
    valuation_result: ValuationResult | None = None,
    risk_score: RiskScore | None = None,
    yield_gap: YieldGap | None = None,
) -> CandidateReasons:
    """Generate deterministic selection reasons and risk flags."""
    reasons: list[str] = []
    risk_flags: list[str] = []

    # Safety margin reason
    if valuation_result and valuation_result.margin_of_safety >= 0.30:
        reasons.append(
            f"Safety margin {valuation_result.margin_of_safety:.0%}, "
            f"above 30% threshold"
        )
    elif valuation_result:
        risk_flags.append(
            f"Safety margin {valuation_result.margin_of_safety:.0%} "
            f"below 30% threshold"
        )

    # Risk level flag (always produce at least one risk-aware flag)
    if risk_score:
        if risk_score.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            risk_flags.append(
                f"Risk level {risk_score.risk_level.value}, "
                f"M-Score={risk_score.m_score:.2f}"
            )
        if risk_score.red_flags:
            risk_flags.append(
                f"{len(risk_score.red_flags)} risk indicator(s): "
                f"{'; '.join(risk_score.red_flags[:3])}"
            )

    # Compliance: ensure at least one risk flag
    if not risk_flags:
        risk_flags.append("Standard risk factors apply; review full analysis")

    return CandidateReasons(
        reasons=reasons,
        risk_flags=risk_flags,
    )
```

### Anti-Patterns to Avoid
- **Anti-pattern: Hardcoding thresholds in business logic.** Every threshold must come from `MarketScannerConfig` or `ScoringWeightsConfig`. Magic numbers in screening rules or scoring functions violate SCR-04 and SCR-07. [CITED: PITFALLS.md Phase-Specific Warnings]
- **Anti-pattern: Using LLM for reason generation.** SCR-06 explicitly requires deterministic metrics-derived reasons. The existing `NarrativeService` is for optional LLM enhancement, not the structured reason generation. [CITED: REQUIREMENTS.md SCR-06]
- **Anti-pattern: Composite score without normalization.** Raw metric values (margin_of_safety = 0.38, alpha_score = 72.5, risk_penalty = varying enums) cannot be directly weighted. All must be normalized to 0-100 first. [CITED: REQUIREMENTS.md SCR-05]
- **Anti-pattern: All-positive candidate reasons without risk flags.** Compliance requires every candidate to have at least one risk flag, even if the stock appears strong. [CITED: PITFALLS.md Pitfall 6]
- **Anti-pattern: Screening logic that calls external APIs.** The coarse screener must be a pure function that receives pre-fetched data as input. External API orchestration belongs in Phase 27. [CITED: PROJECT.md architecture pattern "pure function services"]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile ranking within a group | Custom percentile sorting | `scipy.stats.percentileofscore` | Handles edge cases (ties, boundary values) correctly |
| Weight validation (sums to 1.0) | Manual float comparison | Frozen dataclass `__post_init__` with `abs(sum - 1.0) > epsilon` | IEEE 754 float comparison is tricky; existing pattern from `alpha_service.py` |
| Score clamping to 0-100 | Repeated if/min/max blocks | Dedicated normalization functions per dimension | Each dimension has domain-specific mapping (linear, tiered, inverted) |
| Enum-to-score mapping | If/elif chains | Dict mapping (existing pattern from `alpha_service.py`) | Cleaner, testable, auditable |

**Key insight:** The alpha_service.py normalization functions (`normalize_roic_wacc_score`, `normalize_capex_score`, `normalize_policy_score`, `normalize_moat_score`) are the exact pattern to follow. The composite scorer introduces 5 new normalization functions with domain-specific mappings for the scanner's different dimensions.

## Common Pitfalls

### Pitfall 1: None Values Crashing the Composite Scorer
**What goes wrong:** The composite scorer receives `None` for one or more components (e.g., no Alpha score computed yet, no yield gap for non-dividend stocks). A `TypeError` crashes the weighted sum calculation.
**Why it happens:** Phase 27's daily scan may not have Alpha scores for all stocks. Weekly scans compute Alpha but daily scans may use cached or absent values. Some stocks do not pay dividends (yield_gap = None).
**How to avoid:** Every normalization function must handle `None` input by returning a default score (typically 0.0 or 50.0 depending on dimension). The composite scorer must accept `float | None` for each component and apply the default before weighting.
**Warning signs:** `TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'` in composite scorer.

### Pitfall 2: Coarse Screen Missing Operating Cash Flow Check
**What goes wrong:** The coarse screen filters by PE/PB and ST status but does not check operating cash flow, allowing value traps through. PITFALLS.md Pitfall 2 specifically identifies this.
**Why it happens:** OCF data comes from financial reports, which require a separate data fetch. Developers may defer the OCF check because it is harder to obtain than price data, or use the presence of financial data as a proxy for positive OCF.
**How to avoid:** Make OCF positivity a hard-exclusion rule in the coarse screen. The `ocf_positive_years` field in `ScreeningSnapshot` must be populated before the screen runs. Default to exclusion if OCF data is unavailable (conservative approach).
**Warning signs:** Candidates list dominated by cyclical industrials or real estate with PE < 5 and negative OCF trend.

### Pitfall 3: Rank Score Ordering Does Not Match Composite Score Ordering
**What goes wrong:** The coarse screen ranks stocks by a lightweight `rank_score` (based on PE/PB/dividend/drawdown signals). The composite score uses 5 different dimensions (safety margin, Alpha, risk, yield gap, valuation percentile). A stock ranked #1 by coarse screen may score 45/100 in composite and fail the `min_composite_score` threshold.
**Why it happens:** The two scoring systems measure different things. Coarse screen is about "which stocks are most interesting for deep analysis"; composite score is about "which stocks are best overall candidates." They are not supposed to produce identical rankings.
**How to avoid:** Document this explicitly. The coarse screen's `rank_score` determines which stocks get expensive DCF analysis (Top N). The composite score determines final candidate ranking. Do not assume or enforce consistency between the two. Add `rank_in_coarse_screen` to candidate output for transparency.
**Warning signs:** None of the top-10 coarse-screened stocks making it through composite scoring; or developers "fixing" composite weights to match coarse screen rankings.

### Pitfall 4: Scoring Weights Not Summing to 1.0 Due to Float Precision
**What goes wrong:** Default weights (0.35 + 0.25 + 0.20 + 0.10 + 0.10 = 1.0) work fine, but when users customize weights, floating-point arithmetic may produce sums like 0.9999999999999998 or 1.0000000000000002, causing validation to reject valid configurations.
**Why it happens:** IEEE 754 double-precision floats cannot exactly represent 0.35 (which is 0.34999999... in binary). Summing five such values accumulates rounding errors.
**How to avoid:** Use `abs(sum(weights) - 1.0) > 0.01` for validation (epsilon tolerance), matching the existing pattern in `alpha_service.py` line 179.
**Warning signs:** Valid weight configurations rejected by `__post_init__` validation.

### Pitfall 5: Compliance Risk from Missing Risk Flags
**What goes wrong:** A strong candidate (safety margin 45%, Alpha 85, risk LOW, yield gap positive) generates only positive reasons and zero risk flags. The output reads like a "strong buy" recommendation.
**Why it happens:** The reason generator only adds risk flags when metrics cross danger thresholds. A stock that passes all checks generates no negative flags.
**How to avoid:** Always append at least one generic risk flag ("Standard risk factors apply; review full analysis" or "Data as of [date]; market conditions may have changed"). This is a hard rule, not a soft suggestion.
**Warning signs:** Candidate output with `risk_flags: []` in test data or API responses.

## Code Examples

Verified patterns from existing codebase:

### Existing Normalization Pattern (from alpha_service.py)
```python
# Source: stockvaluefinder/services/alpha_service.py lines 26-62
def normalize_roic_wacc_score(spread: float | None) -> float:
    """Map ROIC-WACC spread to 0-100 using linear clamp +/-10%."""
    if spread is None:
        return 0.0
    if spread != spread:  # NaN guard
        return 0.0
    clamped = max(
        alpha_config.SPREAD_CLAMP_MIN,
        min(alpha_config.SPREAD_CLAMP_MAX, spread),
    )
    range_width = alpha_config.SPREAD_CLAMP_MAX - alpha_config.SPREAD_CLAMP_MIN
    return round((clamped - alpha_config.SPREAD_CLAMP_MIN) / range_width * 100.0, 2)
```

### Existing Weighted Sum Pattern (from alpha_service.py)
```python
# Source: stockvaluefinder/services/alpha_service.py lines 145-187
def calculate_alpha_score(
    roic_wacc_score: float,
    capex_score: float,
    policy_score: float,
    moat_score: float,
    weights: tuple[float, float, float, float] = (0.40, 0.30, 0.20, 0.10),
) -> float:
    if len(weights) != 4:
        raise ValueError(f"weights must have exactly 4 elements, got {len(weights)}")
    if abs(sum(weights) - 1.0) > 0.01:
        raise ValueError(f"weights must sum to approximately 1.0, got {sum(weights)}")
    raw = (
        roic_wacc_score * weights[0]
        + capex_score * weights[1]
        + policy_score * weights[2]
        + moat_score * weights[3]
    )
    return round(raw, 2)
```

### Existing Frozen Config Pattern (from market_scanner/config.py)
```python
# Source: stockvaluefinder/market_scanner/config.py lines 14-76
@dataclass(frozen=True)
class MarketScannerConfig:
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
        if not self.index_codes:
            raise ValueError("index_codes must not be empty")
        # ... validation ...
```

### Existing Risk Level Determination (from risk_service.py)
```python
# Source: stockvaluefinder/services/risk_service.py lines 647-681
def determine_risk_level(m_score: float, red_flags_count: int) -> RiskLevel:
    if m_score >= -1.78:
        base_risk = RiskLevel.HIGH
        if red_flags_count >= 3:
            base_risk = RiskLevel.CRITICAL
    elif m_score < -2.22:
        base_risk = RiskLevel.LOW
    else:
        base_risk = RiskLevel.MEDIUM
    return base_risk
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM-generated investment reasons | Deterministic template-based reasons | v1.5 design decision | Auditable, reproducible, no hallucination risk |
| Fixed hardcoded weights | Configurable frozen dataclass weights | v1.5 SCR-07 | Users can tune scoring without code changes |
| Single-pass screening | 3-layer funnel (coarse -> DCF -> quality review) | v1.5 design | Prevents value traps from reaching candidate list |

**Deprecated/outdated:**
- Using LLM for reason text generation in screening context (SCR-06 explicitly prohibits)
- Single-score ranking without dimension normalization (SCR-05 requires 0-100 normalization before weighting)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The coarse screen operates on a `ScreeningSnapshot` dataclass that Phase 27 populates from batch market data | Coarse Screener | If market data fields differ, screener input model needs adjustment |
| A2 | `scipy.stats.percentileofscore` is available and suitable for valuation percentile normalization | Composite Scorer | If scipy percentile behavior differs from expected, normalization will be wrong |
| A3 | The existing `MarketScannerConfig` will be extended (not replaced) with new fields for screening thresholds | Config | If config needs restructuring, Phase 25 tests may break |
| A4 | Valuation percentile data (PE/PB percentile within index peers) will be computed by Phase 27 (IDX-04) and passed as input to the composite scorer | Composite Scorer | If Phase 27 does not provide this, the valuation_percentile dimension defaults to 50 |
| A5 | `min_turnover_ratio` and `min_ocf_positive_years` thresholds need to be added to MarketScannerConfig for coarse screening | Config | These thresholds are referenced in SCR-01 but not yet in config; must be added |

## Open Questions

1. **Additional screening thresholds needed in config?**
   - What we know: `MarketScannerConfig` has `min_margin_of_safety` and `min_composite_score` but lacks `min_turnover_ratio`, `min_ocf_positive_years`, and other coarse screen thresholds.
   - What's unclear: Should these be added to the existing `MarketScannerConfig` or placed in a separate `ScreeningConfig`?
   - Recommendation: Add to existing `MarketScannerConfig` to keep a single config object. Add `min_turnover_ratio: float = 0.01`, `min_ocf_positive_years: int = 2`, `min_market_cap: float = 1_000_000_000`. This requires updating the existing config and its tests.

2. **ScoringWeightsConfig as separate dataclass or nested in MarketScannerConfig?**
   - What we know: SCR-07 requires configurable weights. The default weights are 0.35/0.25/0.20/0.10/0.10.
   - What's unclear: Whether to nest the weights in MarketScannerConfig or keep them as a separate frozen dataclass.
   - Recommendation: Create `ScoringWeightsConfig` as a separate frozen dataclass with validation, and add a `scoring_weights: ScoringWeightsConfig` field to `MarketScannerConfig`. This separates concerns while keeping a single config entry point.

3. **Valuation percentile data availability for Phase 26 unit tests?**
   - What we know: IDX-04 (valuation percentile calculation) is assigned to Phase 27. The composite scorer needs this as input.
   - What's unclear: How to test the scorer without the actual percentile calculator.
   - Recommendation: The composite scorer accepts `valuation_percentile_score: float` as a pre-normalized 0-100 value. Tests provide mock values. Phase 27 computes the actual percentile and passes it in. Clean separation.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All code | Yes | 3.12 | -- |
| PostgreSQL | Not needed for Phase 26 pure functions | N/A | -- | -- |
| Redis | Not needed for Phase 26 pure functions | N/A | -- | -- |
| scipy | Percentile normalization | Yes | 1.16.0 | -- |
| pytest | Testing | Yes | 9.0+ | -- |
| mypy | Type checking | Yes | 1.19+ | -- |
| ruff | Linting/formatting | Yes | 0.15+ | -- |

**Missing dependencies with no fallback:**
- None

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | stockvaluefinder/pytest.ini |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/test_coarse_screener.py tests/unit/test_market_scanner/test_composite_scorer.py tests/unit/test_market_scanner/test_reason_generator.py -q --no-cov` |
| Full suite command | `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCR-01 | Excludes ST stocks | unit | `uv run pytest tests/unit/test_market_scanner/test_coarse_screener.py::test_excludes_st_stock -q --no-cov` | No, Wave 0 |
| SCR-01 | Excludes suspended stocks | unit | Same file | No, Wave 0 |
| SCR-01 | Excludes missing price data | unit | Same file | No, Wave 0 |
| SCR-01 | Excludes low liquidity stocks | unit | Same file | No, Wave 0 |
| SCR-01 | Excludes negative OCF stocks | unit | Same file | No, Wave 0 |
| SCR-01 | Prioritizes low PE/PB | unit | Same file | No, Wave 0 |
| SCR-01 | Prioritizes high dividend yield | unit | Same file | No, Wave 0 |
| SCR-01 | Prioritizes price drawdown | unit | Same file | No, Wave 0 |
| SCR-05 | Normalizes safety margin to 0-100 | unit | `uv run pytest tests/unit/test_market_scanner/test_composite_scorer.py::test_normalize_safety_margin -q --no-cov` | No, Wave 0 |
| SCR-05 | Normalizes risk penalty from enum | unit | Same file | No, Wave 0 |
| SCR-05 | Normalizes yield gap | unit | Same file | No, Wave 0 |
| SCR-05 | Normalizes valuation percentile | unit | Same file | No, Wave 0 |
| SCR-05 | Calculates weighted composite score | unit | Same file | No, Wave 0 |
| SCR-05 | Handles None components gracefully | unit | Same file | No, Wave 0 |
| SCR-06 | Generates selection reasons from metrics | unit | `uv run pytest tests/unit/test_market_scanner/test_reason_generator.py::test_generate_reasons -q --no-cov` | No, Wave 0 |
| SCR-06 | Always produces at least one risk flag | unit | Same file | No, Wave 0 |
| SCR-06 | No LLM involvement | code review | N/A | N/A |
| SCR-07 | Default weights sum to 1.0 | unit | `uv run pytest tests/unit/test_market_scanner/test_composite_scorer.py::test_default_weights -q --no-cov` | No, Wave 0 |
| SCR-07 | Custom weights validated | unit | Same file | No, Wave 0 |
| SCR-07 | Min composite threshold enforced | unit | Same file | No, Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_market_scanner/test_coarse_screener.py -q --no-cov` (or relevant test file)
- **Per wave merge:** `uv run pytest tests/unit/test_market_scanner/ -v`
- **Phase gate:** Full market scanner test suite green before phase complete

### Wave 0 Gaps
- [ ] `tests/unit/test_market_scanner/test_coarse_screener.py` -- covers SCR-01
- [ ] `tests/unit/test_market_scanner/test_composite_scorer.py` -- covers SCR-05 + SCR-07
- [ ] `tests/unit/test_market_scanner/test_reason_generator.py` -- covers SCR-06
- [ ] `tests/unit/test_market_scanner/test_screening_models.py` -- covers new Pydantic models
- [ ] ScoringWeightsConfig addition to `config.py` and update to `test_config.py`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 26 is pure functions, no auth |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | No API endpoints in this phase |
| V5 Input Validation | Yes | Pydantic model validation on all screening/scoring inputs |
| V6 Cryptography | No | No crypto operations |

### Known Threat Patterns for Screening & Scoring

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed ScreeningSnapshot input | Tampering | Pydantic validation with type constraints and range checks |
| Weight injection (sum != 1.0) | Tampering | Frozen dataclass `__post_init__` validation with epsilon tolerance |
| Compliance violation (no risk flags) | Repudiation | Hard-coded rule: `generate_reasons` always produces at least one risk flag |
| Score manipulation via None injection | Tampering | Default fallback values for all None components |

## Sources

### Primary (HIGH confidence)
- Codebase: `stockvaluefinder/market_scanner/config.py` -- MarketScannerConfig structure and validation pattern
- Codebase: `stockvaluefinder/services/alpha_service.py` -- normalization and weighted scoring pattern
- Codebase: `stockvaluefinder/services/risk_service.py` -- risk level determination and red flag generation
- Codebase: `stockvaluefinder/services/valuation_service.py` -- margin of safety calculation
- Codebase: `stockvaluefinder/services/yield_service.py` -- yield gap calculation
- Codebase: `stockvaluefinder/models/alpha.py` -- AlphaComponentScores model pattern
- Codebase: `stockvaluefinder/models/market_scanner.py` -- existing Pydantic model patterns
- Codebase: `stockvaluefinder/repositories/market_scan_repo.py` -- candidate persistence interface
- Codebase: `.planning/REQUIREMENTS.md` -- SCR-01, SCR-05, SCR-06, SCR-07 definitions
- Codebase: `.planning/research/PITFALLS.md` -- verified pitfalls for v1.5

### Secondary (MEDIUM confidence)
- Codebase: `stockvaluefinder/db/models/market_scan.py` -- MarketScanCandidateDB.screening_snapshot JSONB structure
- Codebase: `stockvaluefinder/models/enums.py` -- RiskLevel, ScanStatus, ScanType enums
- Phase 25 summaries: 25-01-SUMMARY.md, 25-02-SUMMARY.md -- verified data foundation completeness

### Tertiary (LOW confidence)
- None -- all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing codebase patterns
- Architecture: HIGH -- follows established pure-function service pattern with frozen config
- Pitfalls: HIGH -- codebase-verified with PITFALLS.md providing deep analysis

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable domain, no external API changes expected)
