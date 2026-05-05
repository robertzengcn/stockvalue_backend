# Phase 10: Capital Allocation Scorecard - Research

**Researched:** 2026-05-05
**Domain:** Capital allocation analysis (buyback yield, dividend stability, expansion discipline, combined scorecard)
**Confidence:** HIGH

## Summary

Phase 10 implements a three-dimension capital allocation scorecard that evaluates how well management deploys shareholder capital. The three dimensions are: (1) buyback yield via AKShare's `stock_repurchase_em()` full-dataset fetch with Redis caching, (2) 5-year dividend per unit stability trend using existing `DividendDataDB` with scipy `linregress` (reusing Phase 9's moat trend pattern), and (3) blind expansion alerts combining Phase 9's ROIC-WACC spread with CapEx growth from existing cash flow data. The combined scorecard produces an A/B/C/D letter grade with equal weighting (33/33/33) across the three dimensions.

**Primary recommendation:** Follow the exact patterns established in Phase 9 (roic_service, roic_routes, roic_repo) for consistency. All new code fits cleanly into the existing layered architecture: extend `akshare_client.py` with a buyback fetch method, add `capex_service.py` as pure functions, create a new `capex_routes.py` endpoint, and add one Alembic migration for the scorecard persistence table.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** AKShare `stock_repurchase_em()` returns ALL ~5088 A-share stocks. Fetch full dataset, cache in Redis with 24h TTL, filter for requested ticker on read. Consistent with existing caching pattern.
- **D-02:** Buyback yield uses annual repurchase amount from the most recent full fiscal year. Formula: `buyback_yield = annual_repurchase_amount / market_cap`. Aligned with annual report cycle, consistent with other per-year metrics.
- **D-03:** Use existing DividendDataDB (dividend_per_share + fiscal_year) for 5-year DPU trend. Fall back to AKShare fresh fetch if DB has no data for the ticker. Leverages existing dividend infrastructure.
- **D-04:** DPU trend classification via scipy `linregress` on 5-year data -- consistent with Phase 9 moat detection pattern. Slope > threshold = "growth", slope < -threshold = "decline", between = "stable". Reuse `analyze_roic_trend` pattern from roic_service.
- **D-05:** Blind expansion alert triggers when ROIC < WACC AND YoY CapEx growth > 20%. The 20% threshold is a common academic benchmark for aggressive expansion. Requires 2 years of CapEx data.
- **D-06:** CapEx data from existing AKShare financial data -- the field `CONSTRUCT_LONG_ASSET` / `购建固定资产、无形资产和其他长期资产支付的现金` is already extracted by `get_financial_report()`. Extend multi-year fetch to include CapEx.
- **D-07:** Combined scorecard uses letter grades A/B/C/D. Each dimension independently rated, then averaged with equal weights (1/3 each): buyback yield, dividend stability, expansion discipline. A = strong capital allocation, D = poor.
- **D-08:** Equal weighting (33/33/33) for the three dimensions. Simple, transparent, no bias toward any single capital allocation signal.

