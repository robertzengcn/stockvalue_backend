---
phase: 02-redis-cache-integration
verified: 2026-04-15T15:30:00Z
status: gaps_found
score: 3/4
overrides_applied: 0
gaps:
  - truth: "CacheManager wired from lifespan through dependencies to data_service in production code path"
    status: failed
    reason: "main.py lifespan creates CacheManager on app.state.cache but never calls init_cache() to set _cache_instance in dependencies.py. get_initialized_data_service() reads _cache_instance which stays None in production."
    artifacts:
      - path: "stockvaluefinder/stockvaluefinder/main.py"
        issue: "Lifespan creates CacheManager on app.state.cache but does not call dependencies.init_cache() to bridge it to _cache_instance"
      - path: "stockvaluefinder/stockvaluefinder/api/dependencies.py"
        issue: "get_initialized_data_service() reads _cache_instance (line 95) but init_cache() is never called from production code; tests bypass this by directly setting deps._cache_instance"
    missing:
      - "Call to dependencies.init_cache() from main.py lifespan, OR read cache from app.state.cache in get_initialized_data_service()"
---

# Phase 2: Redis Cache Integration Verification Report

**Phase Goal:** External data responses are served from Redis cache with appropriate TTLs, reducing API latency and protecting upstream rate limits
**Verified:** 2026-04-15T15:30:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Repeated requests for the same stock's financial data within 24 hours return cached responses without hitting upstream APIs | VERIFIED | data_service.py `_cache_get_or_set` checks cache first (line 160), returns on hit with `hit=True` metadata; 6 methods cached with 86400 TTL; test suite confirms upstream skipped on hit (mock_akshare.assert_not_called) |
| 2 | Stock price data cached for 5 minutes and interest rate data for 1 hour, with distinct cache keys per ticker, year, and data type | VERIFIED | get_current_price TTL=300 (line 553); rate_client uses separate cache path; build_cache_key produces versioned keys like `v1:price:600519.SH`, `v1:fin_report:600519.SH:2023`; tests verify TTL and key format |
| 3 | Cache responses include a `cached_at` timestamp so consumers know data freshness | VERIFIED | `_cache_get_or_set` adds `_cache: {hit: false, cached_at: <ISO timestamp>}` on miss (line 178); cacheable() wrapper in cache.py does the same (line 249); test_cache_hit_metadata_preserved verifies original cached_at preserved on hit |
| 4 | Cache miss on fresh data still works correctly, fetching from upstream and populating cache | FAILED | Components work in isolation and in tests, but cache is never activated in production due to wiring gap between main.py and dependencies.py (see Wiring Gap Detail below) |

**Score:** 3/4 truths verified

### Wiring Gap Detail

The 4th truth (implicit in all success criteria) is that the cache system actually works end-to-end in a running application. While each component works in isolation and in tests, there is a **broken wire** between `main.py` and `dependencies.py`:

**main.py lifespan** (lines 43-50):
```python
cache = CacheManager(redis_url=settings.external_data.REDIS_URL)
try:
    await cache.connect()
    app.state.cache = cache
```

**dependencies.py** (line 95):
```python
service._cache = _cache_instance  # Always None in production
```

The lifespan stores the CacheManager on `app.state.cache` but never calls `init_cache()` from dependencies.py. The `_cache_instance` module variable stays `None`. Tests pass because they directly set `deps._cache_instance = mock_cache` (test_dependencies.py lines 40, 81, 102).

**Impact:** In production with Redis running, `get_initialized_data_service()` would always inject `cache=None` into ExternalDataService, making the application silently bypass all caching. Every request would hit upstream APIs directly, defeating the phase goal.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `config.py` (ExternalDataConfig) | REDIS_URL + 5 TTL fields + CACHE_KEY_VERSION | VERIFIED | All present, frozen dataclass, correct defaults |
| `main.py` (lifespan) | CacheManager init with graceful degradation | VERIFIED | Lines 43-61: connect/disconnect, try/except on failure |
| `dependencies.py` | init_cache + get_cache + cache injection into data_service | PARTIAL | init_cache and get_cache exist and are tested, but init_cache never called from production code |
| `cache.py` (build_cache_key + cacheable) | Versioned key builder + cache wrapper with cached_at | VERIFIED | build_cache_key (line 173), cacheable() (line 194), both substantive and tested |
| `data_service.py` | 6 cached methods with _cache_get_or_set | VERIFIED | get_financial_report, get_current_price, get_shares_outstanding, get_free_cash_flow, get_dividend_yield, get_stock_basic all wrapped with _cache_get_or_set |
| `test_config.py` | 10 tests for config | VERIFIED | 10/10 passing |
| `test_main_lifespan.py` | 3 tests for lifespan | VERIFIED | 3/3 passing |
| `test_dependencies.py` | 6 tests for DI | VERIFIED | 6/6 passing (but tests bypass real integration path) |
| `test_cache_utils.py` | 10 tests for cache utilities | VERIFIED | 10/10 passing |
| `test_data_service_cache.py` | 15 tests for data service cache | VERIFIED | 15/15 passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| main.py lifespan | dependencies._cache_instance | init_cache() call | NOT_WIRED | init_cache() never called; lifespan stores cache on app.state.cache instead |
| dependencies._cache_instance | data_service._cache | service._cache = _cache_instance (line 95) | NOT_WIRED | _cache_instance is always None in production because init_cache never called |
| data_service._cache | _cache_get_or_set | self._cache check (line 151) | WIRED | Correctly bypasses when None; fetches and stores when available |
| _cache_get_or_set | CacheManager.get/set | await self._cache.get(key) (line 160) | WIRED | Uses CacheManager methods correctly with error handling |
| routes | data_service | Depends(get_initialized_data_service) | WIRED | All 3 routes (risk, valuation, yield) use the dependency correctly |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| data_service._cache_get_or_set | self._cache | dependencies._cache_instance | No -- always None in production | HOLLOW |
| data_service.get_financial_report | result | _cache_get_or_set -> _fetch_financial_report | Yes -- upstream fetch works | FLOWING (when cache=None, falls through to fetch) |
| data_service.get_current_price | Decimal result | _cache_get_or_set -> _fetch_current_price | Yes -- upstream fetch works | FLOWING (when cache=None, falls through to fetch) |

