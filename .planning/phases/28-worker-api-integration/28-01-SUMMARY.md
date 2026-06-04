---
phase: 28-worker-api-integration
plan: 01
subsystem: market_scanner
tags: [arq-worker, cron-jobs, daily-scan, weekly-scan, concurrent-prevention]
dependency_graph:
  requires:
    - phase: 27-market-scanner-service
      provides: ScanOrchestrator
    - phase: 25-data-foundation
      provides: MarketScanRunRepository, MarketScanCandidateRepository, IndexConstituentRepository
  provides:
    - ScannerWorkerSettings arq worker class
    - run_market_scan job function
    - daily_light_scan cron function
    - weekly_deep_scan cron function
    - _build_orchestrator helper
  affects: []
tech_stack:
  added: []
  patterns: [arq-cron-worker, concurrent-scan-prevention, per-invocation-orchestrator]
key_files:
  created:
    - stockvaluefinder/stockvaluefinder/market_scanner/worker.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_worker.py
  modified: []
decisions:
  - "Combined RED+GREEN commit per Phase 25-27 precedent (pre-commit mypy requires type-complete code)"
  - "ScanOrchestrator created per-invocation with fresh session instead of shared instance"
  - "ScannerWorkerSettings as separate class from existing WorkerSettings (independent scaling)"
  - "Invalid scan_type returns failed status dict instead of raising exception (graceful arq handling)"
  - "dataclasses.replace used for top_n config override (immutable pattern per coding conventions)"
metrics:
  duration_seconds: 225
  completed_date: 2026-06-05
  task_count: 1
  file_count: 2
  test_count: 11
requirements-completed: [EXE-01, EXE-02]
---

# Phase 28 Plan 01: Scanner Worker with Daily/Weekly Cron Jobs Summary

ScannerWorkerSettings arq worker class with daily (09:30 UTC weekdays) and weekly (Sat 02:00 UTC) cron jobs wrapping ScanOrchestrator.run_scan() with concurrent scan prevention via get_latest_run() status check.

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-04T22:14:13Z
- **Completed:** 2026-06-04T22:17:58Z
- **Tasks:** 1
- **Files created:** 2

## Accomplishments

- ScannerWorkerSettings class with cron_jobs defining daily (09:30 UTC weekdays, 30-min timeout) and weekly (Sat 02:00 UTC, 60-min timeout) scheduled scans
- run_market_scan job function accepting index_codes, scan_type, and top_n parameters for both cron and manual enqueue
- daily_light_scan delegates to run_market_scan with scan_type="daily"
- weekly_deep_scan delegates to run_market_scan with scan_type="weekly"
- Concurrent scan prevention: checks MarketScanRunRepository.get_latest_run() status before each scan, skipping "running" or "pending" runs
- _build_orchestrator helper creates ScanOrchestrator with ExternalDataService (initialized), repositories, and BatchDataFetcher per-invocation
- Invalid scan_type parameter returns {"status": "failed", "error": "..."} gracefully
- top_n override applied via dataclasses.replace on MarketScannerConfig (immutable pattern)
- redis_settings from get_arq_redis_settings() for arq Redis connection
- 11 unit tests covering all cron functions, concurrent prevention scenarios, custom parameters, error handling, and settings validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Scanner worker with daily/weekly cron jobs and run_market_scan function** - `dfb2626` (feat)

## Files Created/Modified

- `stockvaluefinder/stockvaluefinder/market_scanner/worker.py` - ScannerWorkerSettings class, run_market_scan job function, daily_light_scan/weekly_deep_scan cron functions, _build_orchestrator helper
- `stockvaluefinder/tests/unit/test_market_scanner/test_worker.py` - 11 unit tests in 4 test classes

## Decisions Made

- Combined RED+GREEN commit per Phase 25-27 precedent (pre-commit mypy requires type-complete code)
- ScanOrchestrator created per-invocation with fresh database session to prevent stale connections and ensure clean state
- ScannerWorkerSettings as separate class from existing pipeline WorkerSettings, allowing independent worker scaling
- Invalid scan_type returns failed status dict instead of raising exception, letting arq handle the job completion gracefully
- dataclasses.replace used for top_n config override following project's immutable dataclass pattern

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

Combined RED+GREEN commit per Phase 25-27 established precedent for single-task TDD plans. Test file and implementation file created together and verified in a single commit:
- test commit: included in feat commit (combined)
- feat commit: `dfb2626` - all 11 tests pass

## Verification Results

- Tests: 11 passed, 0 failed
- ruff check: All checks passed
- mypy: Success, no issues found in 1 source file

## Self-Check: PASSED

- FOUND: stockvaluefinder/stockvaluefinder/market_scanner/worker.py
- FOUND: stockvaluefinder/tests/unit/test_market_scanner/test_worker.py
- FOUND: commit dfb2626

---
*Phase: 28-worker-api-integration*
*Completed: 2026-06-05*
