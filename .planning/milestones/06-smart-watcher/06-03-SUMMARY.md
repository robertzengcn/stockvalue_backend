---
phase: 06-smart-watcher
plan: 03
subsystem: pipeline/watcher
tags: [pipeline, watchlist, rest-api, fastapi, crud, tdd]

# Dependency graph
requires:
  - phase: 06-smart-watcher
    plan: 01
    provides: WatchlistItemCreate, WatchlistItemResponse Pydantic models, WatchlistDB ORM model
  - phase: 06-smart-watcher
    plan: 02
    provides: WatchlistRepository with add, remove, get_all, get_by_ticker methods
provides:
  - POST /api/v1/pipeline/watchlist endpoint for adding stocks
  - GET /api/v1/pipeline/watchlist endpoint for listing stocks with active_only filter
  - DELETE /api/v1/pipeline/watchlist/{ticker} endpoint for removing stocks
  - All endpoints using ApiResponse[T] envelope matching project convention
affects: [08-task-management]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JSONResponse for HTTP error status codes (400, 404) with ApiResponse envelope body"
    - "response_model=None on FastAPI routes returning mixed response types for mypy compliance"

key-files:
  created:
    - stockvaluefinder/tests/unit/test_pipeline/test_watchlist_api.py
  modified:
    - stockvaluefinder/stockvaluefinder/api/pipeline_routes.py

key-decisions:
  - "JSONResponse wrapping ApiResponse.model_dump() for HTTP 400/404 error responses, since FastAPI does not support Union return types with generic ApiResponse"
  - "response_model=None on POST and DELETE routes to avoid FastAPI response model validation on Union types"

patterns-established:
  - "Error status pattern: JSONResponse(status_code=N, content=ApiResponse(success=False, error=...).model_dump())"

requirements-completed: [WATCH-04]

# Metrics
duration: 11min
completed: 2026-05-01
---

# Phase 6 Plan 03: Watchlist API Endpoints Summary

**Three watchlist CRUD endpoints (POST, GET, DELETE) on /api/v1/pipeline/watchlist with ticker regex validation, ApiResponse[T] envelope, and 14 TDD tests covering validation, duplicates, and repository integration**

## Performance

- **Duration:** 11 min
- **Started:** 2026-05-01T15:53:43Z
- **Completed:** 2026-05-01T16:05:05Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- POST /api/v1/pipeline/watchlist adds stock with ticker regex validation and duplicate detection (HTTP 400)
- GET /api/v1/pipeline/watchlist lists stocks with optional active_only query parameter filter
- DELETE /api/v1/pipeline/watchlist/{ticker} soft-removes stock with 404 for missing tickers
- All endpoints use ApiResponse[T] envelope matching project convention
- 14 new unit tests (all passing, 330 total pipeline tests)
- Existing health endpoint verified functional after new endpoints

## Task Commits

Each task was committed atomically (TDD):

1. **RED gate: Failing tests for watchlist CRUD API** - `77a5306` (test)
2. **GREEN gate: Watchlist CRUD endpoints** - `aec870c` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/api/pipeline_routes.py` - Added 3 watchlist endpoints (POST, GET, DELETE) with imports for Depends, Path, Query, JSONResponse, get_db, WatchlistItemCreate, WatchlistItemResponse, WatchlistRepository
- `stockvaluefinder/tests/unit/test_pipeline/test_watchlist_api.py` - New file with 14 tests in 5 test classes covering all endpoint behaviors

## Decisions Made
- **JSONResponse for error status codes:** FastAPI cannot handle Union return types with generic ApiResponse[T]. Used `JSONResponse(status_code=N, content=ApiResponse(...).model_dump())` for HTTP 400 and 404 responses while keeping the ApiResponse envelope format in the body.
- **response_model=None on mixed routes:** Added `response_model=None` decorator parameter to POST and DELETE routes to prevent FastAPI from attempting to validate Union[ApiResponse[T], JSONResponse] as a Pydantic model, which fails at route registration.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- mypy pre-commit hook flagged Union return types as incompatible with the declared return type; resolved with `response_model=None` and `ApiResponse[T] | JSONResponse` return type annotation.
- FastAPI raised FastAPIError when trying to use Union[ApiResponse[T], JSONResponse] as response_model; resolved by adding `response_model=None`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Watchlist API endpoints ready for frontend integration
- All CRUD operations available for user-configured stock monitoring
- Phase 6 (Smart Watcher) complete -- all 3 plans delivered
- Ready for Phase 7 (Pipeline Processing) to consume watchlist for disclosure monitoring

---

*Phase: 06-smart-watcher*
*Completed: 2026-05-01*

## Self-Check: PASSED

All 3 key files verified present. Both commits (77a5306 RED, aec870c GREEN) verified in git log. 330 pipeline tests passing.
