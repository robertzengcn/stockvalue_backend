---
phase: 10-capital-allocation-scorecard
plan: 03
subsystem: api
tags: [fastapi, api-endpoint, capital-allocation, scorecard, roic-integration, dividend-stability, buyback-yield]

# Dependency graph
requires:
  - phase: 10-capital-allocation-scorecard
    plan: 01
    provides: Pure calculation functions from capex_service.py and domain models from capital_allocation.py
  - phase: 10-capital-allocation-scorecard
    plan: 02
    provides: Data access layer (get_buyback_data, get_multi_year_capex, CapitalAllocationRepository, ROICResultRepository)
  - phase: 09-roic-wacc-spread
    provides: ROIC-WACC spread results in database for blind expansion detection
provides:
  - POST /api/v1/analyze/capex endpoint returning ApiResponse[CapitalAllocationResult]
  - Three-dimension capital allocation scorecard orchestration (buyback, dividend, expansion)
  - DB-first dividend data with AKShare fallback
  - Phase 9 ROIC integration for blind expansion alerts
  - Scorecard persistence via CapitalAllocationRepository.upsert_by_ticker_year
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [route-orchestration, db-first-with-akshare-fallback, roic-cross-phase-query, market-cap-from-price-shares]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/api/capex_routes.py
  modified:
    - stockvaluefinder/stockvaluefinder/main.py

key-decisions:
  - "Market cap computed from get_current_price * get_shares_outstanding (gracefully falls back to None on failure)"
  - "Dividend data DB-first via DividendRepository.get_by_ticker(), AKShare fallback when fewer than 3 years of DB data"
  - "Buyback grade passed as None to combined score only when data_quality is NO_DATA (no programs at all), not when yield is 0"
  - "CapEx data extracted as capex_data[0] (current) and capex_data[1] (previous) from sorted-descending list"

requirements-completed: [CAPEX-01, CAPEX-02, CAPEX-03, CAPEX-04]

# Metrics
duration: 3min
completed: 2026-05-06
---

# Phase 10 Plan 03: Capital Allocation Scorecard API Summary

**POST /api/v1/analyze/capex endpoint orchestrating buyback yield (AKShare cached data + market cap), dividend stability (DB-first DPU trend with AKShare fallback), and expansion discipline (Phase 9 ROIC + multi-year CapEx) into combined A/B/C/D scorecard with persistence**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-05T22:47:58Z
- **Completed:** 2026-05-06T22:50:58Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- POST /api/v1/analyze/capex endpoint with full three-dimension orchestration
- Buyback yield dimension: fetches buyback data from AKShare via data_service, computes market cap from price * shares
- Dividend stability dimension: DB-first via DividendRepository, AKShare fallback for insufficient data, scipy linregress classification
- Expansion discipline dimension: queries Phase 9 ROIC results from database, multi-year CapEx for YoY comparison
- Combined scorecard with equal-weight A/B/C/D grading and missing-dimension reweighting
- Results persisted via CapitalAllocationRepository.upsert_by_ticker_year
- Router registered in main.py alongside existing routes
- All 104 Phase 10 tests passing, ruff clean, mypy clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Create capex_routes.py and register in main.py** - `1af60ee` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/api/capex_routes.py` - NEW: POST /api/v1/analyze/capex endpoint with three-dimension orchestration, error handling matching roic_routes pattern, persistence
- `stockvaluefinder/stockvaluefinder/main.py` - Added capex_router import and app.include_router(capex_router) after roic_router

## Decisions Made
- Market cap computed from get_current_price * get_shares_outstanding with graceful None fallback on failure
- Dividend data DB-first via DividendRepository.get_by_ticker() with AKShare fallback when fewer than 3 years of DB data
- Buyback grade passed as None to combined score only when data_quality is NO_DATA (no programs at all), not when yield is 0
- CapEx year mapping: capex_data sorted descending, index 0 = current year, index 1 = previous year
- Error handling matches roic_routes.py pattern: DataValidationError, ExternalAPIError, generic Exception with structured responses
- Dividend DPU values grouped by fiscal_year with sum of dividend_per_share per year (handles multiple dividends per year)

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness
- Capital allocation scorecard API fully functional and accessible at POST /api/v1/analyze/capex
- All three dimensions wired: buyback yield, dividend stability, expansion discipline
- Cross-phase integration with Phase 9 ROIC results working
- Persistence layer connected for scorecard results
- Endpoint ready for integration testing and frontend consumption

---
*Phase: 10-Capital Allocation Scorecard*
*Completed: 2026-05-06*

## Self-Check: PASSED

All created files verified: 1 FOUND, 0 MISSING
All commits verified: 1af60ee (Task 1)
Router registration in main.py verified: FOUND
