# Phase 27: Market Scanner Service - Research

**Researched:** 2026-06-04
**Domain:** Scan orchestration, batch market data fetching, deep analysis pipeline, valuation percentile, single-stock failure isolation
**Confidence:** HIGH

## Summary

Phase 27 builds the scan orchestration layer that wires together all components from Phases 25-26 into a complete pipeline: constituent sync triggers batch market data fetch, which feeds the coarse screener, whose top-N survivors get DCF valuation, risk review, composite scoring, and reason generation before being persisted as candidates. This phase introduces three new capabilities not present in earlier phases: (1) batch market snapshot fetching for all index constituents using AKShare's bulk `stock_zh_a_spot_em()` API, (2) historical PE/PB percentile calculation using 5-year valuation histories, and (3) a scan orchestrator service that manages the full funnel with per-stock failure isolation.

The key architectural decision is that the scanner **orchestrates** existing services rather than recalculating. It calls `ExternalDataService` for data, `coarse_screener`/`composite_scorer`/`reason_generator` for screening logic, and repositories for persistence. The scanner itself handles batching, concurrency control via `asyncio.Semaphore`, rate limiting between external API calls, and partial-failure recording so one stock's data failure does not abort the entire scan.

**Primary recommendation:** Build three modules under `stockvaluefinder/market_scanner/` -- `batch_data_fetcher.py` for bulk market data + percentile calculation, `scan_orchestrator.py` for the full pipeline coordination, and a `quality_review.py` pure-function module for the SCR-03 risk gate. Each module should be independently testable with mocked external dependencies.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IDX-03 | Batch market data snapshot (PE TTM, PB, dividend yield, market cap, turnover, ST/suspension status) for all constituents with rate-limited API calls and caching | AKShare `stock_zh_a_spot_em()` returns all A-share real-time data in one call including PE, PB, market cap, turnover; new `batch_data_fetcher.py` module wraps this with constituent filtering and `ScreeningSnapshot` mapping |
| IDX-04 | Historical PE/PB percentile ranking for each stock within its index over 5-year history | New `calculate_valuation_percentile()` function using historical daily PE/PB from AKShare `stock_zh_a_hist()` or cached data, computed as percentile rank within current index peer group |
| SCR-02 | DCF valuation on top-N stocks from coarse screen with configurable safety margin threshold (>=30%) | Orchestrator calls existing `valuation_service.analyze_dcf_valuation()` with per-stock financial data; stocks with `margin_of_safety >= config.min_margin_of_safety` are flagged |
| SCR-03 | Risk and quality review checking ROIC-WACC spread, M-Score, cash flow divergence, leverage, dividend sustainability | New `quality_review.py` pure-function module that evaluates a stock against a checklist using existing `RiskScore` and `ValuationResult` outputs; only stocks passing all checks enter candidate list |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Batch market data fetching | API / Backend (async service) | External (AKShare) | Rate-limited external API orchestration |
| Valuation percentile calculation | API / Backend (pure function) | Database (cached history) | Statistical computation on historical data |
| DCF value confirmation | API / Backend (existing service) | -- | Reuses `valuation_service.analyze_dcf_valuation()` |
| Risk and quality review | API / Backend (pure function) | -- | Evaluates existing analysis results against a checklist |
| Scan pipeline orchestration | API / Backend (async service) | Database (repositories) | Coordinates all components, manages state transitions |
| Candidate persistence | Database (repositories) | -- | Phase 25 repositories already built |
| Single-stock failure isolation | API / Backend (orchestrator) | -- | try/except per stock, error logging, partial_failed state |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python 3.12+ | 3.12 | Runtime | Project constraint [VERIFIED: pyproject.toml] |
| asyncio | stdlib | Concurrency for batch processing | Built-in, `asyncio.Semaphore` for rate limiting |
| Pydantic 2.12+ | 2.12+ | Data validation | Existing project standard [VERIFIED: pyproject.toml] |
| pytest 9.0+ | 9.0+ | Unit testing with asyncio support | Existing project standard [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| scipy 1.16.0 | 1.16.0 | `percentileofscore` for valuation percentile | IDX-04 percentile ranking [VERIFIED: installed] |
| numpy | bundled with scipy | Array operations for percentile batch calculation | When computing percentiles for multiple stocks at once |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `scipy.stats.percentileofscore` | Manual sorting + rank calculation | scipy handles ties, boundary values, and interpolation correctly; manual is error-prone |
| New `batch_data_fetcher.py` | Extend `ExternalDataService` | Extending data_service would couple batch scanning logic into the general-purpose data layer; separate module keeps concerns clean |
| New `quality_review.py` | Inline in orchestrator | Quality review has distinct rules that should be testable independently; pure-function module enables unit testing without orchestrator setup |

**Installation:**
No new packages required -- all dependencies already in pyproject.toml.

**Version verification:**
```
scipy: 1.16.0 (already in pyproject.toml dependencies)
pydantic: >=2.12.5 (in pyproject.toml)
pytest: >=9.0 (in pyproject.toml)
asyncio: stdlib
```

## Architecture Patterns

### System Architecture Diagram

```
Phase 27 Scan Pipeline -- Data Flow

                    +-----------------------+
                    |  MarketScannerConfig   |
                    |  (frozen dataclass)    |
                    +-----------+-----------+
                                |
    +---------------------------+-------------------------------+
    |                           |                               |
    v                           v                               v
+--------------------+  +--------------------+  +--------------------------+
| BatchDataFetcher   |  | ScanOrchestrator   |  | QualityReview            |
| (async service)    |  | (async service)    |  | (pure functions)         |
|                    |  |                    |  |                          |
| Input:             |  | Input:             |  | Input:                   |
| - index_code       |  | - config           |  | - ValuationResult        |
| - config           |  | - data_service     |  | - RiskScore              |
|                    |  | - repositories     |  | - YieldGap               |
| Output:            |  | - BatchDataFetcher |  | - ROIC-WACC spread       |
| - ScreeningSnapshot|  |                    |  |                          |
|   list             |  | Pipeline:          |  | Output:                  |
| - percentile data  |  | 1. Create run      |  | - passed: bool           |
|                    |  | 2. Fetch snapshots |  | - failure_reasons: list  |
+--------+-----------+  | 3. Coarse screen   |  +--------------------------+
         |              | 4. Top N -> DCF     |
         |              | 5. Quality review   |
         |              | 6. Composite score  |
         |              | 7. Generate reasons |
         |              | 8. Persist candidate|
         |              +--------+-----------+
         |                       |
         v                       v
    +----------------+  +-------------------+
    | External Data  |  | Phase 25 Repos    |
    | Service        |  | - ScanRunRepo     |
    | - get_current_ |  | - CandidateRepo   |
    |   price()      |  | - ConstituentRepo |
    | - get_financial|  +-------------------+
    |   _report()    |
    | - get_dividend |
    |   _yield()     |
    +-------+--------+
            |
            v
    +----------------+
    | AKShare        |
    | stock_zh_a_    |
    | spot_em()      |  <-- Bulk API: all A-shares in 1 call
    +----------------+
```

### Recommended Project Structure
```
stockvaluefinder/market_scanner/
+-- __init__.py                # Package exports (Phase 25, extend with new modules)
+-- config.py                  # MarketScannerConfig (Phase 25, no changes needed)
+-- models.py                  # Screening models (Phase 26, no changes needed)
+-- coarse_screener.py         # Phase 26 -- consumed by orchestrator
+-- composite_scorer.py        # Phase 26 -- consumed by orchestrator
+-- reason_generator.py        # Phase 26 -- consumed by orchestrator
+-- batch_data_fetcher.py      # NEW: IDX-03 + IDX-04 batch market snapshot + percentile
+-- quality_review.py          # NEW: SCR-03 risk gate pure functions
+-- scan_orchestrator.py       # NEW: Full scan pipeline coordinator

tests/unit/test_market_scanner/
+-- __init__.py                # Phase 25
+-- test_config.py             # Phase 25
+-- test_models.py             # Phase 25
+-- test_orm.py                # Phase 25
+-- test_repositories.py       # Phase 25
+-- test_screening_models.py   # Phase 26
+-- test_coarse_screener.py    # Phase 26
+-- test_composite_scorer.py   # Phase 26
+-- test_reason_generator.py   # Phase 26
+-- test_batch_data_fetcher.py # NEW: IDX-03 + IDX-04 tests
+-- test_quality_review.py     # NEW: SCR-03 tests
+-- test_scan_orchestrator.py  # NEW: Integration tests with mocked deps
```

### Pattern 1: Bulk Market Snapshot via AKShare stock_zh_a_spot_em()
**What:** Fetch real-time market data for ALL A-share stocks in a single API call, then filter to index constituents.
**When to use:** IDX-03 batch market data snapshot at the start of each scan.
**Example:**
```python
# Source: [CITED: AKShare docs] -- stock_zh_a_spot_em returns all A-shares
async def fetch_market_snapshots(
    self,
    tickers: set[str],
    config: MarketScannerConfig,
) -> dict[str, ScreeningSnapshot]:
    """Fetch market snapshots for a set of tickers using bulk API.

    Uses AKShare stock_zh_a_spot_em() which returns ALL A-share real-time
    data in one call (~5000 stocks). Filters to requested tickers and maps
    to ScreeningSnapshot objects.

    Returns:
        Dict mapping ticker -> ScreeningSnapshot for successful fetches.
    """
    import akshare as ak

    # Single bulk call -- returns DataFrame with all A-shares
    df = await self._run_akshare(ak.stock_zh_a_spot_em)

    # Map 6-digit AKShare codes to project ticker format
    df["_ticker"] = df["代码"].apply(self._to_ticker_format)

    # Filter to requested tickers
    filtered = df[df["_ticker"].isin(tickers)]

    snapshots: dict[str, ScreeningSnapshot] = {}
    for _, row in filtered.iterrows():
        ticker = row["_ticker"]
        try:
            snapshot = ScreeningSnapshot(
                ticker=ticker,
                name=str(row.get("名称", "")),
                index_code="",  # filled by caller
                is_st=self._detect_st_status(row),
                is_suspended=self._detect_suspension(row),
                has_price_data=float(row.get("最新价", 0)) > 0,
                turnover_ratio=float(row.get("换手率", 0)),
                pe_ttm=self._safe_float(row.get("市盈率-动态")),
                pb_ratio=self._safe_float(row.get("市净率")),
                dividend_yield=0.0,  # filled from separate API
                price_vs_52w_high=1.0,  # needs 52w high calculation
                ocf_positive_years=0,  # filled from financial data
                market_cap=float(row.get("总市值", 0)),
            )
            snapshots[ticker] = snapshot
        except Exception as e:
            logger.warning(f"Failed to build snapshot for {ticker}: {e}")
            self._errors[ticker] = str(e)

    return snapshots
```

### Pattern 2: Valuation Percentile Calculation (IDX-04)
**What:** Compute where a stock's current PE/PB sits relative to its 5-year history within the index peer group.
**When to use:** After fetching market snapshots, before composite scoring.
**Example:**
```python
# Source: scipy.stats.percentileofscore pattern
from scipy.stats import percentileofscore

def calculate_valuation_percentile(
    current_value: float,
    historical_values: list[float],
) -> float | None:
    """Calculate percentile rank of current value within historical series.

    Args:
        current_value: Current PE TTM or PB ratio.
        historical_values: Historical daily PE/PB values (5 years).

    Returns:
        Percentile rank (0-100), or None if insufficient data.
    """
    if not historical_values or len(historical_values) < 20:
        return None  # Insufficient history

    if current_value <= 0 or any(v <= 0 for v in historical_values):
        valid = [v for v in historical_values if v > 0]
        if len(valid) < 20:
            return None
        return round(float(percentileofscore(valid, current_value, kind='rank')), 2)

    return round(float(percentileofscore(historical_values, current_value, kind='rank')), 2)
```

### Pattern 3: Quality Review Gate (SCR-03)
**What:** A pure-function checklist that evaluates whether a value-confirmed stock passes the quality bar.
**When to use:** After DCF confirms safety margin >= threshold, before composite scoring.
**Example:**
```python
# Source: SCR-03 requirement specification
def review_stock_quality(
    valuation_result: ValuationResult | None,
    risk_score: RiskScore | None,
    yield_gap: YieldGap | None,
    roic_wacc_spread: float | None = None,
) -> QualityReviewResult:
    """Evaluate whether a stock passes quality review (SCR-03).

    Checks:
    1. ROIC-WACC spread: positive = pass
    2. M-Score: below -1.78 manipulation threshold
    3. Cash flow divergence: not detected
    4. Leverage: debt/equity ratio acceptable
    5. Dividend sustainability: payout ratio reasonable

    Any single failure = stock does NOT enter candidate list.
    All checks must pass, or have unavailable data (graceful degradation).
    """
    failures: list[str] = []

    # Check 1: ROIC-WACC spread
    if roic_wacc_spread is not None and roic_wacc_spread <= 0:
        failures.append(f"ROIC-WACC spread {roic_wacc_spread:.2%} is non-positive")

    # Check 2: M-Score manipulation threshold
    if risk_score is not None:
        if risk_score.m_score >= -1.78:
            failures.append(f"M-Score {risk_score.m_score:.2f} above manipulation threshold")

    # Check 3: Cash flow divergence
    if risk_score is not None and risk_score.profit_cash_divergence:
        failures.append("Profit-cash flow divergence detected")

    # Check 4: Risk level gate
    if risk_score is not None and risk_score.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        failures.append(f"Risk level {risk_score.risk_level.value} exceeds acceptable threshold")

    return QualityReviewResult(
        passed=len(failures) == 0,
        failure_reasons=failures,
    )
```

### Pattern 4: Scan Orchestrator with Per-Stock Failure Isolation
**What:** The orchestrator wraps each stock's deep analysis in a try/except, recording failures without aborting the run.
**When to use:** Core scan pipeline loop in `scan_orchestrator.py`.
**Example:**
```python
# Source: PROJECT.md design decision -- single-stock failure isolation
async def _analyze_single_stock(
    self,
    ticker: str,
    snapshot: ScreeningSnapshot,
    config: MarketScannerConfig,
) -> StockAnalysisResult | None:
    """Run deep analysis for a single stock with failure isolation.

    Returns None on failure (logged, not raised).
    """
    try:
        # Step 1: DCF valuation
        financial_data = await self._data_service.get_financial_report(ticker)
        valuation = analyze_dcf_valuation(ticker, price, fcf, shares, dcf_params, valuation_id)

        # Step 2: Check safety margin threshold
        if valuation.margin_of_safety < config.min_margin_of_safety:
            return StockAnalysisResult(ticker=ticker, passed=False, reason="insufficient_safety_margin")

        # Step 3: Risk analysis
        prev_data = await self._data_service.get_financial_report(ticker, year - 1)
        risk_score = analyze_financial_risk(financial_data, prev_data)

        # Step 4: Quality review
        review = review_stock_quality(valuation, risk_score, yield_gap)
        if not review.passed:
            return StockAnalysisResult(ticker=ticker, passed=False, reason="quality_review_failed")

        # Step 5: Composite score
        composite = calculate_composite_score(
            margin_of_safety=valuation.margin_of_safety,
            alpha_score=None,
            risk_level=risk_score.risk_level,
            yield_gap_value=yield_gap.yield_gap if yield_gap else None,
            valuation_percentile=percentile,
            config=config,
        )

        return StockAnalysisResult(ticker=ticker, passed=True, composite=composite, ...)

    except Exception as e:
        logger.warning(f"Analysis failed for {ticker}: {e}")
        self._stock_errors[ticker] = str(e)
        return None  # Failure isolated, scan continues
```

### Anti-Patterns to Avoid
- **Anti-pattern: Calling get_current_price() per stock in batch.** Use `stock_zh_a_spot_em()` bulk API for all A-shares at once. Per-stock calls for 800 constituents would take 400+ seconds and risk IP blocking. [CITED: PITFALLS.md Pitfall 1]
- **Anti-pattern: Running DCF on all 800 stocks.** DCF is expensive (needs 3 financial statements per stock). Only run on stocks that pass the coarse screen (typically 50-100). [CITED: PITFALLS.md Integration Gotchas]
- **Anti-pattern: Using asyncio.gather without Semaphore for deep analysis.** Unbounded concurrency would overwhelm AKShare rate limits and external APIs. Use `asyncio.Semaphore(config.deep_analysis_concurrency)`. [CITED: PITFALLS.md Pitfall 1]
- **Anti-pattern: Hardcoding quality review thresholds.** SCR-03 says "configurable" but the config already has `min_margin_of_safety`. Quality review thresholds should come from config or be well-documented constants, not magic numbers. [CITED: REQUIREMENTS.md SCR-04]
- **Anti-pattern: Letting one stock's failure abort the entire scan.** EXE-04 requires single-stock failure isolation. Each stock must be wrapped in try/except. [CITED: REQUIREMENTS.md EXE-04]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile ranking | Custom sorting + index calculation | `scipy.stats.percentileofscore` | Handles ties, edge cases (min/max values), and interpolation correctly |
| Rate limiting between API calls | Custom sleep loops | `asyncio.Semaphore` + `request_delay_seconds` from config | Configurable, testable, standard pattern |
| Concurrent task execution | Manual task management | `asyncio.Semaphore` + `asyncio.gather` with `return_exceptions=True` | Built-in, well-tested, handles cancellation |
| Market data field mapping | Ad-hoc dict key lookups | Dedicated `_safe_float()` helper + `ScreeningSnapshot` Pydantic model | Pydantic validates types/ranges; helper handles NaN/None |
| Scan run state transitions | Direct status field mutation | `MarketScanRunRepository` state machine methods | Phase 25 already validates state transitions |

**Key insight:** The scanner is primarily an orchestrator, not a calculator. It delegates to existing services (`valuation_service`, `risk_service`, `yield_service`, `alpha_service`) for all financial computations. The only new computation is the valuation percentile (IDX-04) and quality review gate (SCR-03).

## Common Pitfalls

### Pitfall 1: AKShare Bulk API Field Names Differ From Single-Stock APIs
**What goes wrong:** The bulk `stock_zh_a_spot_em()` returns columns with Chinese names (`市盈率-动态`, `市净率`, `总市值`, `换手率`), while single-stock APIs use English field names. Code that assumes English keys crashes silently, returning `NaN` or default values for PE/PB/market cap, causing all stocks to fail the coarse screen.
**Why it happens:** AKShare does not standardize column names across its functions. Each data source (East Money, Sina, etc.) returns whatever column names the upstream provides.
**How to avoid:** Map Chinese column names explicitly in `batch_data_fetcher.py`. Create a field mapping dict at module level. Test with real AKShare output or a saved fixture.
**Warning signs:** All stocks showing `pe_ttm=None` or `market_cap=0` in ScreeningSnapshot; zero stocks passing coarse screen.

### Pitfall 2: Dividend Yield Not Available in Bulk Spot API
**What goes wrong:** `stock_zh_a_spot_em()` does NOT include dividend yield in its output columns. The ScreeningSnapshot model requires `dividend_yield`. If the batch fetcher leaves it as 0.0, the coarse screener's dividend prioritization signal is zero for all stocks, removing a useful ranking dimension.
**Why it happens:** East Money's real-time quote endpoint does not compute trailing dividend yield. This requires a separate calculation from dividend history data.
**How to avoid:** After the bulk spot fetch, do a secondary fetch for dividend yields. For MVP, only fetch dividend yield for stocks that survive the coarse screen (top-N), and use 0.0 as default in the snapshot for the initial screen.
**Warning signs:** All candidates showing `dividend_yield=0.0`; composite scores never benefit from the yield_gap dimension.

### Pitfall 3: Percentile Calculation with Insufficient Historical Data
**What goes wrong:** Newly listed stocks (IPO within 1-2 years) have fewer than 5 years of PE/PB history. Computing percentile on 50 data points gives noisy, unreliable results.
**Why it happens:** The codebase uses CSI 300/500 which occasionally adds newly listed stocks or recent IPOs.
**How to avoid:** Set a minimum data threshold (e.g., 60 trading days). If fewer historical values, return `None` for percentile. The composite scorer already handles `None` by defaulting to 50.0 (neutral).
**Warning signs:** Stocks with recent IPO dates showing extreme percentile values (0th or 100th); percentile values changing dramatically between scans.

### Pitfall 4: DCF Analysis Fails Silently for Financial Sector Stocks
**What goes wrong:** Banks and insurance companies (about 60 of CSI 300) have fundamentally different cash flow structures. `analyze_dcf_valuation` may produce `NaN` intrinsic values because FCF inputs are meaningless for financials.
**Why it happens:** The DCF model assumes operating cash flow is meaningful, but for banks, "operating cash flow" is fundamentally different.
**How to avoid:** Log financial sector failures as a known category in error_summary rather than treating them as unexpected errors. For MVP, let the per-stock failure isolation handle them gracefully.
**Warning signs:** Error summary showing 50+ "analysis failed" entries for bank tickers (600000.SH, 601398.SH, etc.).

### Pitfall 5: OCF Positive Years Not Available from Bulk API
**What goes wrong:** The coarse screen requires `ocf_positive_years` but `stock_zh_a_spot_em()` does not provide operating cash flow data. If the fetcher leaves it as 0, the coarse screen excludes ALL stocks (since config requires `min_ocf_positive_years=2`).
**Why it happens:** Cash flow data is in financial statements, not real-time market data.
**How to avoid:** Use a two-phase approach: (1) set `ocf_positive_years` to 0 initially (disabling the OCF check in coarse screen), (2) fetch financial data for stocks that pass all other coarse screen rules, (3) re-evaluate OCF check for those stocks. Alternatively, cache OCF data from previous scans.
**Warning signs:** Zero stocks passing coarse screen due to OCF check; or all stocks excluded by "Persistently negative operating cash flow" reason.

### Pitfall 6: 52-Week High Not in Bulk Spot Data
**What goes wrong:** ScreeningSnapshot requires `price_vs_52w_high` but `stock_zh_a_spot_em()` returns current price data, not 52-week range.
**Why it happens:** The bulk spot API does not include historical high/low data.
**How to avoid:** For MVP, default `price_vs_52w_high=1.0` (neutral, no drawdown signal). The drawdown signal in the coarse screener will be zero for all stocks, but other signals (PE, PB, dividend) still provide ranking. This can be enhanced with historical data in a later iteration.
**Warning signs:** All stocks showing identical `price_vs_52w_high=1.0`; drawdown signal always zero.

## Code Examples

Verified patterns from existing codebase:

### Existing Scan Run Lifecycle (from market_scan_repo.py)
```python
# Source: stockvaluefinder/repositories/market_scan_repo.py lines 45-78
async def create_run(self, data: MarketScanRunCreate) -> MarketScanRunDB:
    db_obj = MarketScanRunDB(
        run_id=data.run_id,
        index_codes=list(data.index_codes),
        scan_type=data.scan_type.value if hasattr(data.scan_type, "value") else data.scan_type,
        status="pending",
        rules_version=data.rules_version,
        total_count=data.total_count,
        screened_count=data.screened_count,
        candidate_count=data.candidate_count,
        error_summary=data.error_summary,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    self._session.add(db_obj)
    await self._session.flush()
    await self._session.refresh(db_obj)
    return db_obj
```

### Existing Coarse Screen Consumption (from coarse_screener.py)
```python
# Source: stockvaluefinder/market_scanner/coarse_screener.py lines 131-162
def screen_stocks(
    snapshots: list[ScreeningSnapshot],
    config: MarketScannerConfig,
) -> list[ScreeningResult]:
    return [screen_stock(snapshot, config) for snapshot in snapshots]

def rank_screened_stocks(
    results: list[ScreeningResult],
    top_n: int,
) -> list[ScreeningResult]:
    passed = [r for r in results if r.passed]
    sorted_results = sorted(passed, key=lambda r: r.rank_score, reverse=True)
    return sorted_results[:top_n]
```

### Existing Candidate Persistence (from market_scan_repo.py)
```python
# Source: stockvaluefinder/repositories/market_scan_repo.py lines 350-376
async def create(self, data: MarketScanCandidateCreate) -> MarketScanCandidateDB:
    db_obj = MarketScanCandidateDB(
        candidate_id=data.candidate_id,
        run_id=data.run_id,
        ticker=data.ticker,
        index_code=data.index_code,
        passed=data.passed,
        composite_score=data.composite_score,
        screening_snapshot=data.screening_snapshot,
    )
    self._session.add(db_obj)
    await self._session.flush()
    await self._session.refresh(db_obj)
    return db_obj
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-stock price fetch (800 calls) | Bulk `stock_zh_a_spot_em()` (1 call) | Phase 27 design | 800x reduction in API calls for market data |
| All analysis synchronous | `asyncio.Semaphore` + concurrent deep analysis | Phase 27 design | Configurable concurrency, bounded parallelism |
| Single-stock failure kills scan | Per-stock try/except + partial_failed state | Phase 27 design | Scan survives individual data failures |
| No valuation history context | 5-year PE/PB percentile ranking (IDX-04) | Phase 27 design | Relative valuation context for each stock |

**Deprecated/outdated:**
- Sequential per-stock API calls for batch market data (replaced by bulk AKShare API)
- Assuming all DCF inputs are available for every stock (financial sector requires PB-based alternative)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | AKShare `stock_zh_a_spot_em()` returns columns including `市盈率-动态` (PE TTM), `市净率` (PB), `总市值` (market cap), `换手率` (turnover), and these are reliable for A-share stocks | Batch Data Fetcher | If column names differ or data is sparse, snapshot mapping breaks |
| A2 | `stock_zh_a_spot_em()` does NOT include dividend yield; a secondary fetch strategy is needed | Batch Data Fetcher | If it does include yield, the secondary fetch is unnecessary overhead |
| A3 | For MVP, `price_vs_52w_high` can default to 1.0 (neutral) and `ocf_positive_years` can be deferred to the deep analysis phase | Batch Data Fetcher | If these fields are critical for coarse screen accuracy, the MVP produces lower-quality rankings |
| A4 | The existing `ExternalDataService.get_financial_report()` can be reused for per-stock deep analysis without modification | Scan Orchestrator | If it lacks needed fields (e.g., beta, market_risk_premium), the orchestrator needs additional data sources |
| A5 | Quality review (SCR-03) should use existing `RiskScore` output plus ROIC-WACC spread from the alpha module; no new data fetch is needed | Quality Review | If ROIC-WACC data is not readily available for daily scans, the check degrades gracefully |
| A6 | `scipy.stats.percentileofscore` is the correct function for IDX-04 percentile calculation | Valuation Percentile | If the percentile semantics differ from "where current value sits relative to N-year history", the ranking is wrong |

## Open Questions

1. **ST status and suspension detection from bulk API**
   - What we know: `stock_zh_a_spot_em()` returns stock name which may contain "ST" prefix for ST stocks. It does not have explicit ST/suspension flags.
   - What's unclear: Whether the name field reliably contains "ST" for all ST variants (ST, *ST, SST). Also unclear how to detect suspension from bulk data.
   - Recommendation: Detect ST by checking if stock name contains "ST" (case-insensitive). Detect suspension by checking if turnover and volume are both zero.

2. **Where to get historical PE/PB for percentile calculation (IDX-04)**
   - What we know: `stock_zh_a_hist()` returns daily OHLCV data but not PE/PB. PE/PB would need to be computed from price and financial data.
   - What's unclear: Whether AKShare has a bulk PE/PB history API.
   - Recommendation: For MVP, compute PE percentile using current PE from spot data and historical PE from cached daily records. If no historical data is available, return None (composite scorer defaults to 50.0).

3. **DCF parameter selection for batch mode**
   - What we know: `analyze_dcf_valuation` requires `DCFParams` with growth rates, beta, risk-free rate, etc.
   - What's unclear: Whether to use a single default `DCFParams` for all stocks or attempt to derive per-stock parameters.
   - Recommendation: Use default `DCFParams` with risk-free rate from `RateClient.get_10y_treasury_yield()` and industry-average beta. Document as a known limitation.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All code | Yes | 3.12.11 | -- |
| PostgreSQL | Repositories (scan run/candidate persistence) | Not verified | -- | Tests use AsyncMock |
| Redis | CacheManager (price caching) | Not verified | -- | Tests mock cache |
| scipy | Valuation percentile (IDX-04) | Yes (pyproject.toml) | 1.16.0 | -- |
| AKShare | Batch market data fetch | Not installed in venv | >=1.14.0 (pyproject.toml) | Tests mock AKShare |
| pytest | Testing | Yes | 9.0+ | -- |
| mypy | Type checking | Yes | 1.19+ | -- |
| ruff | Linting/formatting | Yes | 0.15+ | -- |

**Missing dependencies with no fallback:**
- None (AKShare not installed in venv but is a declared dependency; tests mock external calls)

**Missing dependencies with fallback:**
- AKShare: Tests use mocks; runtime requires `uv sync` to install

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | stockvaluefinder/pytest.ini |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py tests/unit/test_market_scanner/test_quality_review.py tests/unit/test_market_scanner/test_scan_orchestrator.py -q --no-cov` |
| Full suite command | `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| IDX-03 | Fetch batch market snapshots for all constituents | unit | `uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py::test_fetch_market_snapshots -q --no-cov` | No, Wave 0 |
| IDX-03 | Rate-limited API calls with caching | unit | `uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py::test_rate_limiting -q --no-cov` | No, Wave 0 |
| IDX-03 | Map AKShare Chinese columns to ScreeningSnapshot | unit | `uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py::test_column_mapping -q --no-cov` | No, Wave 0 |
| IDX-03 | ST/suspension detection from name and turnover data | unit | `uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py::test_st_detection -q --no-cov` | No, Wave 0 |
| IDX-04 | Calculate PE percentile rank within index peers | unit | `uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py::test_pe_percentile -q --no-cov` | No, Wave 0 |
| IDX-04 | Handle insufficient historical data gracefully | unit | `uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py::test_insufficient_history -q --no-cov` | No, Wave 0 |
| SCR-02 | Run DCF on top-N stocks from coarse screen | unit | `uv run pytest tests/unit/test_market_scanner/test_scan_orchestrator.py::test_dcf_on_top_n -q --no-cov` | No, Wave 0 |
| SCR-02 | Flag stocks with safety margin >= 30% (configurable) | unit | `uv run pytest tests/unit/test_market_scanner/test_scan_orchestrator.py::test_safety_margin_threshold -q --no-cov` | No, Wave 0 |
| SCR-03 | Check ROIC-WACC spread is positive | unit | `uv run pytest tests/unit/test_market_scanner/test_quality_review.py::test_roic_wacc_spread -q --no-cov` | No, Wave 0 |
| SCR-03 | Check M-Score below manipulation threshold | unit | `uv run pytest tests/unit/test_market_scanner/test_quality_review.py::test_mscore_threshold -q --no-cov` | No, Wave 0 |
| SCR-03 | Check cash flow divergence not detected | unit | `uv run pytest tests/unit/test_market_scanner/test_quality_review.py::test_cash_flow_divergence -q --no-cov` | No, Wave 0 |
| SCR-03 | Only passing stocks enter candidate list | unit | `uv run pytest tests/unit/test_market_scanner/test_quality_review.py::test_only_passing_enter_candidates -q --no-cov` | No, Wave 0 |
| EXE-04 | Single-stock failure does not abort scan | unit | `uv run pytest tests/unit/test_market_scanner/test_scan_orchestrator.py::test_failure_isolation -q --no-cov` | No, Wave 0 |

### Sampling Rate
- **Per task commit:** `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/test_batch_data_fetcher.py -q --no-cov` (or relevant test file)
- **Per wave merge:** `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/ -v`
- **Phase gate:** Full market scanner test suite green before phase complete

### Wave 0 Gaps
- [ ] `tests/unit/test_market_scanner/test_batch_data_fetcher.py` -- covers IDX-03 + IDX-04
- [ ] `tests/unit/test_market_scanner/test_quality_review.py` -- covers SCR-03
- [ ] `tests/unit/test_market_scanner/test_scan_orchestrator.py` -- covers SCR-02 + pipeline integration

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 27 is backend service orchestration, no user-facing auth |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | No API endpoints in this phase (Phase 28 adds endpoints) |
| V5 Input Validation | Yes | Pydantic model validation on ScreeningSnapshot, ScreeningResult, CompositeScore |
| V6 Cryptography | No | No crypto operations |

### Known Threat Patterns for Scan Orchestration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed external API data | Tampering | Pydantic validation on all ScreeningSnapshot fields; _safe_float() helper for NaN/inf |
| Rate limit exhaustion (DoS via scan) | Denial of Service | asyncio.Semaphore for concurrency; config.request_delay_seconds for rate limiting |
| Error message leaking internal infrastructure | Information Disclosure | Structured error_summary records ticker + error category, not full stack traces or API URLs |
| Batch scan consuming all DB connections | Denial of Service | Connection pool limits (pool_size=5, max_overflow=10); batch inserts with flush, not per-stock commit |

## Sources

### Primary (HIGH confidence)
- Codebase: `stockvaluefinder/market_scanner/config.py` -- MarketScannerConfig with all thresholds
- Codebase: `stockvaluefinder/market_scanner/coarse_screener.py` -- screen_stocks() and rank_screened_stocks()
- Codebase: `stockvaluefinder/market_scanner/composite_scorer.py` -- calculate_composite_score()
- Codebase: `stockvaluefinder/market_scanner/reason_generator.py` -- generate_reasons()
- Codebase: `stockvaluefinder/market_scanner/models.py` -- ScreeningSnapshot, ScreeningResult, CompositeScore, CandidateReasons
- Codebase: `stockvaluefinder/external/data_service.py` -- ExternalDataService API methods, caching, fallback chain
- Codebase: `stockvaluefinder/external/akshare_client.py` -- AKShareClient with rate limiting, _run_sync pattern
- Codebase: `stockvaluefinder/external/efinance_client.py` -- EFinanceClient with get_realtime_quotes()
- Codebase: `stockvaluefinder/services/valuation_service.py` -- analyze_dcf_valuation() and DCFValuationService
- Codebase: `stockvaluefinder/services/risk_service.py` -- analyze_financial_risk() and RiskAnalyzer
- Codebase: `stockvaluefinder/services/yield_service.py` -- analyze_yield_gap() and YieldAnalyzer
- Codebase: `stockvaluefinder/repositories/market_scan_repo.py` -- ScanRun + Candidate repository with state machine
- Codebase: `.planning/REQUIREMENTS.md` -- IDX-03, IDX-04, SCR-02, SCR-03 definitions
- Codebase: `.planning/research/PITFALLS.md` -- verified pitfalls for v1.5

### Secondary (MEDIUM confidence)
- Web search: AKShare `stock_zh_a_spot_em()` documentation -- confirmed returns PE, PB, market cap, turnover in Chinese column names
- Codebase: `stockvaluefinder/models/market_scanner.py` -- MarketScanCandidateCreate model with screening_snapshot JSONB
- Codebase: `stockvaluefinder/external/rate_client.py` -- RateClient for risk-free rate fetching
- Phase summaries: 25-01-SUMMARY.md, 25-02-SUMMARY.md, 26-01-SUMMARY.md, 26-02-SUMMARY.md, 26-03-SUMMARY.md

### Tertiary (LOW confidence)
- A2: `stock_zh_a_spot_em()` does not include dividend yield -- based on training knowledge, not verified with live call [ASSUMED]
- A3: For MVP, price_vs_52w_high and ocf_positive_years can use defaults -- design assumption [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing codebase patterns
- Architecture: HIGH -- follows existing service orchestration pattern with clear module separation
- Pitfalls: HIGH -- PITFALLS.md provides verified domain-specific warnings
- Batch API integration: MEDIUM -- field names verified via web search but not tested with live AKShare call

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable domain, AKShare API surface may change slowly)
