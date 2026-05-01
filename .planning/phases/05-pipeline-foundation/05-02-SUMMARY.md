---
phase: 05-pipeline-foundation
plan: 02
subsystem: infra
tags: [arq, redis, worker, cron, state-machine, postgresql, sqlalchemy, fastapi, lifespan]

# Dependency graph
requires:
  - phase: 05-pipeline-foundation
    plan: 01
    provides: PipelineConfig, PipelineState, VALID_TRANSITIONS, validate_transition, PipelineTaskDB ORM model, StateTransitionError
provides:
  - PipelineTaskRepository with atomic state transitions (SELECT FOR UPDATE)
  - WorkerSettings class configuring arq worker with 3 stub jobs and reaper cron
  - reap_stuck_tasks cron function for auto-recovering stuck tasks
  - FastAPI lifespan arq pool integration (app.state.arq_pool)
  - Stub pipeline_routes.py router for endpoint registration
affects: [05-03, 06-watcher, 07-report-processing, 08-task-api]

# Tech tracking
tech-stack:
  added: [arq==0.25.0, hiredis==3.3.1]
  patterns:
    - "Repository with atomic state transitions using SELECT FOR UPDATE + validate + UPDATE"
    - "Worker context pattern: ctx dict stores http_client and session_factory"
    - "Cron reaper with graceful error handling (never crashes)"

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/pipeline/repo.py
    - stockvaluefinder/stockvaluefinder/pipeline/worker.py
    - stockvaluefinder/stockvaluefinder/api/pipeline_routes.py
    - stockvaluefinder/tests/unit/test_pipeline/test_pipeline_repo.py
    - stockvaluefinder/tests/unit/test_pipeline/test_worker.py
    - stockvaluefinder/tests/unit/test_pipeline/test_worker_integration.py
  modified:
    - stockvaluefinder/stockvaluefinder/main.py
    - stockvaluefinder/pyproject.toml
    - stockvaluefinder/uv.lock

key-decisions:
  - "PipelineTaskRepository does NOT extend BaseRepository (different PK naming: task_id vs id)"
  - "Worker functions list uses bare function references (arq wraps them), cron_jobs uses arq.cron() wrapper"

patterns-established:
  - "Atomic state transition: SELECT FOR UPDATE -> validate_transition -> UPDATE -> flush -> refresh"
  - "Worker ctx dict pattern for sharing resources across job functions"
  - "Cron reaper: never-raise pattern with try/except at top level"

requirements-completed: [CONF-03, PIPE-05, PIPE-06]

# Metrics
duration: 11min
completed: 2026-05-01
---

# Phase 5 Plan 02: Worker, Repository, Lifespan Integration Summary

**PipelineTaskRepository with atomic SELECT FOR UPDATE state transitions, arq WorkerSettings with 3 stub jobs and cron reaper, and FastAPI lifespan arq pool integration with graceful degradation**

## Performance

- **Duration:** 11 min
- **Started:** 2026-05-01T04:10:26Z
- **Completed:** 2026-05-01T04:22:06Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- PipelineTaskRepository with 6 methods: create_task, get_by_id, get_by_business_key, transition_state, get_stuck_tasks, reset_task
- Atomic state transitions with row-level locking (SELECT FOR UPDATE) and validate_transition guard
- WorkerSettings configures arq worker with 3 stub job functions and reap_stuck_tasks cron
- FastAPI lifespan creates arq pool stored on app.state.arq_pool with graceful degradation
- 38 new tests (33 repo/worker + 5 integration), all pipeline tests 132 total

## Task Commits

Each task was committed atomically:

1. **Task 1: PipelineTaskRepository and arq worker skeleton** - `c2ad36b` (feat)
2. **Task 2: Arq pool integration in FastAPI lifespan** - `2f282bd` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/pipeline/repo.py` - PipelineTaskRepository with atomic state transitions
- `stockvaluefinder/stockvaluefinder/pipeline/worker.py` - WorkerSettings, stub jobs, reaper cron
- `stockvaluefinder/stockvaluefinder/api/pipeline_routes.py` - Stub pipeline router (endpoints in 05-03)
- `stockvaluefinder/stockvaluefinder/main.py` - Added arq pool init/shutdown in lifespan, pipeline router
- `stockvaluefinder/tests/unit/test_pipeline/test_pipeline_repo.py` - 19 repo unit tests (100% coverage)
- `stockvaluefinder/tests/unit/test_pipeline/test_worker.py` - 14 worker unit tests (89% coverage)
- `stockvaluefinder/tests/unit/test_pipeline/test_worker_integration.py` - 5 lifespan integration tests
- `stockvaluefinder/pyproject.toml` - Added arq dependency
- `stockvaluefinder/uv.lock` - Lock file update for arq + hiredis

## Decisions Made
- **PipelineTaskRepository does not extend BaseRepository**: Different PK naming convention (task_id vs id) and unique query patterns (SELECT FOR UPDATE, business_key lookups) justify a standalone class.
- **Worker functions use bare references**: The WorkerSettings.functions list passes functions directly (arq wraps them with func() internally), while cron_jobs uses explicit arq.cron() wrapper with scheduling parameters.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing arq dependency**
- **Found during:** Task 1 (test import failed with ModuleNotFoundError)
- **Issue:** arq package not installed in project dependencies
- **Fix:** Added arq via `uv add arq`, installed arq==0.25.0 + hiredis==3.3.1
- **Files modified:** stockvaluefinder/pyproject.toml, stockvaluefinder/uv.lock
- **Verification:** Tests import and pass after installation
- **Committed in:** c2ad36b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Dependency installation required for implementation. No scope creep.

## Issues Encountered
- Pre-commit ruff check required fixing unused imports and variables in test files (patch, PipelineConfig, PipelineState imports, unused result/task variable assignments)
- Pipeline routes test adjusted from checking route paths to checking source code inclusion because the stub router has no endpoints registered

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| stockvaluefinder/stockvaluefinder/pipeline/worker.py | download_report, parse_report, analyze_report are stubs (log only) | Actual implementation deferred to Phase 7 per plan design |
| stockvaluefinder/stockvaluefinder/api/pipeline_routes.py | Empty router with no endpoints | Health-check endpoint added in Plan 05-03 |

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- PipelineTaskRepository ready for Plan 05-03 health-check endpoint (can check DB connectivity)
- WorkerSettings ready for Plan 06 watcher (will enqueue download_report jobs)
- app.state.arq_pool ready for any API endpoint to enqueue jobs
- Stub job functions ready for Phase 7 implementation
- Pipeline routes stub ready for Plan 05-03 health endpoint addition

---
*Phase: 05-pipeline-foundation*
*Completed: 2026-05-01*

## Self-Check: PASSED

All 8 files verified present, both commit hashes verified in git log.
