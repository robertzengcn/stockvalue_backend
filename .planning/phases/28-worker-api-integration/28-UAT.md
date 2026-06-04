---
status: complete
phase: 28-worker-api-integration
source: [28-01-SUMMARY.md, 28-02-SUMMARY.md, 28-03-SUMMARY.md]
started: 2026-06-05T23:15:00Z
updated: 2026-06-05T23:25:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Scanner Worker - Daily Cron Job
expected: ScannerWorkerSettings.cron_jobs contains daily_light_scan function scheduled at 09:30 UTC weekdays with 30-minute timeout.
result: pass

### 2. Scanner Worker - Weekly Cron Job
expected: ScannerWorkerSettings.cron_jobs contains weekly_deep_scan function scheduled Sat 02:00 UTC with 60-minute timeout.
result: pass

### 3. Scanner Worker - Concurrent Scan Prevention
expected: run_market_scan checks get_latest_run() status before starting. Skips if running or pending scan exists.
result: pass

### 4. Repository Pagination - list_runs_paginated
expected: Returns (list_of_runs, total_count) with status and scan_type filters. Orders by created_at descending. Limit capped at 100.
result: pass

### 5. Repository Pagination - list_candidates_paginated
expected: Returns (list_of_candidates, total_count) with run_id filter, index_code filter, and dynamic sorting. JSONB safety_margin sort uses text() with sqlalchemy.desc(). Sort field whitelist validated.
result: pass

### 6. Pydantic API Response Models
expected: ScanRunResponse, ScanRunListResponse, CandidateListItemResponse, CandidateListResponse, CandidateDetailResponse all frozen Pydantic models with correct fields.
result: pass

### 7. Scanner REST API - 6 Endpoints
expected: router has 6 routes: POST /runs (admin trigger), GET /runs (list), GET /runs/latest, GET /runs/{id}/candidates, GET /candidates/{id}, POST /candidates/{id}/watchlist.
result: pass

### 8. Scanner REST API - Auth Protection
expected: POST /runs requires admin role via require_admin dependency. All GET endpoints require authenticated user via get_current_user.
result: pass

### 9. Scanner REST API - Watchlist Integration
expected: POST /candidates/{id}/watchlist checks WatchlistRepository for duplicates. Returns already_exists=True for existing, adds new otherwise.
result: pass

### 10. Router Registration in main.py
expected: scanner_router imported and registered in main.py via app.include_router(scanner_router).
result: pass

### 11. All 380 Scanner Tests Pass
expected: 380 tests in test_market_scanner/ covering worker, repositories, routes pass with 29% overall coverage.
result: pass

### 12. ruff and mypy Clean
expected: ruff check and mypy pass on all Phase 28 modules including scanner_routes.py and main.py.
result: pass

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
