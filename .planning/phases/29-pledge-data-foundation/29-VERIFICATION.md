---
phase: 29-pledge-data-foundation
verified: 2026-06-06T12:00:00Z
status: gaps_found
score: 12/13 must-haves verified
overrides_applied: 0
gaps:
  - truth: "System uses Tushare pledge_detail as optional fallback for shareholder details when AKShare data is unavailable (DATA-07)"
    status: failed
    reason: "TushareClient has no pledge-related methods. get_equity_pledge_details() returns empty list when AKShare returns no data, with no Tushare fallback path. Test is a skeleton that only verifies the empty-list behavior."
    artifacts:
      - path: "stockvaluefinder/stockvaluefinder/external/data_service.py"
        issue: "get_equity_pledge_details() has no Tushare fallback; returns empty list when AKShare bulk is empty or no matching records"
      - path: "stockvaluefinder/stockvaluefinder/external/tushare_client.py"
        issue: "No pledge_detail method exists in TushareClient"
      - path: "stockvaluefinder/tests/unit/test_external/test_data_service_pledge.py"
        issue: "TestTushareFallback is a skeleton test that only verifies empty list return, not actual fallback behavior"
    missing:
      - "TushareClient.pledge_detail method (or equivalent) for fetching shareholder pledge data from Tushare"
      - "Fallback logic in get_equity_pledge_details() to call Tushare when AKShare returns no matching records"
---

# Phase 29: Pledge Data Foundation Verification Report

**Phase Goal:** System can reliably fetch and cache A-share equity pledge data from AKShare with proper field normalization and automatic date discovery
**Verified:** 2026-06-06T12:00:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can fetch company pledge ratio snapshot for a given A-share ticker on a specific trade date, receiving company pledge ratio, pledged shares, market value, pledge count, unrestricted/restricted breakdown, and 1-year price change | VERIFIED | `data_service.py:2262` get_equity_pledge_snapshot returns EquityPledgeSnapshot with 12 fields including all listed metrics. Field mapping at lines 126-138 translates Chinese AKShare columns. |
| 2 | User can fetch important shareholder pledge details for a given A-share ticker, receiving holder name, pledge amounts, ratios, pledgee, closeout price, and dates | VERIFIED | `data_service.py:2323` get_equity_pledge_details returns list[EquityPledgeDetail] with 14 fields including holder_name, pledge_amount, pledged_to_holding_ratio, pledgee, estimated_closeout_price, start_date, announcement_date. |
| 3 | AKShare 6-digit stock codes are automatically normalized to internal ticker format (600519->600519.SH, 000002->000002.SZ) | VERIFIED | `validators.py:179-212` normalize_a_share_ticker maps 6xx->.SH, 0xx/3xx->.SZ, returns None for invalid/BSE. data_service.py:2311 uses ticker.split(".")[0] for reverse matching against raw AKShare codes. |
| 4 | Pledge ratio data cached in Redis with 24h TTL keyed by trade date, detail data cached with 24h TTL keyed by latest | VERIFIED | `data_service.py:2303-2306` ratio cache key_parts=("equity_pledge","ratio",trade_date), ttl=86400. `data_service.py:2354-2357` detail cache key_parts=("equity_pledge","ratio_detail","latest"), ttl=86400. |
| 5 | When no trade date specified, system auto-finds latest available date by trying last 10 calendar days in reverse order | VERIFIED | `data_service.py:2234-2260` _find_latest_pledge_date iterates range(10), subtracts timedelta(days=i), calls get_equity_pledge_ratio_by_date per candidate, returns first non-empty result. |
| 6 | 6-digit AKShare codes normalized with BSE/invalid returning None and warning log | VERIFIED | `validators.py:205-212` validates 6-digit numeric, prefix check, logger.warning for unsupported codes. 9 tests in TestNormalizeAShareTicker cover all branches. |
| 7 | EquityPledgeSnapshot model is frozen with all required fields | VERIFIED | `equity_pledge.py:27-55` frozen=True, 12 fields including data_quality. Test verifies FrozenInstanceError on mutation. |
| 8 | EquityPledgeDetail model is frozen with all required fields | VERIFIED | `equity_pledge.py:58-88` frozen=True, 14 fields. Test verifies FrozenInstanceError on mutation. |
| 9 | DataFreshness enum provides CURRENT/STALE/UNAVAILABLE | VERIFIED | `enums.py:104-109` three-member str enum. Used in data_service.py at lines 2086, 2090, 2147, 2174. |
| 10 | EquityPledgeDataQuality captures source, date, freshness, warnings | VERIFIED | `equity_pledge.py:11-24` frozen model with source, latest_date, fetched_at, freshness, warnings fields. |
| 11 | Missing ticker from non-empty bulk returns zero-pledge snapshot (company_pledge_ratio=0, freshness=CURRENT) | VERIFIED | `data_service.py:2117-2118` _build_zero_pledge_snapshot returns full snapshot with ratio=0.0, all numeric fields zeroed. Test at test_data_service_pledge.py confirms behavior. |
| 12 | Empty bulk response returns UNAVAILABLE freshness with warning | VERIFIED | `data_service.py:2163-2181` _build_unavailable_snapshot returns None fields, freshness=UNAVAILABLE, warnings=["Pledge data unavailable..."]. Test confirms. |
| 13 | Tushare pledge_detail as optional fallback when AKShare data unavailable (DATA-07) | FAILED | TushareClient has no pledge methods. get_equity_pledge_details returns empty list when AKShare has no data. Skeleton test only verifies empty-list return. |

