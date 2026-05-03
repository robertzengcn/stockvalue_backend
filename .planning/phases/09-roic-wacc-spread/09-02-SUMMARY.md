---
phase: 09-roic-wacc-spread
plan: 02
subsystem: database, data-pipeline
tags: [roic, wacc, akshare, redis-cache, sqlalchemy, alembic, repository-pattern]

# Dependency graph
requires:
  - phase: prior-phases
    provides: AKShareClient, ExternalDataService, BaseRepository, SQLAlchemy Base, Alembic migrations 001-010
provides:
  - AKShareClient.fetch_multi_year_financials() for N-year profit+balance data (D-04)
  - ExternalDataService.get_roic_inputs() with 24h Redis cache (D-05)
  - ExternalDataService.get_multi_year_roic_inputs() with 24h Redis cache (D-05)
  - ROICResultDB ORM model for roic_results table
  - Alembic migration 011 creating roic_results table
  - ROICResultRepository with upsert_by_ticker_year and multi-year queries
affects: [09-03-service-layer, future-narrative-generation]

# Tech tracking
tech-stack:
  added: []
  patterns: [multi-year-financial-fetch, upsert-by-composite-key, lazy-import-for-parallel-plans]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/db/models/roic.py
    - stockvaluefinder/alembic/versions/011_roic_results_table.py
    - stockvaluefinder/stockvaluefinder/repositories/roic_repo.py
  modified:
    - stockvaluefinder/stockvaluefinder/external/akshare_client.py
    - stockvaluefinder/stockvaluefinder/external/data_service.py
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py

key-decisions:
  - "Lazy import with try/except for ROICResultCreate/ROICResultUpdate since Plan 01 creates them in parallel wave"
  - "fetch_multi_year_financials filters ALL periods in-memory rather than making per-year API calls"
  - "get_multi_year_roic_inputs uses _unwrap_cached_value to handle list caching via _cache_get_or_set"

patterns-established:
  - "Multi-year data fetch: single API call returning all periods, filter in-memory by fiscal year"
  - "Upsert by composite key: (ticker, fiscal_year) pattern mirrors upsert_by_report_id"
  - "Lazy import fallback: try/except for Pydantic models created by parallel plan"

requirements-completed: [ROIC-01, ROIC-06]

# Metrics
duration: 5min
completed: 2026-05-03
---

# Phase 9 Plan 2: ROIC Data Access Layer Summary

**Multi-year financial data pipeline with AKShare fetch, 24h Redis caching, ROICResultDB ORM model, Alembic migration 011, and upsert repository**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-03T06:28:12Z
- **Completed:** 2026-05-03T06:33:19Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- AKShareClient extended with fetch_multi_year_financials() for N-year profit+balance data in single API calls
- ExternalDataService orchestration with get_roic_inputs() and get_multi_year_roic_inputs(), both cached 24h in Redis
- ROICResultDB ORM model with all ROIC/WACC/spread fields and unique constraint on (ticker, fiscal_year)
- Alembic migration 011 creating roic_results table with indexes and unique constraint
- ROICResultRepository with upsert_by_ticker_year, get_by_ticker, get_latest_for_ticker, get_multi_year_for_ticker

## Task Commits

Each task was committed atomically:

1. **Task 1: Add multi-year financial fetch to AKShareClient + data_service orchestration** - `bc5fc8f` (feat)
2. **Task 2: Create ROICResultDB ORM model, Alembic migration, and repository** - `9e6c638` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` - Added fetch_multi_year_financials() method
- `stockvaluefinder/stockvaluefinder/external/data_service.py` - Added get_roic_inputs() and get_multi_year_roic_inputs() with 24h cache
- `stockvaluefinder/stockvaluefinder/db/models/roic.py` - ROICResultDB ORM model with all fields
- `stockvaluefinder/stockvaluefinder/db/models/__init__.py` - Registered ROICResultDB import
- `stockvaluefinder/alembic/versions/011_roic_results_table.py` - Migration creating roic_results table
- `stockvaluefinder/stockvaluefinder/repositories/roic_repo.py` - Repository with upsert and query methods

## Decisions Made
- **Lazy import for parallel plan models:** ROICResultCreate and ROICResultUpdate are created by Plan 01 in the same wave. Used try/except import to avoid ModuleNotFoundError during parallel execution, falling back to Any. The import resolves correctly once both plans are merged.
- **Single API call for multi-year data:** fetch_multi_year_financials() calls AKShare once per statement type (profit, balance), returning all reporting periods, then filters in-memory. This avoids N separate API calls and respects the existing rate limiter (0.5s between requests).
- **List caching via _unwrap_cached_value:** get_multi_year_roic_inputs returns a list, which _cache_get_or_set wraps in {"data": [...], "_cache": {...}}. Used _unwrap_cached_value to extract the list on cache hit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lazy import for parallel plan dependency**
- **Found during:** Task 2 (ROICResultRepository creation)
- **Issue:** stockvaluefinder.models.roic does not exist yet -- Plan 01 creates it in the same parallel wave
- **Fix:** Added try/except import block that falls back to Any for ROICResultCreate and ROICResultUpdate
- **Files modified:** stockvaluefinder/stockvaluefinder/repositories/roic_repo.py
- **Verification:** Module imports cleanly with fallback; will resolve correctly when Plan 01 is merged
- **Committed in:** 9e6c638 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for parallel execution. No functional impact -- import resolves once plans merge.

## Issues Encountered
None beyond the parallel plan import issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Data access layer complete, ready for Plan 03 (service layer) to consume
- Plan 03 can use get_roic_inputs() / get_multi_year_roic_inputs() for ROIC calculation
- Plan 03 can use ROICResultRepository for persisting analysis results
- Migration 011 must be applied before using ROICResultRepository in production

---
*Phase: 09-roic-wacc-spread*
*Completed: 2026-05-03*

## Self-Check: PASSED

All files verified: roic.py, 011_roic_results_table.py, roic_repo.py, 09-02-SUMMARY.md
All commits verified: bc5fc8f, 9e6c638