### Claude's Discretion
- Exact thresholds for A/B/C/D grade boundaries per dimension
- API endpoint path and request/response model structure
- New ORM model field names and Alembic migration details
- Internal helper function organization within capex_service.py
- Test file structure and test case selection

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAPEX-01 | User can view buyback yield (repurchase amount / market cap) from AKShare stock_repurchase_em() | `stock_repurchase_em()` verified live: returns 5088 rows, columns include `股票代码`, `已回购金额`, `已回购股份数量`. Cache full dataset with 24h TTL, filter by ticker. |
| CAPEX-02 | User can view 5-year dividend per unit stability trend with growth/decline/stable classification | Existing `DividendDataDB` has `dividend_per_share` + `fiscal_year`. scipy `linregress` pattern from `analyze_roic_trend()` in roic_service.py. |
| CAPEX-03 | System alerts on blind expansion (ROIC < WACC AND CapEx growth exceeding threshold) | Phase 9 ROIC results persisted in `roic_results` table. CapEx from `CONSTRUCT_LONG_ASSET` in cash flow sheet, already extracted. |
| CAPEX-04 | User can view capital allocation scorecard combining buyback yield, dividend stability, and expansion discipline | Three dimensions independently rated A/B/C/D, averaged with equal weights. New `capex_routes.py` endpoint with `ApiResponse[T]` envelope. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Buyback data fetching + caching | API / Backend | External service | Full-dataset fetch from AKShare, Redis cache, in-memory filter |
| Dividend trend data retrieval | API / Backend | Database | DB-first from DividendDataDB, fallback to AKShare fresh fetch |
| CapEx data extraction | API / Backend | External service | Extends existing multi-year financial fetch with CapEx field |
| All calculation logic (yield, trend, expansion, scorecard) | API / Backend | -- | Pure functions in capex_service.py, no I/O |
| ROIC-WACC dependency | API / Backend | Database | Reads Phase 9 roic_results for blind expansion check |
| Scorecard persistence | Database | API / Backend | New ORM model + Alembic migration, upsert by (ticker, fiscal_year) |
| API endpoint | API / Backend | -- | New capex_routes.py following roic_routes pattern |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scipy | 1.17.1 (installed) | `linregress` for 5-year DPU trend slope | Already installed and used in Phase 9 `analyze_roic_trend()`. Provides slope + p-value for trend significance. |
| AKShare | 1.18.46 (installed) | `stock_repurchase_em()` for buyback data | Only free data source for A-share buyback data. Returns 5088 stocks with actual repurchase amounts. |
| FastAPI | >=0.133.1 (installed) | API routing | Project standard. New `capex_routes.py` follows existing route pattern. |
| SQLAlchemy 2.0 | >=2.0.47 (installed) | ORM for scorecard persistence | Project standard. New `CapitalAllocationScoreDB` model. |
| Pydantic 2.x | >=2.12.5 (installed) | Request/response validation | Project standard. Frozen models for results. |
| Alembic | >=1.18.4 (installed) | Database migration | Project standard. Migration 012 for capital_allocation_scores table. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| redis | >=7.2.1 (installed) | Caching buyback full dataset | 24h TTL for `stock_repurchase_em()` results |
| pytest | >=9.0 (installed) | Unit and integration testing | All new functions require 80%+ coverage |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AKShare `stock_repurchase_em()` | Tushare `repurchase` API | Tushare requires paid token. AKShare is free and returns same East Money data. |
| AKShare `stock_repurchase_em()` | Balance sheet `TREASURY_SHARES` | `TREASURY_SHARES` is cumulative stock, not annual flow. Cannot compute annual buyback yield. |
| scipy `linregress` | numpy `polyfit` | linregress provides p-value for significance. Phase 9 already uses this pattern. |

**Installation:**
No new packages required. All dependencies already installed:
- scipy 1.17.1 [VERIFIED: `import scipy; scipy.__version__`]
- akshare 1.18.46 [VERIFIED: `import akshare; akshare.__version__`]

## Architecture Patterns

### System Architecture Diagram

```
Request: POST /api/v1/analyze/capex
    |
    v
capex_routes.py (orchestrator)
    |
    +---> ExternalDataService.get_buyback_data()
    |         |
    |         +---> AKShareClient.get_repurchase_data()  [NEW]
    |         |         |
    |         |         +---> stock_repurchase_em()  [5088 rows, cached 24h]
    |         |         +---> filter by ticker
    |         |
    |         +---> ExternalDataService.get_current_price()  [EXISTING]
    |         +---> ExternalDataService.get_shares_outstanding()  [EXISTING]
    |
    +---> capex_service.calculate_buyback_yield()  [NEW pure fn]
    |
    +---> DividendRepository.get_by_ticker()  [EXISTING]
    |     OR AKShareClient.get_dividend_history()  [EXISTING fallback]
    |         |
    |         +---> 5 years of dividend_per_share data
    |
    +---> capex_service.classify_dividend_stability()  [NEW pure fn]
    |         |
    |         +---> scipy.stats.linregress  [reuse Phase 9 pattern]
    |
    +---> ROICResultRepository.get_latest_for_ticker()  [EXISTING]
    |         |
    |         +---> roic, wacc, spread from Phase 9
    |
    +---> ExternalDataService.get_multi_year_capex()  [NEW, extends existing]
    |         |
    |         +---> Cash flow sheet CONSTRUCT_LONG_ASSET for 2 years
    |
    +---> capex_service.detect_blind_expansion()  [NEW pure fn]
    |
    +---> capex_service.calculate_capital_allocation_score()  [NEW pure fn]
    |         |
    |         +---> Equal-weight average of 3 dimension grades
    |
    +---> CapitalAllocationRepo.upsert_by_ticker_year()  [NEW]
    |
    v
ApiResponse[CapitalAllocationResult]
```

