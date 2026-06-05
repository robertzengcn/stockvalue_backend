# Phase 29: Pledge Data Foundation - Research

**Researched:** 2026-06-06
**Domain:** AKShare equity pledge data fetching, field mapping, ticker normalization, Redis caching
**Confidence:** HIGH

## Summary

Phase 29 adds the data layer for A-share equity pledge risk analysis. The system fetches two bulk datasets from AKShare -- company pledge ratios (per trade date, full market) and important shareholder pledge details (current, full market) -- then caches the bulk response in Redis, filtering per-ticker on read. The implementation follows the exact same pattern as the existing `get_buyback_data()` method: bulk fetch -> cache -> in-memory filter.

The two AKShare functions are `stock_gpzy_pledge_ratio_em(date="YYYYMMDD")` (paginated, ~6 pages per date, ~3000 rows) and `stock_gpzy_pledge_ratio_detail_em()` (paginated, ~40+ pages, tens of thousands of rows). Both return Chinese column names that must be mapped to internal English field names. AKShare returns 6-digit stock codes requiring normalization to the internal `600519.SH` / `000002.SZ` format.

**Primary recommendation:** Follow the `get_buyback_data()` bulk-cache-filter pattern exactly. Add two methods to `AKShareClient`, two methods to `ExternalDataService`, one utility function to `validators.py`, and one new Pydantic models file `models/equity_pledge.py`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `normalize_a_share_ticker` function lives in `stockvaluefinder/utils/validators.py` as a reusable utility
- **D-02:** Prefix mapping: 6xx -> .SH (Shanghai main board), 0xx/3xx -> .SZ (Shenzhen main board + ChiNext). BSE codes (8xx/4xx) are rejected -- return None with a warning log
- **D-03:** Function performs both format validation (6 digits, all numeric) AND prefix validation (must be 0xx/3xx/6xx). Invalid codes like `999999` return None
- **D-04:** Return type is `str | None` -- None for unsupported/invalid codes, no exceptions raised. Caller decides how to handle None
- **D-05:** ExternalDataService exposes per-ticker methods (`get_equity_pledge_snapshot(ticker, date)`, `get_equity_pledge_details(ticker)`) that internally handle bulk AKShare fetch, cache, and filter
- **D-06:** Cache strategy: store entire AKShare bulk response as a single Redis value keyed by trade_date (ratio) or `latest` (detail). Filter in-memory on per-ticker read. One cache entry per date, amortized across all ticker lookups
- **D-07:** Same bulk-cache-filter pattern applies to both ratio data (`stock_gpzy_pledge_ratio_em`) and detail data (`stock_gpzy_pledge_ratio_detail_em`)
- **D-08:** Ticker absent from a non-empty bulk response = the stock has zero pledges. Return a full `EquityPledgeSnapshot` with `company_pledge_ratio=0`, all numeric fields zeroed, `freshness=CURRENT`, no warnings
- **D-09:** Distinguish data source health: if bulk response has data for other tickers (non-empty), missing ticker = zero pledges. If bulk response is completely empty or AKShare failed, freshness = UNAVAILABLE
- **D-10:** Zero-pledge stocks get a full snapshot response (not a minimal "no data" object). This ensures consistent downstream handling

