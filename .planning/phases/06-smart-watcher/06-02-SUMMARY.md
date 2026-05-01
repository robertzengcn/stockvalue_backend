---
phase: 06-smart-watcher
plan: 02
subsystem: pipeline/watcher
tags: [pipeline, watcher, cron, arq, akshare, cninfo, disclosure-polling, repositories, tdd]

# Dependency graph
requires:
  - phase: 05-pipeline-foundation
    provides: PipelineConfig, PipelineTaskRepository, WorkerSettings, cron pattern
  - phase: 06-smart-watcher
    plan: 01
    provides: WatchlistDB, WatcherStateDB, PendingDisclosureDB ORM models, PendingDisclosureCreate Pydantic model
provides:
  - WatcherService with poll_disclosures and process_disclosures methods
  - WatchlistRepository for watchlist CRUD operations
  - WatcherStateRepository for watcher_state singleton management
  - PendingDisclosureRepository for staging table operations
  - AKShareClient extended with get_report_disclosures, get_cninfo_announcements, get_index_constituents
  - Updated WorkerSettings with watch_disclosures cron and process_disclosures job function
  - Helper functions: get_current_report_periods, normalize_akshare_ticker, build_business_key
affects: [06-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-phase poll-process architecture (poll -> pending_disclosures -> process)"
    - "Season-aware single cron with runtime month check instead of two cron entries"
    - "AKShare NaT filtering on disclosure_date column"
    - "Business key construction as ticker:fiscal_year:report_type for dedup"

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/pipeline/watcher.py
    - stockvaluefinder/stockvaluefinder/pipeline/watchlist_repo.py
    - stockvaluefinder/stockvaluefinder/pipeline/watcher_repo.py
    - stockvaluefinder/stockvaluefinder/pipeline/disclosure_repo.py
    - stockvaluefinder/tests/unit/test_pipeline/test_watcher.py
    - stockvaluefinder/tests/unit/test_pipeline/test_watchlist_repo.py
    - stockvaluefinder/tests/unit/test_pipeline/test_watcher_repo.py
    - stockvaluefinder/tests/unit/test_pipeline/test_disclosure_repo.py
  modified:
    - stockvaluefinder/stockvaluefinder/external/akshare_client.py
    - stockvaluefinder/stockvaluefinder/pipeline/worker.py
    - stockvaluefinder/tests/unit/test_pipeline/test_worker.py

key-decisions:
  - "Two-phase architecture: poll writes to staging table, separate job processes and enqueues (D-11)"
  - "Single daily cron with runtime month check instead of two cron entries (avoids boundary conflicts)"
  - "AKShare NaT filtering done in client method, not in WatcherService (separation of concerns)"
  - "get_current_report_periods returns empty for May, June, September (no active reporting deadlines)"
  - "Amendment detection appends timestamp suffix to business_key for uniqueness"

requirements-completed: [WATCH-01, WATCH-02, WATCH-03, WATCH-05]

# Metrics
duration: 14min
completed: 2026-05-01
---

# Phase 6 Plan 02: Watcher Service and Disclosure Polling Summary

**Built WatcherService with two-phase disclosure polling, 3 new repositories, 3 AKShare client methods, and season-aware cron integration -- replacing manual report discovery with automated A-share financial report monitoring**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-01T15:28:48Z
- **Completed:** 2026-05-01T15:42:54Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- WatcherService with poll_disclosures (AKShare primary + CNInfo fallback) and process_disclosures (new/amendment/skip detection)
- WatchlistRepository with get_active_tickers, add, remove, get_all, get_by_ticker methods
- WatcherStateRepository with get_state (creates if not exists) and update_state (increments counters)
- PendingDisclosureRepository with stage_disclosures (bulk insert), get_unprocessed, mark_processed
- AKShareClient extended with get_report_disclosures (NaT filtering), get_cninfo_announcements, get_index_constituents
- Helper functions: get_current_report_periods (month-based), normalize_akshare_ticker (6xx->.SH, 0xx/3xx->.SZ), build_business_key
- WorkerSettings updated with watch_disclosures cron (daily 09:00, unique, 5min timeout) and process_disclosures job
- on_startup now creates WatcherService instance in worker context
- 72 new unit tests across 4 new test files and 1 updated test file (all 316 pipeline tests passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: AKShare disclosure methods, repositories, and WatcherService** - `ff6a570` (feat)
2. **Task 2: Update WorkerSettings with watch_disclosures cron and process_disclosures job** - `65d33ca` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/pipeline/watcher.py` - WatcherService class, PollResult/ProcessResult dataclasses, helper functions
- `stockvaluefinder/stockvaluefinder/pipeline/watchlist_repo.py` - WatchlistRepository with 5 CRUD methods
- `stockvaluefinder/stockvaluefinder/pipeline/watcher_repo.py` - WatcherStateRepository with singleton state management
- `stockvaluefinder/stockvaluefinder/pipeline/disclosure_repo.py` - PendingDisclosureRepository with staging operations
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` - Added 3 new methods (get_report_disclosures, get_cninfo_announcements, get_index_constituents)
- `stockvaluefinder/stockvaluefinder/pipeline/worker.py` - Added watch_disclosures cron, process_disclosures job, updated on_startup
- `stockvaluefinder/tests/unit/test_pipeline/test_watcher.py` - 48 tests for helpers, AKShare methods, WatcherService
- `stockvaluefinder/tests/unit/test_pipeline/test_watchlist_repo.py` - 10 tests for WatchlistRepository
- `stockvaluefinder/tests/unit/test_pipeline/test_watcher_repo.py` - 4 tests for WatcherStateRepository
- `stockvaluefinder/tests/unit/test_pipeline/test_disclosure_repo.py` - 5 tests for PendingDisclosureRepository
- `stockvaluefinder/tests/unit/test_pipeline/test_worker.py` - 24 tests (8 new for watch_disclosures, 3 new for process_disclosures, updated structure)

## Decisions Made
- **Two-phase architecture (D-11):** Poll cron writes to pending_disclosures staging table. A separate worker job reads and processes. This decouples polling from processing, allowing each to be retried independently.
- **Single cron with runtime check:** Instead of two separate cron entries for high/off season, a single daily cron checks the current month against PipelineConfig.high_season_months at runtime. Simpler and avoids boundary conflicts between two crons.
- **NaT filtering in AKShareClient:** Rows where the actual disclosure date is NaT (not yet disclosed) are filtered out in get_report_disclosures, not in WatcherService. This keeps data filtering at the data source layer.
- **Empty period months:** May, June, and September return empty from get_current_report_periods because no A-share reporting deadlines fall in those months. The watcher will skip polling gracefully.
- **Amendment business_key suffix:** When an amendment is detected (later disclosure_date), the business_key gets an `:amd:{date}` suffix for uniqueness, since the original business_key already exists in pipeline_tasks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] get_current_report_periods included May/June/Sep in semi-annual period**
- **Found during:** Task 1 GREEN phase (test_may_june_return_empty failed)
- **Issue:** Original code used `elif month <= 8` which matched May and June. Plan specifies only Jul-Aug for semi-annual and Oct-Nov for Q3.
- **Fix:** Changed to explicit month sets: `elif month in (7, 8)` for semi-annual, `elif month in (10, 11)` for Q3, `elif month == 12` for annual.
- **Files modified:** stockvaluefinder/stockvaluefinder/pipeline/watcher.py
- **Committed in:** ff6a570 (Task 1 commit)

**2. [Rule 3 - Blocking] Tests needed mocking of get_current_report_periods for poll tests**
- **Found during:** Task 1 GREEN phase (poll test failed because May returns empty periods)
- **Issue:** Tests running in May get empty periods from get_current_report_periods, causing poll_disclosures to return early with staged_count=0.
- **Fix:** Added `patch("stockvaluefinder.pipeline.watcher.get_current_report_periods")` to poll_disclosures tests to return controlled periods regardless of current date.
- **Files modified:** tests/unit/test_pipeline/test_watcher.py
- **Committed in:** ff6a570 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Strengthened period calculation accuracy and test isolation. No scope creep.

## Issues Encountered
- Pre-commit hooks required multiple passes for mypy type annotation fixes (UUID vs uuid4, rowcount attr-defined) and unused import cleanup in test files.
- pandas import in tests required `# type: ignore[import-untyped]` annotation for mypy compliance.

## User Setup Required
None - no external service configuration required. All tests use mocks.

## Next Phase Readiness
- WatcherService ready for Watchlist API endpoints (Plan 06-03)
- process_disclosures ready for download_report integration (Phase 7)
- All repository interfaces stable for Phase 7 consumption
- WorkerSettings fully configured with both cron jobs and job functions

---

*Phase: 06-smart-watcher*
*Completed: 2026-05-01*

## Self-Check: PASSED

All 11 key files verified present. Both commits (ff6a570, 65d33ca) verified in git log. 316 pipeline tests passing.