### Recommended Project Structure
```
stockvaluefinder/
├── stockvaluefinder/
│   ├── services/
│   │   └── capex_service.py          # NEW - pure functions for all 3 dimensions + scorecard
│   ├── models/
│   │   └── capital_allocation.py     # NEW - Pydantic request/response/domain models
│   ├── db/models/
│   │   └── capital_allocation.py     # NEW - SQLAlchemy ORM model
│   ├── repositories/
│   │   └── capital_allocation_repo.py # NEW - data access with upsert pattern
│   ├── api/
│   │   └── capex_routes.py           # NEW - API endpoint
│   ├── external/
│   │   ├── akshare_client.py         # EXTEND - add get_repurchase_data()
│   │   └── data_service.py           # EXTEND - add get_buyback_data(), get_multi_year_capex()
│   └── config.py                     # EXTEND - add CapitalAllocationConfig
├── alembic/versions/
│   └── 012_capital_allocation_scores_table.py  # NEW
└── tests/
    └── unit/
        ├── test_services/
        │   └── test_capex_service.py  # NEW - pure function unit tests
        ├── test_models/
        │   └── test_capital_allocation_models.py  # NEW
        └── test_external/
            └── test_data_service_capex.py  # NEW - data service extension tests
```

### Pattern 1: Buyback Data Fetch with Full-Dataset Cache (D-01)
**What:** AKShare `stock_repurchase_em()` returns all 5088 A-share stocks with no per-stock option. Cache the full result, filter in memory.
**When to use:** Every buyback yield calculation.
**Example:**
```python
# In akshare_client.py - new method
async def get_repurchase_data(self) -> list[dict[str, Any]]:
    """Fetch full A-share buyback dataset from East Money.

    Returns ALL ~5088 stocks. Caller filters by stock code.
    Cache at data_service level with 24h TTL.
    """
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak
        df = ak.stock_repurchase_em()
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)

# In data_service.py - new method wrapping with cache
async def get_buyback_data(self, ticker: str) -> dict[str, Any]:
    """Get buyback data for a specific ticker.

    Fetches full dataset, caches 24h, filters for requested ticker.
    Cache key: v1:buyback_full_dataset
    """
    # Cache key does NOT include ticker -- single cache for all tickers
    full_dataset = await self._cache_get_or_set(
        key_parts=("buyback_full_dataset",),
        ttl=86400,
        fetch_fn=lambda: self._akshare.get_repurchase_data(),
    )
    # Filter for requested ticker (6-digit code)
    symbol = ticker.split(".")[0] if "." in ticker else ticker
    matching = [r for r in full_dataset if r.get("股票代码") == symbol]
    ...
```
Source: [VERIFIED: live AKShare `stock_repurchase_em()` returns 5088 rows with columns `股票代码`, `已回购金额`, `已回购股份数量`, `实施进度`]

### Pattern 2: DPU Trend with scipy linregress (D-04)
**What:** 5-year dividend per unit trend classification using linear regression, reusing Phase 9's `analyze_roic_trend()` pattern.
**When to use:** Dividend stability dimension of the scorecard.
**Example:**
```python
def classify_dividend_stability(
    dpu_values: list[float],
    years: list[int],
    growth_threshold: float = 0.05,
    decline_threshold: float = -0.05,
) -> dict[str, Any]:
    """Classify 5-year DPU trend using scipy linregress.

    Reuse analyze_roic_trend pattern from roic_service.py.
    Returns: {classification: DividendTrend, slope, p_value, data_points}
    """
    from scipy.stats import linregress
    # ... same structure as analyze_roic_trend ...
```
Source: [CITED: `roic_service.py:223-285` `analyze_roic_trend()` function]