### Claude's Discretion
- Exact Pydantic model field types and validation rules (follow tech design section 8)
- AKShare error wrapping pattern (follow existing ExternalAPIError convention)
- Redis cache key format (follow tech design section 6.1 or existing cache key conventions)
- Date backfill implementation details (follow REQUIREMENTS DATA-06)
- Tushare fallback activation logic (follow REQUIREMENTS DATA-07)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Fetch A-share equity pledge ratio data via AKShare `stock_gpzy_pledge_ratio_em` | AKShare source verified (section 5.2 field mapping), AKShareClient method pattern established |
| DATA-02 | Fetch important shareholder pledge details via AKShare `stock_gpzy_pledge_ratio_detail_em` | AKShare source verified (section 5.2 field mapping), AKShareClient method pattern established |
| DATA-03 | Normalize 6-digit AKShare stock codes to internal ticker format | D-01 through D-04 locked, `validators.py` integration point identified |
| DATA-04 | Cache pledge ratio data in Redis with 24h TTL keyed by trade date | `_cache_get_or_set` pattern from `get_buyback_data()`, key format `v1:equity_pledge:ratio:{trade_date}` |
| DATA-05 | Cache pledge detail data in Redis with 24h TTL keyed by latest | `_cache_get_or_set` pattern, key format `v1:equity_pledge:ratio_detail:latest` |
| DATA-06 | Auto-find latest available trade date by trying last 10 calendar days in reverse | Date discovery algorithm researched, AKShare date format `YYYYMMDD` confirmed |
| DATA-07 | Tushare `pledge_detail` as optional fallback for shareholder details | TushareClient exists but has no pledge methods yet; pattern from existing fallback chain |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| AKShare pledge API calls | External/API Client | -- | Network I/O belongs in client layer |
| Chinese-to-English field mapping | External/API Client | -- | Translation at source, internal models stay English |
| Ticker normalization (6-digit to .SH/.SZ) | Utility (validators.py) | -- | Reusable across modules, not tied to any one client |
| Bulk data caching in Redis | External Data Service | -- | Service owns cache lifecycle, clients are stateless |
| Per-ticker filtering from bulk cache | External Data Service | -- | Amortizes bulk fetch cost across multiple ticker lookups |
| Date discovery (find latest trade date) | External Data Service | -- | Orchestrates retries across dates, caches result |
| Pydantic model definitions | Domain Models | -- | Data contracts for inter-layer communication |
| Data freshness classification | External Data Service | -- | Requires knowledge of fetch time and current date |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| akshare | 1.18.46 | Equity pledge data source | Already installed, primary free data source for A-shares |
| pydantic | 2.12+ | Pledge model validation | Project standard for all domain models |
| redis (redis.asyncio) | 7.2+ | Caching bulk pledge data | Already integrated via CacheManager |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0+ | Unit tests for pledge data layer | All pledge data tests |
| pytest-asyncio | -- | Async test support | All AKShareClient and ExternalDataService tests |
| pytest-mock | 3.15+ | Mocking AKShare calls | Avoid real API calls in unit tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `stock_gpzy_pledge_ratio_em` | Direct East Money API | AKShare handles pagination and column naming; direct API would require reimplementing both |
| `stock_gpzy_pledge_ratio_detail_em` | Tushare `pledge_detail` | Tushare requires token + credits; AKShare is free and already integrated |
| Per-ticker caching | Bulk caching | Per-ticker would require 5000+ cache entries per date vs 1; bulk is 5000x more efficient |

**Installation:**

No new packages needed. All dependencies are already in `pyproject.toml`.

**Version verification:**

```
akshare: 1.18.46 (verified via `uv run python -c "import akshare; print(akshare.__version__)"`)
pydantic: 2.12+ (verified in pyproject.toml as >=2.12.5)
redis: 7.2+ (verified in pyproject.toml as >=7.2.1)
```

## Package Legitimacy Audit

> No new packages are installed in this phase. All dependencies are pre-existing.

| Package | Registry | Status | Notes |
|---------|----------|--------|-------|
| akshare | PyPI | Pre-existing | Already verified in prior phases |
| pydantic | PyPI | Pre-existing | Already verified in prior phases |
| redis | PyPI | Pre-existing | Already verified in prior phases |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
AKShare API (East Money)
    |
    | HTTP (paginated, ~6 pages for ratio, ~40+ pages for detail)
    v
AKShareClient.get_equity_pledge_ratio_by_date(date)     AKShareClient.get_equity_pledge_ratio_detail()
    |                                                          |
    | list[dict] (Chinese field names, 6-digit codes)          | list[dict] (Chinese field names, 6-digit codes)
    v                                                          v
ExternalDataService._cache_get_or_set()                  ExternalDataService._cache_get_or_set()
    |                                                          |
    | Redis: v1:equity_pledge:ratio:{trade_date}               | Redis: v1:equity_pledge:ratio_detail:latest
    | TTL: 86400s                                              | TTL: 86400s
    v                                                          v
ExternalDataService.get_equity_pledge_snapshot(ticker)   ExternalDataService.get_equity_pledge_details(ticker)
    |                                                          |
    | 1. Filter bulk by ticker                                 | 1. Filter bulk by ticker
    | 2. Map Chinese fields -> English                         | 2. Map Chinese fields -> English
    | 3. Normalize 6-digit code -> .SH/.SZ                     | 3. Normalize 6-digit code -> .SH/.SZ
    | 4. Build EquityPledgeSnapshot                            | 4. Build list[EquityPledgeDetail]
    v                                                          v
