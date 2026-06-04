---
phase: 28-worker-api-integration
plan: 03
subsystem: api, routes
tags: [rest-api, scanner-endpoints, pagination, auth, watchlist]
dependency_graph:
  requires: [28-02 (paginated repos, API response models)]
  provides: [scanner_routes.py with 6 endpoints, scanner_router registration]
  affects: [main.py, api/scanner_routes.py]
tech_stack:
  added: []
  patterns: [admin-only trigger, paginated list with ApiResponse envelope, watchlist duplicate detection]
key_files:
  created:
    - stockvaluefinder/stockvaluefinder/api/scanner_routes.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_scanner_routes.py
  modified:
    - stockvaluefinder/stockvaluefinder/main.py
decisions:
  - Used getattr(req.app.state, "arq_pool", None) instead of direct attribute access for graceful arq pool unavailability handling
  - Placed get_candidate_by_id lookup on MarketScanRunRepository (from Plan 02) for API route convenience
  - Used Any type hints for ORM-to-Pydantic mapper helper functions to satisfy mypy strict checking
  - Accepted global watchlist (no user_id) for MVP as documented in Phase 28 research Pitfall 3
metrics:
  duration: 6m22s
  completed: 2026-06-05
  tasks_completed: 1
  files_modified: 3
  tests_added: 18
  tests_total: 380
---

# Phase 28 Plan 03: Scanner REST API Endpoints Summary

Created 6 REST API endpoints for the scanner module covering scan triggering, result browsing, candidate inspection, and watchlist integration, all with authentication/authorization and full test coverage.

## What Changed

### scanner_routes.py (NEW)

6 endpoints under `/api/v1/scanner`:

1. **POST /runs** (EXE-03) -- Admin-only scan trigger. Validates scan_type (daily/weekly), gets arq pool from `req.app.state.arq_pool`, enqueues `run_market_scan` job, returns `{job_id, status: "queued"}`. Handles None pool (worker unavailable) and None job (duplicate enqueue).

2. **GET /runs** (EXE-05) -- Authenticated. Paginated scan run list with optional `status` and `scan_type` filters. Returns `ScanRunListResponse` with `PaginationMeta`.

3. **GET /runs/latest/{index_code}` (EXE-05) -- Authenticated. Returns latest run for a given index code. 404 if no runs exist.

4. **GET /runs/{run_id}/candidates** (EXE-06) -- Authenticated. Paginated candidate list with `index_code` filter, `sort_by` whitelist validation (composite_score, safety_margin, created_at), and `sort_order` validation (asc/desc). Maps ORM to `CandidateListItemResponse` extracting `safety_margin`, `intrinsic_value`, `risk_level` from `screening_snapshot` JSONB.

5. **GET /candidates/{candidate_id}` (EXE-07) -- Authenticated. Full candidate detail including complete `screening_snapshot` JSONB. 404 if not found.

6. **POST /candidates/{candidate_id}/watchlist** (EXE-08) -- Authenticated. Looks up candidate, checks `WatchlistRepository.get_by_ticker()` for duplicates. Returns `{ticker, already_exists: true/false}`. Adds to global watchlist if not present.

### main.py (MODIFIED)

Added import and registration of `scanner_router`:
- `from stockvaluefinder.api.scanner_routes import router as scanner_router`
- `app.include_router(scanner_router)`

### test_scanner_routes.py (NEW)

18 tests across 6 test classes:
- `TestTriggerManualScan` (5 tests) -- success enqueue, admin-only check, no arq pool, enqueue returns None, custom params
- `TestListScanRuns` (3 tests) -- paginated list, status filter, empty list
- `TestGetLatestRun` (2 tests) -- found, 404 not found
- `TestListCandidates` (3 tests) -- sorted by composite_score, sorted by safety_margin, invalid sort field
- `TestGetCandidateDetail` (2 tests) -- full detail with snapshot, 404 not found
- `TestAddToWatchlist` (3 tests) -- new addition, duplicate detection, candidate not found

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastAPI rejects `Request | None = None` as route parameter**
- **Found during:** Test execution (conftest import triggers route registration)
- **Issue:** FastAPI interprets `req: Request | None = None` as a response field type, causing `FastAPIError: Invalid args for response field`. The `Request` type with a None default confuses FastAPI's parameter resolution.
- **Fix:** Changed to `req: Request` (no default, no None) and used `getattr(req.app.state, "arq_pool", None)` for safe attribute access. FastAPI injects the Request object automatically via its special parameter handling.
- **Files modified:** `stockvaluefinder/api/scanner_routes.py`
- **Commit:** ca52ba4

**2. [Rule 1 - Bug] mypy strict mode rejects `object` type annotations on ORM attribute access**
- **Found during:** mypy verification
- **Issue:** Helper functions `_map_run_to_response(run: object)` and `_map_candidate_to_list_item(candidate: object)` caused 19 mypy errors because `object` type does not have `.run_id`, `.ticker` etc. attributes.
- **Fix:** Changed parameter types from `object` to `Any`, which is the established pattern in this codebase for ORM-to-Pydantic mappers where the actual type is the SQLAlchemy ORM model.
- **Files modified:** `stockvaluefinder/api/scanner_routes.py`
- **Commit:** ca52ba4

## Threat Mitigations

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-28-07 | require_admin dependency on POST /runs enforces admin role | Implemented |
| T-28-08 | arq unique prevents duplicate enqueue; graceful None handling | Implemented |
| T-28-09 | Generic error messages in ApiResponse; detailed errors logged server-side | Implemented |
| T-28-10 | sort_by whitelist validated by repository (composite_score, safety_margin, created_at) | Implemented |
| T-28-11 | All authenticated users can see all scan data (accepted MVP limitation) | Accepted |
| T-28-12 | UUID validation via Pydantic; candidate existence check before watchlist add | Implemented |

## Verification Results

- Tests: 380 passed (18 new + 362 existing market scanner tests)
- ruff check: All checks passed
- mypy: Success, no issues found
- scanner_router registered in main.py: 2 occurrences (import + include_router)

## Self-Check: PASSED

All 3 files (scanner_routes.py, main.py, test_scanner_routes.py) exist on disk. Commit ca52ba4 found in git log. All tests pass.