### Pattern 3: Blind Expansion Detection (D-05)
**What:** Alert when ROIC < WACC AND YoY CapEx growth > 20%.
**When to use:** Expansion discipline dimension of the scorecard.
**Example:**
```python
def detect_blind_expansion(
    roic: float | None,
    wacc: float,
    capex_current: float | None,
    capex_previous: float | None,
    capex_growth_threshold: float = 0.20,
) -> dict[str, Any]:
    """Detect blind expansion: value destruction + aggressive capex.

    Alert triggers when:
    1. ROIC < WACC (value destroying per Phase 9)
    2. YoY CapEx growth > 20%

    Returns: {alert: bool, roic_wacc_spread, capex_yoy_growth, details}
    """
    if roic is None or capex_current is None or capex_previous is None:
        return {"alert": False, "reason": "insufficient_data", ...}

    spread = roic - wacc
    capex_growth = (capex_current - capex_previous) / abs(capex_previous)

    alert = (spread < 0) and (capex_growth > capex_growth_threshold)
    return {"alert": alert, "roic_wacc_spread": spread, "capex_yoy_growth": capex_growth, ...}
```
Source: [CITED: `roic_service.py:188-220` `calculate_roic_wacc_spread()` pattern]

### Anti-Patterns to Avoid
- **Fetching `stock_repurchase_em()` per stock request:** Returns 5088 rows every time. Fetch once, cache full dataset, filter in memory. [VERIFIED: `stock_repurchase_em()` takes no arguments]
- **Using `TREASURY_SHARES` from balance sheet as annual buyback:** This is a cumulative balance, not annual flow. Only use `已回购金额` from `stock_repurchase_em()`. [CITED: PITFALLS.md Pitfall 6]
- **Using planned repurchase amount (`拟回购金额`) instead of actual (`已回购金额`):** Many companies announce but don't execute. Only use actual execution data. [CITED: PITFALLS.md]
- **Computing CapEx YoY growth without handling sign:** CapEx from cash flow statement is a negative number (cash outflow). Use `abs()` before computing growth ratio. [CITED: PITFALLS.md integration gotchas]
- **Omitting buyback dimension when data unavailable:** If buyback data missing for a stock, reweight remaining 2 dimensions to 50/50 instead of treating missing dimension as grade D. [CITED: PITFALLS.md recovery strategies]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Linear regression for DPU trend | Manual slope/p-value calculation | scipy.stats.linregress | Phase 9 already uses this. Provides slope + p-value with battle-tested numerics. |
| Buyback data fetching | Web scraping East Money | AKShare `stock_repurchase_em()` | Free, structured, maintained. Scraping violates rate limits. |
| Multi-year financial data | Separate API calls per year | `AKShareClient.fetch_multi_year_financials()` | Already exists, fetches all periods in one call, filters in-memory. |
| API response envelope | Custom response format | `ApiResponse[T]` from `models/api.py` | Project standard. Generic with success/data/error. |
| DB persistence pattern | Custom CRUD logic | `BaseRepository` + `upsert_by_ticker_year()` | Follows Phase 9 `ROICResultRepository` pattern. |
| Cache management | Manual cache logic | `CacheManager._cache_get_or_set()` | Handles TTL, serialization, cache miss, graceful degradation. |

**Key insight:** This phase is 80% reuse of existing patterns. The only genuinely new data source is `stock_repurchase_em()`.

## Common Pitfalls