Note: Data still flows correctly because the graceful degradation path (cache=None -> call upstream directly) works. But the caching layer is never activated in production.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase 02 tests pass | `uv run pytest test_config test_main_lifespan test_dependencies test_cache_utils test_data_service_cache -v` | 44 passed, 0 failed | PASS |
| Config frozen dataclass | Verified in code | ExternalDataConfig has frozen=True | PASS |
| Cache key format | Verified in code | build_cache_key("v1", "price", "600519.SH") = "v1:price:600519.SH" | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-01 | 02-01, 02-02 | Redis caching integrated into all external data routes (24h financials, 5min prices, 1h rates) | PARTIAL | All 6 data_service methods cached with correct TTLs (86400, 300, etc.), BUT cache never activated in production due to wiring gap between main.py and dependencies.py |
| DATA-02 | 02-02 | CacheManager wired into data_service, risk_service, valuation_service, and yield_service | PARTIAL | CacheManager wired into data_service via _cache attribute and _cache_get_or_set helper. risk_service, valuation_service, and yield_service do NOT directly reference CacheManager -- they receive pre-fetched data from data_service via routes. This architectural choice achieves the same caching effect (data is cached at the data_service level before reaching services), but does not match the literal requirement wording. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| dependencies.py / main.py | -- | Tests bypass real integration path by directly setting deps._cache_instance | Warning | Tests pass but do not verify the actual production code path; gives false confidence |
| dependencies.py | 19-33 | init_cache() function defined but never called from production code | Info | Dead code in production; only exercised in tests |

### Human Verification Required

### 1. Redis Cache End-to-End Test

**Test:** Start the application with Redis running, make two identical requests to `POST /api/v1/analyze/risk` for the same stock within a 24-hour window.
**Expected:** Second request should return `_cache: {hit: true, cached_at: <timestamp>}` and the AKShare upstream should not be called twice.
**Why human:** Requires running Redis server and full application, which cannot be tested programmatically without infrastructure.

### 2. Graceful Degradation Without Redis

**Test:** Start the application without Redis running, make a request to any analysis endpoint.
**Expected:** Application starts without error (logs warning about Redis unavailable), requests complete normally using upstream data sources directly.
**Why human:** Requires starting the full application with and without Redis.

### Gaps Summary

**1 critical wiring gap found: Cache never activated in production**

The `main.py` lifespan creates a CacheManager and stores it on `app.state.cache`, but the `dependencies.py` module-level `_cache_instance` variable is never set because `init_cache()` is never called. The `get_initialized_data_service()` function reads `_cache_instance` (which stays `None`) and injects it into the data service as `service._cache = None`.

**Fix required:** In `main.py` lifespan, after creating the CacheManager, call `init_cache()` from dependencies to bridge the instance:

```python
from stockvaluefinder.api.dependencies import init_cache
# After successful cache.connect():
init_cache(settings.external_data.REDIS_URL)
```

Or alternatively, modify `get_initialized_data_service()` to read from `app.state.cache` instead of `_cache_instance`.

**2. DATA-02 literal wording mismatch**

DATA-02 states "CacheManager wired into data_service, risk_service, valuation_service, and yield_service." The implementation only wires cache into data_service. The three domain services (risk, valuation, yield) receive pre-fetched data from the routes. This architectural choice achieves equivalent caching (all data flows through data_service which is cached), but does not match the literal requirement. This appears intentional given the architectural pattern.

---

_Verified: 2026-04-15T15:30:00Z_
_Verifier: Claude (gsd-verifier)_
