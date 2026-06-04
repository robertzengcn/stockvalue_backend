---
phase: 28-worker-api-integration
plan: 02
subsystem: repositories, models
tags: [pagination, api-response-models, repository, pydantic]
dependency_graph:
  requires: [25-02 (market_scan_repo, market_scanner models)]
  provides: [list_runs_paginated, list_candidates_paginated, get_candidate_by_id, ScanRunResponse, CandidateDetailResponse]
  affects: [market_scan_repo.py, market_scanner.py]
tech_stack:
  added: []
  patterns: [whitelist-validated sort_by, limit-capped pagination, JSONB text() sorting]
key_files:
  created: []
  modified:
    - stockvaluefinder/stockvaluefinder/repositories/market_scan_repo.py
    - stockvaluefinder/stockvaluefinder/models/market_scanner.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_repositories.py
decisions:
  - Used sqlalchemy asc()/desc() functions instead of column method .desc()/.asc() to support text() clauses for JSONB sorting
  - Placed get_candidate_by_id on MarketScanRunRepository as specified in plan for API route convenience
  - Added sort_by whitelist validation (composite_score, safety_margin, created_at) to mitigate T-28-04 tampering threat
metrics:
  duration: 6m30s
  completed: 2026-06-05
  tasks_completed: 1
  files_modified: 3
  tests_added: 18
  tests_total: 43
---

# Phase 28 Plan 02: Paginated Repository Methods & API Response Models Summary

Added paginated query methods to existing market scan repositories and created Pydantic API response models for the scanner REST endpoints (Plan 03).

## What Changed

### Repository Methods (market_scan_repo.py)

**MarketScanRunRepository** received two new methods:

1. `list_runs_paginated(page, limit, status, scan_type)` - Paginated listing with optional status and scan_type filters, ordered by created_at descending. Returns `(list[MarketScanRunDB], total_count)`.

2. `get_candidate_by_id(candidate_id)` - Single candidate retrieval by UUID. Returns `MarketScanCandidateDB | None`. Placed on the run repository for API route convenience as specified in the plan.

**MarketScanCandidateRepository** received one new method:

3. `list_candidates_paginated(run_id, page, limit, index_code, sort_by, sort_order)` - Paginated candidate listing filtered to passed candidates only, with dynamic sorting. Supports sorting by `composite_score` (dedicated column), `safety_margin` (JSONB extraction via `text()`), and `created_at`. Sort field validated against a whitelist to prevent injection. Limit capped at 100.

### API Response Pydantic Models (market_scanner.py)

Added 5 frozen Pydantic models for scanner REST endpoint responses:

- `ScanRunResponse` - Single scan run summary for API output
- `ScanRunListResponse` - Paginated list with `PaginationMeta`
- `CandidateListItemResponse` - Candidate summary with extracted snapshot fields (safety_margin, intrinsic_value, risk_level)
- `CandidateListResponse` - Paginated candidate list with `PaginationMeta`
- `CandidateDetailResponse` - Full candidate detail including complete `screening_snapshot` JSONB

### Tests (test_repositories.py)

Added 18 new tests across 4 test classes:
- `TestMarketScanRunRepositoryPagination` (6 tests) - default pagination, status filter, scan_type filter, combined filters, ordering, limit cap
- `TestMarketScanCandidateRepositoryPagination` (6 tests) - default pagination, index_code filter, safety_margin JSONB sort, invalid sort rejection, asc order, limit cap
- `TestMarketScanCandidateRepositoryGetById` (2 tests) - found and not-found cases
- `TestApiResponseModels` (3 tests) - ScanRunResponse serialization, CandidateListItemResponse serialization, CandidateDetailResponse with full snapshot

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] text() clause does not support .desc()/.asc() methods**
- **Found during:** Test execution (test_list_candidates_paginated_sort_by_safety_margin)
- **Issue:** `sqlalchemy.text()` returns a `TextClause` object which has no `.desc()` or `.asc()` methods. The plan specified `text("CAST(...)")` for JSONB sorting but assumed it would work with `.desc()`.
- **Fix:** Changed from `sort_col.desc()` / `sort_col.asc()` to `sqlalchemy.desc(sort_col)` / `sqlalchemy.asc(sort_col)` which are standalone functions that work with any SQL expression including `TextClause`.
- **Files modified:** `stockvaluefinder/repositories/market_scan_repo.py`
- **Commit:** 78b2e3f

## Threat Mitigations

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-28-04 | sort_by whitelist validation against {"composite_score", "safety_margin", "created_at"} | Implemented |
| T-28-06 | Pagination limit capped at min(limit, 100) | Implemented |

## Verification Results

- Tests: 43 passed, 0 failed (18 new + 25 existing)
- ruff check: All checks passed
- mypy: Success, no issues found in 2 source files

## Self-Check: PASSED

All 3 modified files exist on disk. Commit 78b2e3f found in git log. SUMMARY.md created.