### Pitfall 1: Buyback Data Fragmentation (CAPEX-01)
**What goes wrong:** `stock_repurchase_em()` returns 5088 rows but a single stock may have multiple rows (different buyback programs/announcements). Maotai has 2 rows: one "completed" and one "in progress". Summing all rows for a ticker produces inflated buyback yield.
**Why it happens:** The API returns one row per buyback program, not per stock. A company can have multiple concurrent buyback programs.
**How to avoid:** Filter by ticker, then select the most recent COMPLETED program (`实施进度 == '完成实施'`). If no completed program, use the most recent "in progress" (`实施进度 == '实施中'`) but flag as `data_quality: "INCOMPLETE"`. Do NOT sum all programs.
**Warning signs:** Buyback yield > 10% for any stock (unrealistic for A-shares).
Source: [VERIFIED: live data shows Maotai has 2 rows with different `实施进度` values]

### Pitfall 2: DividendDataDB Missing Fiscal Year Data (CAPEX-02)
**What goes wrong:** `DividendDataDB` may have incomplete fiscal year coverage for a stock. If only 3 of 5 needed years exist, linregress runs on insufficient data and produces unreliable trend classification.
**Why it happens:** Dividend data is populated by the yield gap analysis pipeline. Stocks not yet analyzed via yield routes may have no dividend data in DB at all.
**How to avoid:** Check DB data first. If fewer than 5 years, fall back to AKShare `get_dividend_history()`. If still insufficient (< 3 years), return `classification: INSUFFICIENT_DATA` with neutral score.
**Warning signs:** All stocks show `INSUFFICIENT_DATA` for dividend stability.

### Pitfall 3: CapEx NaN/Zero from Cash Flow Sheet (CAPEX-03)
**What goes wrong:** AKShare returns NaN for `CONSTRUCT_LONG_ASSET` when the field is blank in the cash flow statement. Dividing by NaN or zero CapEx in the previous year produces NaN growth rate.
**Why it happens:** Some companies (especially financials) have different cash flow statement formats. AKShare's mapping is imperfect for all edge cases.
**How to avoid:** Use `_to_float()` helper from `risk_service.py` which normalizes NaN to 0.0. If previous year CapEx is 0, skip blind expansion check and return `alert: false, reason: "no_prior_capex"`.
**Warning signs:** CapEx growth shows `inf` or `nan` for any stock.

### Pitfall 4: ROIC Result Not Yet Computed (CAPEX-03)
**What goes wrong:** Blind expansion check requires Phase 9 ROIC results. If Phase 9 analysis hasn't been run for the requested stock, `get_latest_for_ticker()` returns None.
**Why it happens:** ROIC analysis is on-demand, not pre-computed. The capital allocation scorecard may be the first analysis requested for a stock.
**How to avoid:** When ROIC result is None for blind expansion, return `expansion_discipline: INSUFFICIENT_DATA` with neutral score. Do NOT trigger blind expansion alert. Include a hint in the response suggesting the user run ROIC analysis first.
**Warning signs:** All stocks show `INSUFFICIENT_DATA` for expansion discipline.

### Pitfall 5: Grade Boundary Ambiguity (CAPEX-04)
**What goes wrong:** Equal-weight averaging of three letter grades produces ambiguous results. E.g., grade A (buyback) + grade D (dividend) + grade C (expansion) = average numeric 2.0 which maps to C or B?
**Why it happens:** Letter grades are ordinal, not interval. Mapping A=4, B=3, C=2, D=1 and averaging treats the difference between A and B as equal to the difference between C and D, which may not be appropriate.
**How to avoid:** Use a consistent numeric mapping (A=4, B=3, C=2, D=1), compute average, then map back with clear boundaries: >= 3.5 = A, >= 2.5 = B, >= 1.5 = C, < 1.5 = D. Document the boundaries in `CapitalAllocationConfig`.
**Warning signs:** Scorecard grade flips between B and C with minor data changes.

## Code Examples

Verified patterns from existing codebase:

### Buyback Data Structure (verified live)
```python
# stock_repurchase_em() returns DataFrame with these columns:
# ['序号', '股票代码', '股票简称', '最新价',
#  '计划回购价格区间', '计划回购数量区间-下限', '计划回购数量区间-上限',
#  '占公告前一日总股本比例-下限', '占公告前一日总股本比例-上限',
#  '计划回购金额区间-下限', '计划回购金额区间-上限',
#  '回购起始时间', '实施进度',
#  '已回购股份价格区间-下限', '已回购股份价格区间-上限',
#  '已回购股份数量', '已回购金额', '最新公告日期']

# Key fields for buyback yield:
# - 股票代码: 6-digit stock code (e.g., '600519')
# - 已回购金额: actual repurchase amount in CNY
# - 已回购股份数量: actual shares repurchased
# - 实施进度: '完成实施' (completed) or '实施中' (in progress)
# - 最新公告日期: latest announcement date

# Coverage: 4907 / 5088 stocks have non-null 已回购金额
```
Source: [VERIFIED: live `ak.stock_repurchase_em()` call, 2026-05-05]

### Reusing Phase 9 Trend Pattern
```python
# Source: stockvaluefinder/services/roic_service.py:223-285
# This exact pattern should be adapted for DPU trend:

def classify_dividend_stability(
    dpu_values: list[float],
    years: list[int],
    growth_threshold: float = 0.05,
    decline_threshold: float = -0.05,
) -> dict[str, Any]:
    """Classify 5-year DPU trend.

    Adapted from analyze_roic_trend() in roic_service.py.
    """
    valid: list[tuple[int, float]] = []
    for year, dpu in zip(years, dpu_values):
        if dpu is not None and dpu == dpu and dpu > 0:  # NaN + zero check
            valid.append((year, dpu))

    if len(valid) < 3:  # minimum 3 data points
        return {
            "classification": "INSUFFICIENT_DATA",
            "slope": None, "p_value": None, "data_points": len(valid),
        }

    x = list(range(len(valid)))
    y = [d for _, d in valid]

    from scipy.stats import linregress
    result = linregress(x, y)
    slope = result.slope

    if slope > growth_threshold:
        classification = "GROWTH"
    elif slope < decline_threshold:
        classification = "DECLINE"
    else:
        classification = "STABLE"

    return {
        "classification": classification,
        "slope": round(slope, 6),
        "p_value": round(result.pvalue, 6),
        "data_points": len(valid),
    }
```
Source: [CITED: `roic_service.py:223-285`]

### CapEx Field Extraction (existing pattern)
```python
# Source: stockvaluefinder/external/data_service.py:737-746
# CapEx is already extracted in _fetch_free_cash_flow:

for field in [
    "CONSTRUCT_LONG_ASSET",
    "购建固定资产、无形资产和其他长期资产支付的现金",
    "资本支出",
    "capex",
    "capital_expenditure",
]:
    if field in latest and latest[field]:
        capex = float(latest[field])
        break
```
Source: [CITED: `data_service.py:737-746`]

### Route Pattern (from Phase 9 roic_routes.py)
```python
# Source: stockvaluefinder/api/roic_routes.py
# Pattern to follow for capex_routes.py:

router = APIRouter(prefix="/api/v1/analyze/capex", tags=["capex"])

@router.post("/", response_model=ApiResponse[CapitalAllocationResult])
async def analyze_capital_allocation(
    request: CapitalAllocationRequest,
    data_service: ExternalDataService = Depends(get_initialized_data_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[CapitalAllocationResult]:
    try:
        ticker = request.ticker.upper()
        # (a) Fetch buyback data
        # (b) Fetch dividend history
        # (c) Fetch ROIC result from Phase 9
        # (d) Fetch multi-year CapEx data
        # (e) Calculate all dimensions
        # (f) Compute combined scorecard
        # (g) Persist to database
        # (h) Return response
        return ApiResponse(success=True, data=result)
    except DataValidationError as e:
        return ApiResponse(success=False, error=str(e))
    except ExternalAPIError as e:
        return ApiResponse(success=False, error="Failed to fetch data.")
    except Exception:
        return ApiResponse(success=False, error="An internal error occurred.")
```
Source: [CITED: `roic_routes.py:43-271`]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No buyback analysis | `stock_repurchase_em()` full dataset | Phase 10 (new) | New data source, requires caching strategy |
| F-Score only for financial health | Capital allocation scorecard (3 dimensions) | Phase 10 (new) | Broader management quality assessment |
| Phase 9 ROIC-WACC standalone | ROIC-WACC integrated with CapEx for blind expansion | Phase 10 | Cross-phase dependency: Phase 9 results feed Phase 3 |