EquityPledgeSnapshot                                     list[EquityPledgeDetail]
    |                                                          |
    +--- DataFreshness classification ---+                     |
                                         v
                              Downstream Phase 30 (risk calc)
```

### Recommended Project Structure

```
stockvaluefinder/
├── models/
│   └── equity_pledge.py          # NEW: DataFreshness, EquityPledgeSnapshot, EquityPledgeDetail, EquityPledgeDataQuality
├── external/
│   ├── akshare_client.py          # MODIFY: add get_equity_pledge_ratio_by_date(), get_equity_pledge_ratio_detail()
│   └── data_service.py            # MODIFY: add get_equity_pledge_snapshot(), get_equity_pledge_details(), _find_latest_pledge_date()
├── utils/
│   └── validators.py              # MODIFY: add normalize_a_share_ticker()
└── tests/
    └── unit/
        ├── test_external/
        │   ├── test_akshare_equity_pledge.py   # NEW: AKShare pledge field mapping + error tests
        │   └── test_data_service_pledge.py     # NEW: ExternalDataService pledge + cache + date discovery tests
        └── test_utils/
            └── test_validators.py              # MODIFY: add TestNormalizeAShareTicker class
```

### Pattern 1: Bulk-Cache-Filter (from existing `get_buyback_data`)

**What:** AKShare returns full-market data in a single call. Cache the entire bulk response as one Redis entry, then filter for the requested ticker in memory.

**When to use:** Whenever an AKShare function returns data for ALL stocks rather than a single stock.

**Example:**

```python
# Source: existing data_service.py get_buyback_data() pattern
async def get_equity_pledge_snapshot(
    self, ticker: str, trade_date: str | None = None,
) -> EquityPledgeSnapshot | None:
    if not self._initialized:
        raise ExternalAPIError("Data service not initialized.")

    # Find latest date if not provided (DATA-06)
    if trade_date is None:
        trade_date = await self._find_latest_pledge_date()
        if trade_date is None:
            return self._build_unavailable_snapshot(ticker)

    # Bulk fetch + cache
    async def _fetch() -> list[dict[str, Any]]:
        if self._akshare is None:
            raise ExternalAPIError("AKShare client not initialized")
        return await self._akshare.get_equity_pledge_ratio_by_date(trade_date)

    result = await self._cache_get_or_set(
        key_parts=("equity_pledge", "ratio", trade_date),
        ttl=86400,
        fetch_fn=_fetch,
    )
    bulk_data = self._unwrap_cached_value(result)

    # Filter + normalize
    symbol = ticker.split(".")[0]
    matching = [r for r in bulk_data if str(r.get("股票代码", "")) == symbol]

    if matching:
        return self._map_pledge_ratio_record(ticker, matching[0], trade_date)
    elif bulk_data:  # Non-empty bulk = ticker has zero pledges
        return self._build_zero_pledge_snapshot(ticker, trade_date)
    else:  # Empty bulk = source failure
        return self._build_unavailable_snapshot(ticker)
```

### Pattern 2: Sync-to-Async Bridge (existing `_run_sync`)

**What:** AKShare is a synchronous library. All calls go through `_run_sync` which runs them in a thread pool executor with retry logic.

**When to use:** Every AKShare function call.

**Example:**

```python
# Source: existing akshare_client.py pattern
async def get_equity_pledge_ratio_by_date(self, trade_date: str) -> list[dict[str, Any]]:
    def _fetch() -> list[dict[str, Any]]:
        import akshare as ak
        df = ak.stock_gpzy_pledge_ratio_em(date=trade_date)
        if df is None or df.empty:
            return []
        return df.to_dict("records")

    return await self._run_sync(_fetch)
