---
phase: 10-capital-allocation-scorecard
plan: 02
subsystem: data-access
tags: [akshare, stock_repurchase_em, buyback-data, capex, redis-cache, orm, alembic, repository]

# Dependency graph
requires:
  - phase: 10-capital-allocation-scorecard
    plan: 01
    provides: Pure calculation functions and domain models from capex_service.py and capital_allocation.py
provides:
  - AKShareClient.get_repurchase_data() for full A-share buyback dataset
  - ExternalDataService.get_buyback_data() with 24h Redis cache and ticker filtering
  - ExternalDataService.get_multi_year_capex() extracting CONSTRUCT_LONG_ASSET from cash flow
  - CapitalAllocationScoreDB ORM model for scorecard persistence
  - Alembic migration 012 creating capital_allocation_scores table
  - CapitalAllocationRepository with upsert_by_ticker_year and get_latest_for_ticker
affects: [10-03-capex-routes]

# Tech tracking
tech-stack:
  added: []
  patterns: [full-dataset-cache-then-filter, buyback-program-selection-by-status, capex-field-fallback-chain, upsert-by-ticker-year]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/db/models/capital_allocation.py
    - stockvaluefinder/stockvaluefinder/repositories/capital_allocation_repo.py
    - stockvaluefinder/alembic/versions/012_capital_allocation_scores_table.py
    - stockvaluefinder/tests/unit/test_external/test_data_service_capex.py
  modified:
    - stockvaluefinder/stockvaluefinder/external/akshare_client.py
    - stockvaluefinder/stockvaluefinder/external/data_service.py
    - stockvaluefinder/stockvaluefinder/models/capital_allocation.py
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py

key-decisions:
  - "Buyback data fetched as full dataset (5088 rows), cached 24h, filtered by ticker in memory per D-01"
  - "Most recent completed buyback program selected; in-progress used as fallback with INCOMPLETE quality flag per Pitfall 1"
  - "CapEx extracted from CONSTRUCT_LONG_ASSET field with fallback to Chinese field names, NaN normalized to 0.0"
  - "Cache key buyback_full_dataset does NOT include ticker (single cache for all tickers)"

requirements-completed: [CAPEX-01, CAPEX-03]

# Metrics
duration: 14min
completed: 2026-05-06
---

# Phase 10 Plan 02: Capital Allocation Data Access Layer Summary

**Buyback data fetch with Redis 24h cache, multi-year CapEx extraction from cash flow statements, ORM model with JSONB fields, Alembic migration 012, and repository with upsert-by-ticker-year pattern**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-05T22:30:45Z
- **Completed:** 2026-05-05T22:44:41Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- AKShareClient extended with get_repurchase_data() wrapping stock_repurchase_em()
- ExternalDataService extended with get_buyback_data() (full-dataset cache, ticker filter, completed-program selection) and get_multi_year_capex() (CONSTRUCT_LONG_ASSET extraction with NaN handling)
- CapitalAllocationScoreDB ORM model with 3 JSONB dimension fields, weighting, and audit_trail
- Alembic migration 012 creating capital_allocation_scores table with unique constraint on (ticker, fiscal_year)
- CapitalAllocationRepository with upsert_by_ticker_year and get_latest_for_ticker
- 13 unit tests for data service extensions, all passing with ruff and mypy clean
- 104 total Phase 10 tests passing (51 capex_service + 40 models + 13 data service)

## Task Commits

Each task was committed atomically:

1. **Task 1: Buyback fetch and CapEx data service methods** - `0606969` (feat)
2. **Task 2: ORM model, Alembic migration, repository** - `3450d13` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` - Added get_repurchase_data() method
- `stockvaluefinder/stockvaluefinder/external/data_service.py` - Added get_buyback_data() and get_multi_year_capex() methods
- `stockvaluefinder/stockvaluefinder/db/models/capital_allocation.py` - NEW: CapitalAllocationScoreDB ORM model
- `stockvaluefinder/stockvaluefinder/db/models/__init__.py` - Added CapitalAllocationScoreDB import and export
- `stockvaluefinder/stockvaluefinder/repositories/capital_allocation_repo.py` - NEW: CapitalAllocationRepository with upsert and latest methods
- `stockvaluefinder/stockvaluefinder/models/capital_allocation.py` - Added CapitalAllocationScoreUpdate Pydantic model
- `stockvaluefinder/alembic/versions/012_capital_allocation_scores_table.py` - NEW: Migration creating capital_allocation_scores table
- `stockvaluefinder/tests/unit/test_external/test_data_service_capex.py` - NEW: 13 unit tests for data service extensions

## Decisions Made
- Full buyback dataset cached at data_service level with key "buyback_full_dataset" (not per-ticker) per D-01
- Most recent completed program selected for buyback data; in-progress as fallback with INCOMPLETE flag per Pitfall 1
- CapEx field fallback chain: CONSTRUCT_LONG_ASSET > Chinese field name > capital expenditure aliases
- NaN values normalized to None for buyback amounts, 0.0 for CapEx per RESEARCH.md Pitfall 3
- CapitalAllocationScoreUpdate uses optional fields for partial updates (only overall_grade and audit_trail)
- Migration 012 uses down_revision "011" matching existing migration chain

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness
- Data access layer ready for Plan 10-03 (API route wiring)
- All data methods follow existing caching patterns from Phase 9
- ORM model and repository ready for route-level persistence
- Alembic migration chain intact (011 -> 012)

---
*Phase: 10-Capital Allocation Scorecard*
*Completed: 2026-05-06*

## Self-Check: PASSED

All created files verified: 6 FOUND, 0 MISSING
All commits verified: 0606969 (Task 1), 3450d13 (Task 2)