**Score:** 12/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `stockvaluefinder/models/equity_pledge.py` | DataFreshness, EquityPledgeDataQuality, EquityPledgeSnapshot, EquityPledgeDetail | VERIFIED | 89 lines, 3 frozen models + imports. All exports present. |
| `stockvaluefinder/utils/validators.py` | normalize_a_share_ticker function | VERIFIED | Function at line 179, 34 lines, proper prefix mapping, logging, docstring with doctests. |
| `stockvaluefinder/models/enums.py` | DataFreshness enum | VERIFIED | Enum at line 104 with CURRENT, STALE, UNAVAILABLE. |
| `stockvaluefinder/tests/unit/test_models/test_equity_pledge.py` | Pydantic model tests | VERIFIED | 213 lines, 15 test methods across 4 test classes. Exceeds min_lines:60. |
| `stockvaluefinder/tests/unit/test_utils/test_validators.py` | TestNormalizeAShareTicker class | VERIFIED | 9 test methods at lines 172-209 covering SH, SZ, ChiNext, BSE 8xx/4xx, invalid, non-numeric, short code, whitespace. |
| `stockvaluefinder/external/akshare_client.py` | get_equity_pledge_ratio_by_date, get_equity_pledge_ratio_detail | VERIFIED | Methods at lines 684 and 709, both substantive (call ak.stock_gpzy_pledge_ratio_em and ak.stock_gpzy_pledge_ratio_detail_em respectively). |
| `stockvaluefinder/external/data_service.py` | get_equity_pledge_snapshot, get_equity_pledge_details, _find_latest_pledge_date, helpers, field maps | VERIFIED | All 3 public + 5 private methods + 2 field map constants present and substantive. |
| `stockvaluefinder/tests/unit/test_external/test_akshare_equity_pledge.py` | AKShare pledge method tests | VERIFIED | 158 lines, 7 async tests in 2 classes. Exceeds min_lines:80. |
| `stockvaluefinder/tests/unit/test_external/test_data_service_pledge.py` | DataService pledge facade tests | VERIFIED | 503 lines, 15 async tests in 5 classes. Exceeds min_lines:120. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| equity_pledge.py | enums.py | import DataFreshness | WIRED | Line 8: `from stockvaluefinder.models.enums import DataFreshness`. Used in EquityPledgeDataQuality.freshness field type. |
| validators.py | logging | logger.warning for unsupported codes | WIRED | Line 10: `logger = logging.getLogger(__name__)`. Line 211: `logger.warning(...)`. |
| data_service.py get_equity_pledge_snapshot | akshare_client.py get_equity_pledge_ratio_by_date | async call in _fetch closure | WIRED | Line 2301: `return await self._akshare.get_equity_pledge_ratio_by_date(trade_date)`. |
| data_service.py get_equity_pledge_snapshot | cache.py _cache_get_or_set | cache key (equity_pledge, ratio, trade_date) | WIRED | Lines 2303-2306: `_cache_get_or_set(key_parts=("equity_pledge","ratio",trade_date), ttl=86400, fetch_fn=_fetch)`. |
| data_service.py get_equity_pledge_snapshot | validators.py normalize_a_share_ticker | ticker normalization | PARTIAL | normalize_a_share_ticker NOT imported. Filtering uses `ticker.split(".")[0]` at line 2311 which achieves same result for inbound tickers but does not use the shared utility. Functionally correct but plan deviation. |
| data_service.py get_equity_pledge_details | akshare_client.py get_equity_pledge_ratio_detail | async call in _fetch closure | WIRED | Line 2352: `return await self._akshare.get_equity_pledge_ratio_detail()`. |
| data_service.py get_equity_pledge_details | TushareClient pledge_detail | Tushare fallback | NOT_WIRED | No Tushare fallback exists. TushareClient has no pledge methods. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| akshare_client.get_equity_pledge_ratio_by_date | df (DataFrame) | ak.stock_gpzy_pledge_ratio_em(date=trade_date) | Yes -- calls real AKShare function | FLOWING |
| akshare_client.get_equity_pledge_ratio_detail | df (DataFrame) | ak.stock_gpzy_pledge_ratio_detail_em() | Yes -- calls real AKShare function | FLOWING |
| data_service.get_equity_pledge_snapshot | bulk_data | _cache_get_or_set -> akshare_client.get_equity_pledge_ratio_by_date | Yes -- chains through cache to AKShare | FLOWING |
| data_service.get_equity_pledge_details | bulk_data | _cache_get_or_set -> akshare_client.get_equity_pledge_ratio_detail | Yes -- chains through cache to AKShare | FLOWING |
| data_service._find_latest_pledge_date | data (list) | akshare_client.get_equity_pledge_ratio_by_date per candidate date | Yes -- real AKShare calls | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All pledge-related tests pass | `DATABASE_URL=... uv run pytest tests/unit/test_models/test_equity_pledge.py tests/unit/test_utils/test_validators.py::TestNormalizeAShareTicker tests/unit/test_external/test_akshare_equity_pledge.py tests/unit/test_external/test_data_service_pledge.py -x -q` | 48 passed in 1.53s | PASS |
| Full external test suite no regressions | `DATABASE_URL=... uv run pytest tests/unit/test_external/ -x -q` | 123 passed in 7.47s | PASS |
| Ruff lint clean on all modified files | `uv run ruff check stockvaluefinder/models/equity_pledge.py stockvaluefinder/utils/validators.py stockvaluefinder/models/enums.py stockvaluefinder/external/akshare_client.py stockvaluefinder/external/data_service.py` | All checks passed! | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-01 | 29-02 | Fetch A-share equity pledge ratio data via AKShare stock_gpzy_pledge_ratio_em | SATISFIED | akshare_client.py:702 calls ak.stock_gpzy_pledge_ratio_em(date=trade_date). Returns list of dicts with all specified fields. |
| DATA-02 | 29-02 | Fetch shareholder pledge details via AKShare stock_gpzy_pledge_ratio_detail_em | SATISFIED | akshare_client.py:722 calls ak.stock_gpzy_pledge_ratio_detail_em(). Returns list of dicts with holder name, amounts, ratios, dates. |
| DATA-03 | 29-01 | Normalize 6-digit AKShare codes to internal ticker format | SATISFIED | validators.py:179 normalize_a_share_ticker with 6xx->.SH, 0xx/3xx->.SZ. 9 tests covering all branches. |
| DATA-04 | 29-02 | Cache pledge ratio in Redis 24h TTL keyed by trade date | SATISFIED | data_service.py:2303-2306 _cache_get_or_set(key_parts=("equity_pledge","ratio",trade_date), ttl=86400). |
| DATA-05 | 29-02 | Cache pledge detail in Redis 24h TTL keyed by latest | SATISFIED | data_service.py:2354-2357 _cache_get_or_set(key_parts=("equity_pledge","ratio_detail","latest"), ttl=86400). |
| DATA-06 | 29-02 | Auto-find latest trade date trying last 10 calendar days | SATISFIED | data_service.py:2234-2260 _find_latest_pledge_date iterates range(10) in reverse, calls AKShare per candidate. |
| DATA-07 | 29-02 | Tushare pledge_detail as optional fallback | BLOCKED | TushareClient has no pledge methods. get_equity_pledge_details has no fallback path. Skeleton test only. |