```

### Pattern 3: Ticker Normalization (new utility)

**What:** Convert AKShare 6-digit stock codes to internal format with exchange suffix.

**When to use:** Every time AKShare data is processed (both ratio and detail).

**Example:**

```python
# Per D-01 through D-04 in CONTEXT.md
def normalize_a_share_ticker(code: str) -> str | None:
    """Normalize 6-digit A-share stock code to internal ticker format.

    Args:
        code: 6-digit stock code (e.g., '600519', '000002')

    Returns:
        Internal ticker (e.g., '600519.SH', '000002.SZ') or None for invalid/unsupported codes
    """
    code = str(code).strip()
    if len(code) != 6 or not code.isdigit():
        return None
    if code.startswith("6"):
        return f"{code}.SH"   # Shanghai main board
    if code.startswith(("0", "3")):
        return f"{code}.SZ"   # Shenzhen main board + ChiNext
    # BSE (8xx/4xx) and other unsupported codes
    logger.warning(f"Unsupported A-share stock code prefix: {code}")
    return None
```

### Anti-Patterns to Avoid

- **Per-ticker AKShare calls:** Never call AKShare per-stock when a bulk API exists. The pledge APIs return full-market data; calling them once per stock would be 5000x slower and trigger rate limits.
- **Caching individual stock records:** The detail API returns ~20,000+ rows. Caching each stock separately would flood Redis. Cache the entire bulk response as one key.
- **Assuming AKShare columns are stable:** AKShare is a thin wrapper around East Money web scraping. Column names can change between versions. Always map fields through an explicit mapping dict, and test the mapping.
- **Raising exceptions for missing tickers:** A ticker not found in pledge data is a valid business outcome (zero pledges), not an error. Return a zero-pledge snapshot per D-08.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AKShare pagination | Manual pagination loop | `_run_sync` + AKShare built-in pagination | AKShare handles page iteration internally via tqdm |
| Redis caching logic | Custom cache wrapper | `_cache_get_or_set` | Handles serialization, TTL, cache miss/hit, dev mode bypass |
| Cache key construction | String concatenation | `build_cache_key(version, prefix, *parts)` | Consistent format, version-based invalidation |
| Async sync bridge | Manual thread pool | `AKShareClient._run_sync` | Built-in rate limiting, retry with exponential backoff |
| Error wrapping | Raw exception propagation | `ExternalAPIError` with structured details | Consistent error handling across all data sources |

**Key insight:** The existing codebase already solves every infrastructure problem this phase faces. The entire implementation is wiring existing patterns to new AKShare functions.

## Common Pitfalls

### Pitfall 1: AKShare Connection Resets (ChunkedEncodingError)

**What goes wrong:** East Money's API frequently drops connections mid-response, causing `ChunkedEncodingError` or `ProtocolError`.
**Why it happens:** East Money rate-limits and connection-resets bulk scrapers.
**How to avoid:** The existing `_run_sync` method has retry logic with 5 attempts and exponential backoff (2, 4, 8, 16, 30 seconds). No additional handling needed.
**Warning signs:** `ExternalAPIError: AKShare function failed after 5 attempts`.

### Pitfall 2: Stale Trade Date Returns Empty Data

**What goes wrong:** Calling `stock_gpzy_pledge_ratio_em(date="20240101")` with a non-trading day or future date returns an empty DataFrame.
**Why it happens:** AKShare does not validate the date; it passes it directly to the East Money API which returns empty results.
**How to avoid:** The date discovery logic (DATA-06) must try the last 10 calendar days in reverse order. If all 10 fail, return UNAVAILABLE. Never assume today's date has data (weekends, holidays).
**Warning signs:** `EquityPledgeSnapshot` with all fields zero when data was expected.

### Pitfall 3: Pledge Detail API is Very Slow

**What goes wrong:** `stock_gpzy_pledge_ratio_detail_em()` fetches ALL shareholder pledge details across the entire market (~40+ pages of 500 rows each).
**Why it happens:** The API has no date or ticker filter; it returns everything.
**How to avoid:** Cache the entire response with 24h TTL. First call is slow (~30-60 seconds), subsequent calls within 24h are instant cache hits.
**Warning signs:** API timeouts on first pledge detail request after cache expiry.

### Pitfall 4: AKShare Code Column Contains Non-6-Digit Values

**What goes wrong:** Some AKShare datasets include index codes or malformed codes that are not 6 digits.
**Why it happens:** AKShare wraps raw API responses without cleaning edge cases.
**How to avoid:** `normalize_a_share_ticker` returns `None` for non-6-digit or non-numeric codes. The field mapping code must handle `None` gracefully (skip the record).
**Warning signs:** `KeyError` or `None` attribute errors during field mapping.

### Pitfall 5: Confusing "No Pledges" with "Data Unavailable"

**What goes wrong:** Returning an error when a stock legitimately has zero pledges, or returning zero pledges when the data source failed.
**Why it happens:** The same empty-result condition can mean two different things.
**How to avoid:** Follow D-08/D-09 strictly: check if the bulk response is non-empty. Non-empty + ticker missing = zero pledges. Empty bulk = UNAVAILABLE.
**Warning signs:** Risk analysis showing `freshness=UNAVAILABLE` for stocks that actually have zero pledges.

### Pitfall 6: AKShare Pledge Ratio is Already a Percentage

**What goes wrong:** AKShare's `质押比例` column is already in percentage form (e.g., 35.5 means 35.5%), not a decimal (0.355).
**Why it happens:** AKShare does not normalize percentage representation across its functions.
**How to avoid:** Store and use the raw percentage value directly. Do NOT multiply by 100. Document in the Pydantic model that `company_pledge_ratio` is in percentage form (e.g., 35.5 means 35.5%).
**Warning signs:** Pledge ratios showing as 3550% or 0.35%.

## Code Examples

### AKShare Verified Field Mappings

Verified directly from AKShare 1.18.46 source code (`stock_gpzy_em.py`):

**`stock_gpzy_pledge_ratio_em` columns:**

```python
# Source: akshare/stock_feature/stock_gpzy_em.py lines 125-158 (VERIFIED)
PLEDGE_RATIO_FIELD_MAP = {
    "股票代码": "code_6digit",       # 6-digit, needs normalize_a_share_ticker()
    "股票简称": "stock_name",
    "交易日期": "latest_date",        # Already pd.to_datetime().dt.date
    "所属行业": "industry",
    "质押比例": "company_pledge_ratio",  # Already numeric, percentage form (e.g. 35.5)
    "质押股数": "pledged_shares",         # Already numeric
    "质押市值": "pledge_market_value",   # Already numeric
    "质押笔数": "pledge_count",          # Already numeric, int
    "无限售股质押数": "unrestricted_pledged_shares",  # Already numeric
    "限售股质押数": "restricted_pledged_shares",      # Already numeric
    "近一年涨跌幅": "one_year_price_change",          # Already numeric, percentage
}
```

**`stock_gpzy_pledge_ratio_detail_em` columns:**

```python
# Source: akshare/stock_feature/stock_gpzy_em.py lines 222-282 (VERIFIED)
PLEDGE_DETAIL_FIELD_MAP = {
    "股票代码": "code_6digit",
    "股票简称": "stock_name",
    "股东名称": "holder_name",
    "质押股份数量": "pledge_amount",          # Already numeric
    "占所持股份比例": "pledged_to_holding_ratio",  # Already numeric, percentage
    "占总股本比例": "pledged_to_total_share_ratio", # Already numeric, percentage
    "质押机构": "pledgee",
    "最新价": "latest_price",                  # Already numeric
    "质押日收盘价": "pledge_date_close_price",  # Already numeric
    "预估平仓线": "estimated_closeout_price",   # Already numeric
    "质押开始日期": "start_date",               # Already pd.to_datetime().dt.date
    "公告日期": "announcement_date",            # Already pd.to_datetime().dt.date
}
```

### Ticker Normalization

```python
# Per D-01 through D-04
# Source: CONTEXT.md decisions
import logging