**Deprecated/outdated:**
- Using `TREASURY_SHARES` from balance sheet as buyback proxy: Cumulative, not annual flow. Never reliable for buyback yield.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Grade boundaries: A >= 3.5, B >= 2.5, C >= 1.5, D < 1.5 on a 4-point scale (A=4, B=3, C=2, D=1) | Scorecard | Grade distribution may be skewed; planner can adjust |
| A2 | DPU trend threshold: slope > 0.05 = growth, slope < -0.05 = decline | Dividend stability | Thresholds may be too aggressive for Chinese dividend patterns; planner can tune |
| A3 | Per-dimension grade thresholds: buyback yield > 2% = A, 1-2% = B, 0.5-1% = C, < 0.5% = D | Buyback yield | A-share buyback yields are typically low; thresholds may need adjustment after data analysis |
| A4 | Expansion discipline: if no blind expansion alert, grade = A; if alert + capex growth 20-50% = C; if alert + capex growth > 50% = D; if insufficient data = B (neutral) | Expansion discipline | The "no alert = A" assumption is generous; some stocks with low capex may not deserve A |

## Open Questions

1. **Should we use the most recent completed buyback or sum all active programs?**
   - What we know: Maotai has 2 rows -- one completed, one in progress. Summing inflates yield.
   - What's unclear: Should we use only completed programs, or include "in progress" with a quality flag?
   - Recommendation: Use the most recent completed program. If no completed program exists, use the most recent "in progress" with `data_quality: "INCOMPLETE"` flag. This matches D-02 (annual repurchase amount).

2. **What happens when Phase 9 ROIC hasn't been computed for a stock?**
   - What we know: ROIC analysis is on-demand. Capital allocation may be requested first.
   - What's unclear: Should we compute ROIC inline as part of capital allocation, or just flag as insufficient?
   - Recommendation: Flag as `INSUFFICIENT_DATA` for expansion discipline dimension. Do not cascade into full ROIC computation -- that would make the capex endpoint depend on all of Phase 9's data fetching, violating separation of concerns. Include a message suggesting the user run ROIC analysis first.

3. **Buyback data has a `最新公告日期` (latest announcement date). Should we filter by date to get annual amounts?**
   - What we know: D-02 specifies "annual repurchase amount from the most recent full fiscal year."
   - What's unclear: The `已回购金额` field may be cumulative for the program, not annual. We may need to look at announcement dates or program start dates to isolate annual amounts.
   - Recommendation: For the MVP, use `已回购金额` from the most recent completed program as a proxy. This may overstate or understate true annual buyback, but it's the best data available from AKShare. Flag in audit trail.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Runtime | Yes | 3.12 | -- |
| PostgreSQL | Scorecard persistence | Yes | 15.x | -- |
| Redis | Buyback data caching | Yes | Docker | Graceful degradation (no cache, slower) |
| scipy | DPU trend linregress | Yes | 1.17.1 | -- |
| AKShare | Buyback + CapEx data | Yes | 1.18.46 | -- |
| pytest | Testing | Yes | 9.x | -- |
| ruff | Linting | Yes | 0.15+ | -- |
| mypy | Type checking | Yes | 1.19+ | -- |

**Missing dependencies with no fallback:**
None -- all required tools are installed.

