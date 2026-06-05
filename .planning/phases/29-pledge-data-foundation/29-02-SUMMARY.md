---
phase: 29-pledge-data-foundation
plan: 02
subsystem: external-data
tags: [akshare, equity-pledge, redis-cache, bulk-cache-filter, data-service]

# Dependency graph
requires:
  - 29-01 (EquityPledgeSnapshot, EquityPledgeDetail, DataFreshness, normalize_a_share_ticker)
provides:
  - AKShareClient.get_equity_pledge_ratio_by_date -- async method for bulk pledge ratio data
  - AKShareClient.get_equity_pledge_ratio_detail -- async method for bulk pledge detail data
  - ExternalDataService.get_equity_pledge_snapshot -- cached, filtered, normalized snapshot
  - ExternalDataService.get_equity_pledge_details -- cached, filtered, normalized details
  - ExternalDataService._find_latest_pledge_date -- 10-day reverse date discovery
  - PLEDGE_RATIO_FIELD_MAP -- Chinese-to-English field mapping constant
  - PLEDGE_DETAIL_FIELD_MAP -- Chinese-to-English field mapping constant
affects: [29-pledge-data-foundation, 30-pledge-risk-calc]

# Tech tracking
tech-stack:
  added: []
  patterns: [bulk-cache-filter, nan-to-none-normalization, date-discovery-10-day]

key-files:
  created:
    - stockvaluefinder/tests/unit/test_external/test_akshare_equity_pledge.py
    - stockvaluefinder/tests/unit/test_external/test_data_service_pledge.py
  modified:
    - stockvaluefinder/stockvaluefinder/external/akshare_client.py
    - stockvaluefinder/stockvaluefinder/external/data_service.py

key-decisions:
  - "NaN normalization uses helper methods (_normalize_pledge_numeric, _normalize_pledge_decimal, _normalize_pledge_int) rather than inline NaN checks for DRY"
  - "Date discovery tries 10 calendar days (not trading days) for simplicity; weekends/holidays naturally return empty data"
  - "Field maps are module-level constants for testability and import by downstream phases"

patterns-established:
  - "Bulk-cache-filter pattern for pledge data mirrors get_buyback_data() exactly"
  - "Zero-pledge snapshot (D-08) returns full EquityPledgeSnapshot with all fields zeroed"
  - "Unavailable snapshot (D-09) returns None numeric fields with UNAVAILABLE freshness"

requirements-completed: [DATA-01, DATA-02, DATA-04, DATA-05, DATA-06, DATA-07]

# Metrics
duration: 11min
completed: 2026-06-06
---

# Phase 29 Plan 02: Pledge Data Fetching Summary

**AKShare client pledge methods and ExternalDataService pledge facade with Redis caching, bulk-cache-filter pattern, and 10-day date discovery**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-05T19:03:50Z
- **Completed:** 2026-06-05T19:15:05Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added 2 AKShareClient methods wrapping stock_gpzy_pledge_ratio_em and stock_gpzy_pledge_ratio_detail_em
- Added 3 public methods + 5 private helpers + 2 field map constants to ExternalDataService
- Implemented bulk-cache-filter pattern with 24h TTL for both ratio and detail data
- Implemented _find_latest_pledge_date with 10-day reverse chronological search (DATA-06)
- Zero-pledge handling (D-08) returns full snapshot with ratio=0 and CURRENT freshness
- Unavailable handling (D-09) returns None fields with UNAVAILABLE freshness
- NaN-to-None normalization for all numeric fields extracted from AKShare data
- 24 new tests (7 AKShare + 17 DataService) covering all behaviors
- All 123 tests in test_external/ pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: AKShare client pledge methods and data service pledge facade** - `5778912` (feat) -- TDD: tests written first (RED), implementation added (GREEN)
2. **Task 2: Lint, type-check, and verify no regressions** - verification-only, all checks passed

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` - Added get_equity_pledge_ratio_by_date and get_equity_pledge_ratio_detail methods
- `stockvaluefinder/stockvaluefinder/external/data_service.py` - Added PLEDGE_RATIO_FIELD_MAP, PLEDGE_DETAIL_FIELD_MAP, get_equity_pledge_snapshot, get_equity_pledge_details, _find_latest_pledge_date, and 5 private helpers
- `stockvaluefinder/tests/unit/test_external/test_akshare_equity_pledge.py` - 7 tests in 2 classes (TestEquityPledgeRatioByDate, TestEquityPledgeRatioDetail)
- `stockvaluefinder/tests/unit/test_external/test_data_service_pledge.py` - 17 tests in 5 classes (TestEquityPledgeSnapshot, TestEquityPledgeDetails, TestDateDiscovery, TestFieldMapConstants, TestTushareFallback)

## Decisions Made
- NaN normalization uses dedicated helper methods rather than inline checks for DRY and testability
- Date discovery iterates 10 calendar days (not business days) for simplicity; non-trading days return empty data naturally
- Field maps are module-level constants (not instance attributes) so they can be imported and tested independently
- normalize_a_share_ticker import not added to data_service.py yet (unused in this plan); Phase 30 will add it when needed for pledge risk calculation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-commit hook rejected initial commit due to unused imports (normalize_a_share_ticker, math, timedelta, EquityPledgeDataQuality). Fixed by removing unused imports before re-committing.

## Next Phase Readiness
- All data fetching methods ready for Phase 30 (risk calculation) to consume
- get_equity_pledge_snapshot(ticker, date) returns structured EquityPledgeSnapshot with data quality metadata
- get_equity_pledge_details(ticker) returns list of EquityPledgeDetail with per-shareholder pledge records
- Bulk data cached per trade date for ratio, per "latest" for detail, both 24h TTL
- Field mapping from Chinese AKShare columns to English Pydantic model fields is complete and tested

## Self-Check: PASSED
- akshare_client.py: FOUND
- data_service.py: FOUND
- test_akshare_equity_pledge.py: FOUND
- test_data_service_pledge.py: FOUND
- Commit 5778912: FOUND