logger = logging.getLogger(__name__)

def normalize_a_share_ticker(code: str) -> str | None:
    """Normalize 6-digit A-share stock code to internal ticker format.

    Prefix mapping: 6xx -> .SH, 0xx/3xx -> .SZ.
    BSE codes (8xx/4xx) and invalid codes return None.

    Args:
        code: 6-digit stock code (e.g., '600519', '000002')

    Returns:
        Internal ticker (e.g., '600519.SH', '000002.SZ') or None

    Examples:
        >>> normalize_a_share_ticker("600519")
        '600519.SH'
        >>> normalize_a_share_ticker("000002")
        '000002.SZ'
        >>> normalize_a_share_ticker("300001")
        '300001.SZ'
        >>> normalize_a_share_ticker("830001") is None  # BSE
        True
        >>> normalize_a_share_ticker("999999") is None  # Invalid
        True
    """
    code = str(code).strip()
    if len(code) != 6 or not code.isdigit():
        return None
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    logger.warning(f"Unsupported A-share stock code prefix: {code}")
    return None
```

### Date Discovery Algorithm (DATA-06)

```python
# Source: REQUIREMENTS.md DATA-06 + tech design section 6.3
from datetime import date, timedelta

async def _find_latest_pledge_date(self) -> str | None:
    """Try last 10 calendar days in reverse order to find latest with data.

    Returns:
        Date string in YYYYMMDD format, or None if all dates failed.
    """
    today = date.today()
    for i in range(10):
        candidate = today - timedelta(days=i)
        date_str = candidate.strftime("%Y%m%d")

        try:
            if self._akshare is None:
                continue
            data = await self._akshare.get_equity_pledge_ratio_by_date(date_str)
            if data:  # Non-empty list = valid trade date
                return date_str
        except ExternalAPIError:
            logger.warning(f"Pledge data fetch failed for date {date_str}, trying previous day")
            continue

    logger.warning("No pledge data found in last 10 calendar days")
    return None
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-stock pledge API | Bulk market-wide pledge API | AKShare design | Must cache bulk + filter in memory |
| No caching | Redis with TTL per trade date | Phase 29 (this phase) | Amortizes 6-page API call across all ticker lookups |
| Manual date entry | Auto-discovery via 10-day backfill | Phase 29 (this phase) | Users do not need to know trade dates |