**Missing dependencies with fallback:**
None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x with pytest-asyncio |
| Config file | pyproject.toml (tool.pytest.ini_options) |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_capex_service.py -x` |
| Full suite command | `cd stockvaluefinder && uv run pytest tests/ --cov=stockvaluefinder --cov-report=term-missing` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAPEX-01 | Buyback yield calculation from repurchase data | unit | `uv run pytest tests/unit/test_services/test_capex_service.py::test_calculate_buyback_yield -x` | Wave 0 |
| CAPEX-01 | Buyback data fetch + cache from AKShare | unit | `uv run pytest tests/unit/test_external/test_data_service_capex.py::test_get_buyback_data -x` | Wave 0 |
| CAPEX-02 | DPU trend classification via linregress | unit | `uv run pytest tests/unit/test_services/test_capex_service.py::test_classify_dividend_stability -x` | Wave 0 |
| CAPEX-02 | DPU trend with insufficient data | unit | `uv run pytest tests/unit/test_services/test_capex_service.py::test_classify_dividend_stability_insufficient -x` | Wave 0 |
| CAPEX-03 | Blind expansion alert when ROIC < WACC + CapEx surge | unit | `uv run pytest tests/unit/test_services/test_capex_service.py::test_detect_blind_expansion -x` | Wave 0 |
| CAPEX-03 | No alert when ROIC > WACC | unit | `uv run pytest tests/unit/test_services/test_capex_service.py::test_no_blind_expansion_when_value_creating -x` | Wave 0 |
| CAPEX-04 | Combined scorecard A/B/C/D grading | unit | `uv run pytest tests/unit/test_services/test_capex_service.py::test_calculate_capital_allocation_score -x` | Wave 0 |
| CAPEX-04 | Scorecard with missing dimension reweighting | unit | `uv run pytest tests/unit/test_services/test_capex_service.py::test_scorecard_with_missing_buyback -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_capex_service.py -x`
- **Per wave merge:** `cd stockvaluefinder && uv run pytest tests/ --cov=stockvaluefinder`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_services/test_capex_service.py` -- covers CAPEX-01 through CAPEX-04 pure function tests
- [ ] `tests/unit/test_services/__init__.py` -- package init (if not existing)
- [ ] `tests/unit/test_external/test_data_service_capex.py` -- data service extension tests
- [ ] `tests/unit/test_models/test_capital_allocation_models.py` -- Pydantic model validation tests

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (no auth in this phase) |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Pydantic `BaseModel` with `Field(..., pattern=...)` for ticker validation |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for Capital Allocation Scorecard

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed ticker bypass | Tampering | Pydantic `pattern=r"^\d{6}\.(SH|SZ|HK)$"` on request model |
| AKShare API rate limiting | Denial of Service | `_run_sync` has retry with backoff (2, 4, 8, 16, 30s); 0.5s min interval between requests |
| Redis cache poisoning | Tampering | Cache stores only AKShare public data; no user-controlled values in cache keys |

## Sources

### Primary (HIGH confidence)
- AKShare `stock_repurchase_em()` live verification: 5088 rows, 18 columns, Maotai has 2 rows with `已回购金额` [VERIFIED: 2026-05-05]
- `stockvaluefinder/services/roic_service.py` -- `analyze_roic_trend()` linregress pattern [CODE READ]
- `stockvaluefinder/external/data_service.py` -- `_cache_get_or_set()`, `get_roic_inputs()`, CapEx extraction [CODE READ]
- `stockvaluefinder/external/akshare_client.py` -- `_run_sync()`, `fetch_multi_year_financials()` pattern [CODE READ]
- `stockvaluefinder/api/roic_routes.py` -- route structure, error handling, persistence pattern [CODE READ]
- `stockvaluefinder/repositories/roic_repo.py` -- `upsert_by_ticker_year()` pattern [CODE READ]
- `stockvaluefinder/config.py` -- frozen dataclass pattern [CODE READ]

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` -- comprehensive AKShare API mapping, verified 2026-05-03 [CITED]
- `.planning/research/PITFALLS.md` -- buyback data pitfalls, CapEx handling, grade boundary issues [CITED]

### Tertiary (LOW confidence)
- Grade boundary thresholds (A1-A4) are based on domain knowledge and need validation with real CSI 300 data [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies verified installed, APIs tested live
- Architecture: HIGH -- 80% reuse of existing Phase 9 patterns; only new component is buyback data fetch
- Pitfalls: HIGH -- buyback data verified live, CapEx extraction pattern confirmed in codebase
- Grade thresholds: MEDIUM -- based on domain knowledge, need validation with real data

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (stable domain, AKShare API is stable)
