# Phase 29: Pledge Data Foundation - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

System can reliably fetch and cache A-share equity pledge data from AKShare with proper field normalization and automatic date discovery. This phase delivers the data layer: Pydantic models, AKShare client methods, field mapping, ticker normalization, ExternalDataService pledge interfaces, Redis caching, and date backfill logic. Downstream phases (30-31) consume this data for risk calculation and API integration.

**In scope:** DATA-01 through DATA-07 (data fetching, field mapping, normalization, caching, date discovery, Tushare fallback)
**Out of scope:** Risk calculation (Phase 30), DB persistence/API integration (Phase 31)
</domain>

<decisions>
## Implementation Decisions

### Ticker Normalization
- **D-01:** `normalize_a_share_ticker` function lives in `stockvaluefinder/utils/validators.py` as a reusable utility
- **D-02:** Prefix mapping: 6xx -> .SH (上交所主板), 0xx/3xx -> .SZ (深交所主板+创业板). BSE codes (8xx/4xx) are rejected — return None with a warning log
- **D-03:** Function performs both format validation (6 digits, all numeric) AND prefix validation (must be 0xx/3xx/6xx). Invalid codes like `999999` return None
- **D-04:** Return type is `str | None` — None for unsupported/invalid codes, no exceptions raised. Caller decides how to handle None

### Bulk vs Per-Stock API Design
- **D-05:** ExternalDataService exposes per-ticker methods (`get_equity_pledge_snapshot(ticker, date)`, `get_equity_pledge_details(ticker)`) that internally handle bulk AKShare fetch, cache, and filter
- **D-06:** Cache strategy: store entire AKShare bulk response as a single Redis value keyed by trade_date (ratio) or `latest` (detail). Filter in-memory on per-ticker read. One cache entry per date, amortized across all ticker lookups
- **D-07:** Same bulk-cache-filter pattern applies to both ratio data (`stock_gpzy_pledge_ratio_em`) and detail data (`stock_gpzy_pledge_ratio_detail_em`)

### Missing Ticker Handling
- **D-08:** Ticker absent from a non-empty bulk response = the stock has zero pledges. Return a full `EquityPledgeSnapshot` with `company_pledge_ratio=0`, all numeric fields zeroed, `freshness=CURRENT`, no warnings
- **D-09:** Distinguish data source health: if bulk response has data for other tickers (non-empty), missing ticker = zero pledges. If bulk response is completely empty or AKShare failed, freshness = UNAVAILABLE
- **D-10:** Zero-pledge stocks get a full snapshot response (not a minimal "no data" object). This ensures consistent downstream handling

### Claude's Discretion
- Exact Pydantic model field types and validation rules (follow tech design §8)
- AKShare error wrapping pattern (follow existing ExternalAPIError convention)
- Redis cache key format (follow tech design §6.1 or existing cache key conventions)
- Date backfill implementation details (follow REQUIREMENTS DATA-06)
- Tushare fallback activation logic (follow REQUIREMENTS DATA-07)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### PRD & Technical Design
- `doc/equity_pledge_risk_analysis_prd.md` — Product requirements, data fields, risk grading rules, acceptance criteria
- `doc/equity_pledge_risk_analysis_technical_design.md` — Architecture, field mappings (§5.2), cache strategy (§6), Pydantic models (§8), AKShare interface signatures (§5.1), data quality rules (§11.3)

### Requirements
- `.planning/REQUIREMENTS.md` — DATA-01 through DATA-07 (locked requirements for this phase)

### Existing Code Patterns
- `stockvaluefinder/external/akshare_client.py` — Existing AKShare client with `asyncio.run_in_executor` pattern and field mapping conventions
- `stockvaluefinder/external/data_service.py` — ExternalDataService facade with fallback chain and cache integration
- `stockvaluefinder/utils/validators.py` — Where `normalize_a_share_ticker` will live
- `stockvaluefinder/utils/cache.py` — CacheManager with `@cache_result` decorator pattern
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **AKShareClient**: Already uses `asyncio.run_in_executor` for sync AKShare calls. New pledge methods follow the same pattern
- **CacheManager**: Redis caching with TTL, `@cache_result` decorator available. Pledge data uses 24h TTL matching financial data pattern
- **ExternalDataService**: Unified facade with lazy init/shutdown. New pledge methods integrate here
- **validators.py**: Existing ticker pattern validation (`r"^\d{6}\.(SH|SZ|HK)$"`). `normalize_a_share_ticker` complements this

### Established Patterns
- **Field mapping**: Client layer transforms AKShare Chinese field names to internal English names. 集中在一个 mapping dict
- **Error wrapping**: AKShare exceptions -> `ExternalAPIError` with structured details
- **Graceful degradation**: External data failures return None or empty results, never crash the caller
- **Frozen config**: PledgeConfig (if needed) should be frozen dataclass matching ValuationConfig pattern

### Integration Points
- **AKShareClient**: Add `get_equity_pledge_ratio_by_date()` and `get_equity_pledge_ratio_detail()` methods
- **ExternalDataService**: Add `get_equity_pledge_snapshot()` and `get_equity_pledge_details()` methods with Redis caching
- **validators.py**: Add `normalize_a_share_ticker()` function
- **models/equity_pledge.py**: New file for Pydantic models (EquityPledgeSnapshot, EquityPledgeDetail, DataFreshness, EquityPledgeDataQuality)
</code_context>

<specifics>
## Specific Ideas

No specific requirements — implementation follows established patterns from existing data clients and the tech design document.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 29-Pledge Data Foundation*
*Context gathered: 2026-06-05*
