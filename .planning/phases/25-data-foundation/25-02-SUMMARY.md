---
phase: 25-data-foundation
plan: 02
subsystem: database
tags: [sqlalchemy, pydantic, async, repository, upsert, state-machine, jsonb]

# Dependency graph
requires:
  - phase: 25-01
    provides: "ORM models (IndexConstituentDB, MarketScanRunDB, MarketScanCandidateDB), Pydantic models (Create/Update), enums (ScanStatus, ScanType)"
provides:
  - "IndexConstituentRepository with upsert, get_active, deactivate_missing (IDX-01, IDX-02)"
  - "MarketScanRunRepository with state machine: create_run, mark_running, mark_completed, mark_partial_failed (EXE-04)"
  - "MarketScanCandidateRepository with get_by_run_id, get_passed_candidates, get_by_ticker_run"
  - "26 unit tests covering all repository methods with AsyncMock sessions"
affects: [26-screening-engine, 27-scanner-orchestration, 28-scanner-api]

# Tech tracking
tech-stack:
  added: []
  patterns: [repository-upsert-by-composite-key, bulk-update-deactivate, jsonb-path-exists-query, state-machine-validation]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/repositories/index_constituent_repo.py
    - stockvaluefinder/stockvaluefinder/repositories/market_scan_repo.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_repositories.py
  modified:
    - stockvaluefinder/stockvaluefinder/repositories/__init__.py

key-decisions:
  - "Combined TDD RED+GREEN into single commits due to pre-commit mypy hook requiring type-complete code (same as 25-01)"
  - "Used func.jsonb_path_exists for get_latest_run JSONB array contains query instead of cast/op approach for cleaner SQLAlchemy integration"
  - "Used type: ignore for result.rowcount since mypy cannot resolve CursorResult attribute on async Result wrapper"

patterns-established:
  - "deactivate_missing: bulk SQLAlchemy update() for efficient multi-row status change with rowcount return"
  - "State machine repositories: validate current state before transition, raise ValueError on invalid transitions"
  - "create_run pattern: convert ScanType enum to string value, convert index_codes tuple to list for JSONB"

requirements-completed: [IDX-01, IDX-02, EXE-04]

# Metrics
duration: 5min
completed: 2026-06-04
---

# Phase 25 Plan 02: Data Foundation Summary

**IndexConstituentRepository with upsert-by-composite-key and deactivate_missing for constituent history, MarketScanRunRepository with pending->running->completed/partial_failed state machine, MarketScanCandidateRepository with filtered queries, and 26 passing tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-04T05:02:36Z
- **Completed:** 2026-06-04T05:07:31Z
- **Tasks:** 2
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments
- IndexConstituentRepository with 6 domain methods: get_active_by_index, get_by_ticker, get_constituent_history, upsert_constituent, bulk_upsert_constituents, deactivate_missing
- deactivate_missing uses bulk SQLAlchemy update() for efficient multi-row status change (IDX-02)
- upsert_constituent implements IDX-01 by recording effective_date from data source
- MarketScanRunRepository with full state machine: create_run (pending), mark_running, mark_completed, mark_partial_failed (EXE-04)
- State transitions validate current status before allowing changes, preventing invalid state jumps
- MarketScanCandidateRepository with get_by_run_id, get_passed_candidates, get_by_ticker_run for future API layers
- All 3 repositories registered in __init__.py with proper exports
- 26 unit tests (12 constituent + 10 run + 4 candidate) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: IndexConstituentRepository with sync and history tracking** - `99fa52e` (feat)
2. **Task 2: MarketScanRunRepository, MarketScanCandidateRepository, and tests** - `2aeb2cf` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/repositories/index_constituent_repo.py` - IndexConstituentRepository with upsert, sync, history tracking
- `stockvaluefinder/stockvaluefinder/repositories/market_scan_repo.py` - MarketScanRunRepository + MarketScanCandidateRepository
- `stockvaluefinder/stockvaluefinder/repositories/__init__.py` - Added exports for all 3 new repositories
- `stockvaluefinder/tests/unit/test_market_scanner/test_repositories.py` - 26 unit tests with AsyncMock sessions

## Decisions Made
- **Combined TDD RED+GREEN commits**: Pre-commit mypy hook requires type-complete code, making separate RED commits (with failing imports) impossible. Same approach as 25-01.
- **JSONB query approach for get_latest_run**: Used `func.jsonb_path_exists` with a JSONPath expression instead of `cast/op` approach for cleaner SQLAlchemy integration with PostgreSQL JSONB arrays.
- **type: ignore for rowcount**: Mypy cannot resolve `rowcount` attribute on the async `Result` wrapper type, so added `# type: ignore[attr-defined]` annotation rather than adding a cast.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed unused imports flagged by ruff**
- **Found during:** Task 1 and Task 2 (pre-commit ruff check)
- **Issue:** Unused imports: `typing.Any` in index_constituent_repo.py, `cast` and `String` imports in market_scan_repo.py, `ScanStatus` in test file
- **Fix:** Removed all unused imports
- **Files modified:** index_constituent_repo.py, market_scan_repo.py, test_repositories.py
- **Verification:** ruff check passes
- **Committed in:** 99fa52e and 2aeb2cf

**2. [Rule 3 - Blocking] Fixed mypy rowcount type error**
- **Found during:** Task 1 (mypy check)
- **Issue:** mypy error `"Result[Any]" has no attribute "rowcount"` on deactivate_missing return
- **Fix:** Added `# type: ignore[attr-defined]` annotation since rowcount exists on CursorResult at runtime
- **Files modified:** index_constituent_repo.py
- **Verification:** mypy passes
- **Committed in:** 99fa52e

**3. [Rule 3 - Blocking] Fixed unused test variable assignments**
- **Found during:** Task 2 (pre-commit ruff check)
- **Issue:** F841 errors for `result =` assignments in test methods that only assert on session mock calls
- **Fix:** Changed to `await repo.method(data)` without assignment
- **Files modified:** test_repositories.py
- **Verification:** ruff check passes
- **Committed in:** 2aeb2cf

---

**Total deviations:** 3 auto-fixed (3 blocking issues)
**Impact on plan:** All auto-fixes were lint/type compatibility adjustments. No scope creep.

## TDD Gate Compliance

**Note:** This plan has `type: tdd` in frontmatter, requiring RED/GREEN/REFACTOR gate commits. Due to the pre-commit mypy hook requiring type-complete code, separate RED commits (with failing imports) are not possible. Both test and implementation are committed together in a single GREEN commit per task (same approach as 25-01).

- RED gate: Tests were written to cover all specified behaviors before implementation logic was finalized
- GREEN gate: Implementation written to pass all tests, verified with 26 passing tests
- REFACTOR gate: ruff format applied by pre-commit hooks; no additional refactoring needed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Repository layer complete: 3 repositories ready for service layer consumption (Phase 27)
- IndexConstituentRepository provides sync operations for the AKShare data fetcher
- MarketScanRunRepository provides lifecycle management for scan orchestration
- MarketScanCandidateRepository provides query methods for the API layer
- Full test suite (109 tests) passes: 83 from 25-01 + 26 from 25-02

---
*Phase: 25-data-foundation*
*Completed: 2026-06-04*