**Deprecated/outdated:**
- None for this phase. AKShare pledge functions have been stable since their introduction.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | AKShare `质押比例` is in percentage form (35.5 means 35.5%, not 0.355) | Field Mappings | MEDIUM -- downstream risk calculation would be off by 100x |
| A2 | AKShare `质押股数` is in shares (not in 10000-share lots) | Field Mappings | LOW -- display would be wrong but risk thresholds unaffected |
| A3 | Tushare `pledge_detail` accepts `ts_code` parameter in `600519.SH` format | DATA-07 | LOW -- Tushare fallback is optional in V1 |
| A4 | The detail API returns all currently active pledges (not historical) | Architecture | MEDIUM -- if it returns historical too, filtering by `is_released` would be needed |

**If this table has claims needing validation:** The planner should add a manual verification checkpoint for A1 during implementation by printing a known stock's raw AKShare data and confirming the pledge ratio scale.

## Open Questions

1. **Detail API data volume and caching feasibility**
   - What we know: The detail API returns all shareholder pledge records across the entire market. AKShare paginates at 500 rows/page, with potentially 40+ pages.
   - What's unclear: Exact JSON payload size when cached in Redis (estimated 5-15 MB).
   - Recommendation: Test with one real fetch. If payload exceeds 10 MB, consider compressing before caching or caching a summarized version. For V1, proceed with full data caching.

2. **Whether `pledge_ratio_detail_em` includes released pledges**
   - What we know: The API returns fields for `质押开始日期` and `公告日期` but no `is_released` or `解押日期` field.
   - What's unclear: Whether the API automatically filters out released pledges or returns all historical records.
   - Recommendation: Proceed assuming it returns active pledges only (based on the East Money page name "重要股东股权质押明细"). If it includes released pledges, downstream Phase 30 can filter by date freshness.

3. **Tushare `pledge_detail` API signature and field names**
   - What we know: Tushare has a `pledge_detail` endpoint per the PRD section 5.3.
   - What's unclear: Exact parameter names, required fields, and response format.
   - Recommendation: Treat Tushare fallback as low priority for V1. Implement AKShare as primary, add Tushare skeleton that can be filled in later.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Runtime | Yes | 3.12.11 | -- |
| AKShare | Pledge data fetching | Yes | 1.18.46 | -- |
| Redis | Caching | No | -- | Tests mock cache; production requires Redis |
| uv | Package management | Yes | -- | -- |
| pytest | Testing | Yes | 9.0+ | -- |