### Anti-Patterns Found

No TBD, FIXME, XXX, or unreferenced TODO markers found in phase-modified files. No stub returns or placeholder implementations in pledge-specific code.

### Human Verification Required

None -- all truths are programmatically verifiable and have been checked.

### Gaps Summary

**1 gap found:**

**DATA-07 (Tushare pledge_detail fallback):** The requirement states the system should use Tushare pledge_detail as an optional fallback for shareholder details when AKShare data is unavailable. The implementation has no Tushare fallback path at all. TushareClient has zero pledge-related methods. The `get_equity_pledge_details()` method returns an empty list when AKShare returns no data. The test for this path is a skeleton test that only verifies the empty-list return behavior.

**Impact:** If AKShare's `stock_gpzy_pledge_ratio_detail_em()` returns empty data (API outage, rate limiting), there is no secondary data source for shareholder pledge details. This affects downstream risk calculation in Phase 30 which may have incomplete data.

**Mitigation:** AKShare is the primary and reliable free data source for A-share equity pledges. The likelihood of persistent AKShare unavailability is low. The fallback was always marked as "optional" in the requirement text.

**This looks intentional.** The PLAN itself labeled the test as a "skeleton test, may skip if Tushare not configured." To accept this deviation, add to VERIFICATION.md frontmatter:

```yaml
overrides:
  - must_have: "System uses Tushare pledge_detail as optional fallback for shareholder details when AKShare data is unavailable (DATA-07)"
    reason: "AKShare is the primary reliable free data source. Tushare pledge_detail API requires token and may not be freely available. Skeleton test documents intended future implementation."
    accepted_by: ""
    accepted_at: ""
```

---

_Verified: 2026-06-06T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