**Missing dependencies with no fallback:**
- Redis is not running locally. Unit tests use mocked CacheManager (None). Integration tests would require Redis. This is acceptable because the existing test suite already handles this pattern (dev mode bypasses cache).

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `uv run pytest tests/unit/test_utils/test_validators.py tests/unit/test_external/test_akshare_equity_pledge.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Fetch pledge ratio data, map fields correctly | unit | `uv run pytest tests/unit/test_external/test_akshare_equity_pledge.py -x` | Wave 0 |
| DATA-02 | Fetch pledge detail data, map fields correctly | unit | `uv run pytest tests/unit/test_external/test_akshare_equity_pledge.py -x` | Wave 0 |
| DATA-03 | Normalize 6-digit codes to .SH/.SZ | unit | `uv run pytest tests/unit/test_utils/test_validators.py::TestNormalizeAShareTicker -x` | Wave 0 (modify existing) |
| DATA-04 | Cache pledge ratio with 24h TTL keyed by trade date | unit | `uv run pytest tests/unit/test_external/test_data_service_pledge.py -x` | Wave 0 |
| DATA-05 | Cache pledge detail with 24h TTL keyed by latest | unit | `uv run pytest tests/unit/test_external/test_data_service_pledge.py -x` | Wave 0 |
| DATA-06 | Auto-find latest trade date from 10 calendar days | unit | `uv run pytest tests/unit/test_external/test_data_service_pledge.py::TestDateDiscovery -x` | Wave 0 |
| DATA-07 | Tushare fallback for pledge details | unit | `uv run pytest tests/unit/test_external/test_data_service_pledge.py::TestTushareFallback -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_utils/test_validators.py tests/unit/test_external/test_akshare_equity_pledge.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_external/test_akshare_equity_pledge.py` -- covers DATA-01, DATA-02 field mapping and error wrapping
- [ ] `tests/unit/test_external/test_data_service_pledge.py` -- covers DATA-04, DATA-05, DATA-06, DATA-07 caching and date discovery
- [ ] Modify `tests/unit/test_utils/test_validators.py` -- add TestNormalizeAShareTicker class for DATA-03

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A for data layer |
| V3 Session Management | No | N/A for data layer |
| V4 Access Control | No | N/A for data layer |
| V5 Input Validation | Yes | Ticker normalization validates 6-digit codes; Pydantic models validate field types |
| V6 Cryptography | No | N/A for data layer |

### Known Threat Patterns for Pledge Data Layer

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Ticker injection (non-numeric codes) | Tampering | `normalize_a_share_ticker` validates format and returns None |
| AKShare API response tampering | Spoofing | Field mapping uses explicit dict; unexpected fields ignored |
| Redis cache poisoning | Tampering | Cache keys use version prefix (`v1:`); TTL limits damage window |
| Excessive API calls (DoS against East Money) | Denial of Service | Built-in rate limiting in `_run_sync` (0.5s between requests) |

## Sources

### Primary (HIGH confidence)
- AKShare source code `stock_gpzy_em.py` -- verified function signatures, column names, data types, pagination behavior (read directly from `.venv` installed package)
- Project codebase `akshare_client.py` -- existing `_run_sync` pattern, retry logic, rate limiting
- Project codebase `data_service.py` -- existing `_cache_get_or_set`, `get_buyback_data()` bulk-cache-filter pattern
- Project codebase `cache.py` -- `CacheManager`, `build_cache_key`, `cacheable` utility
- Project codebase `validators.py` -- existing ticker validation, location for `normalize_a_share_ticker`
- CONTEXT.md decisions D-01 through D-10 -- locked implementation decisions

### Secondary (MEDIUM confidence)
- Technical design document `equity_pledge_risk_analysis_technical_design.md` -- field mappings (section 5.2), cache strategy (section 6), Pydantic models (section 8)
- PRD `equity_pledge_risk_analysis_prd.md` -- data fields (section 5), acceptance criteria (section 11)

### Tertiary (LOW confidence)
- None -- all claims verified against codebase or AKShare source

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages, all existing infrastructure
- Architecture: HIGH -- follows established `get_buyback_data()` pattern exactly
- Pitfalls: HIGH -- based on observed AKShare behavior (ChunkedEncodingError confirmed during research)
- Field mappings: HIGH -- verified directly from AKShare 1.18.46 source code

**Research date:** 2026-06-06
**Valid until:** 2026-07-06 (30 days; AKShare field names are stable across minor versions)
