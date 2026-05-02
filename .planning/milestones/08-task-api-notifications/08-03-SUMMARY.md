---
phase: 08-task-api-notifications
plan: 03
subsystem: services
tags: [subprocess, sandbox, resource-limits, isolation, calculation, RLIMIT_CPU, RLIMIT_AS]

# Dependency graph
requires:
  - phase: 05-pipeline-foundation
    provides: PipelineTaskRepository, PipelineState, PipelineConfig, worker.py
  - phase: 07-report-processing
    provides: Worker functions (download_report, parse_report, analyze_report)
  - phase: 08-task-api-notifications/01
    provides: PipelineConfig sandbox_enabled and sandbox_timeout fields
  - phase: 08-task-api-notifications/02
    provides: _emit_event hooks in worker.py

provides:
  - CalculationSandboxService with subprocess execution and in-process fallback
  - sandbox_runner.py subprocess entry point with resource limits
  - ALLOWED_CALCULATIONS whitelist for calculation_type validation
  - JSON stdin/stdout protocol for subprocess communication
  - Conditional routing in _run_all_analyzers via config.sandbox_enabled

affects: [08-task-api-notifications, 09-future-milestones]

# Tech tracking
tech-stack:
  added: []
  patterns: [subprocess-sandbox, resource-limits, whitelist-validation, conditional-routing]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/services/sandbox_runner.py
    - stockvaluefinder/tests/unit/test_services/test_sandbox.py
    - stockvaluefinder/tests/unit/test_pipeline/test_sandbox_integration.py
  modified:
    - stockvaluefinder/stockvaluefinder/services/calculation_sandbox.py
    - stockvaluefinder/stockvaluefinder/pipeline/worker.py

key-decisions:
  - "Used separate static methods for each in-process calculation type to avoid mypy type narrowing issues with shared variable names"
  - "Added dict isinstance check in result summary to handle both sandbox dicts and Pydantic model results"
  - "Used Any type annotations on coroutine variables to avoid mypy type unification errors across if/else branches"

patterns-established:
  - "Subprocess sandbox: JSON stdin/stdout via subprocess.run, resource.setrlimit inside child"
  - "Whitelist validation: frozenset of allowed calculation types checked before execution"
  - "Conditional routing: config flag gates sandbox vs direct analyzer path"

requirements-completed: [SBOX-01, SBOX-02, SBOX-03, SBOX-04]

# Metrics
duration: 11min
completed: 2026-05-02
---

# Phase 8 Plan 03: Calculation Sandbox Summary

**Subprocess sandbox with RLIMIT_CPU/RLIMIT_AS resource limits and working in-process fallback for financial calculation isolation**

## Performance

- **Duration:** 11 min
- **Started:** 2026-05-02T14:22:31Z
- **Completed:** 2026-05-02T14:33:10Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- CalculationSandboxService replaces the old stub with dual-mode execution: subprocess isolation or in-process direct calls
- sandbox_runner.py subprocess entry point sets RLIMIT_CPU and RLIMIT_AS before importing calculation modules (SBOX-01, SBOX-03)
- JSON stdin/stdout protocol for subprocess communication (SBOX-02)
- ALLOWED_CALCULATIONS frozenset whitelist prevents command injection (T-08-08 mitigation)
- TimeoutExpired and MemoryError caught and returned as CalculationError (SBOX-03)
- Default behavior (sandbox_enabled=False) unchanged -- analyzers called directly in-process (SBOX-04, D-07)
- _run_all_analyzers conditionally routes through sandbox when config.sandbox_enabled=True
- 13 new tests (10 unit + 3 integration) with 421 total pipeline tests passing (no regressions)

## Task Commits

Each task was committed atomically (TDD cycle: RED -> GREEN):

1. **Task 1 (GREEN): CalculationSandboxService + sandbox_runner + tests** - `91dbf92` (feat)
2. **Task 2 (GREEN): Wire sandbox into worker + integration tests** - `a622d2a` (feat)

## Files Created/Modified

- `stockvaluefinder/stockvaluefinder/services/calculation_sandbox.py` - Replaced stub with CalculationSandboxService class (subprocess + in-process fallback)
- `stockvaluefinder/stockvaluefinder/services/sandbox_runner.py` - New subprocess entry point with set_resource_limits() and run_calculation()
- `stockvaluefinder/stockvaluefinder/pipeline/worker.py` - Added sandbox routing in _run_all_analyzers via config.sandbox_enabled flag
- `stockvaluefinder/tests/unit/test_services/test_sandbox.py` - 10 unit tests for sandbox service and runner
- `stockvaluefinder/tests/unit/test_pipeline/test_sandbox_integration.py` - 3 integration tests for sandbox routing in worker

## Decisions Made

- Used separate static methods (_run_m_score, _run_dcf_valuation, _run_yield_gap) in CalculationSandboxService to avoid mypy type narrowing errors when reusing the result variable across elif branches
- Added isinstance(result, dict) check in _run_all_analyzers result summary to handle both sandbox result dicts and direct Pydantic model objects
- Used Any type annotations on coroutine variables (risk_coro, valuation_coro, yield_coro) to avoid mypy type unification errors across if/else branches where sandbox returns dict but direct analyzers return Pydantic models
- sandbox_runner.py uses Market enum conversion for the market parameter to satisfy YieldAnalyzer.analyze() type signature

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type narrowing with shared result variable across elif branches**
- **Found during:** Task 1 (implementation)
- **Issue:** mypy rejected reassignment of result from RiskScore to ValuationResult across elif branches
- **Fix:** Extracted each calculation branch into its own static method with unique variable names
- **Files modified:** stockvaluefinder/services/calculation_sandbox.py, stockvaluefinder/services/sandbox_runner.py
- **Committed in:** 91dbf92

**2. [Rule 3 - Blocking] Fixed test Market enum value case mismatch**
- **Found during:** Task 1 (test execution)
- **Issue:** Test passed "a_share" but Market enum expects "A_SHARE"
- **Fix:** Updated test to use correct uppercase "A_SHARE" value
- **Files modified:** tests/unit/test_services/test_sandbox.py
- **Committed in:** 91dbf92

**3. [Rule 3 - Blocking] Fixed mypy type unification on coroutine variables**
- **Found during:** Task 2 (implementation)
- **Issue:** mypy could not unify Coroutine[Any, Any, dict] with Coroutine[Any, Any, RiskScore] across if/else branches
- **Fix:** Added Any type annotations on risk_coro, valuation_coro, yield_coro variables
- **Files modified:** stockvaluefinder/pipeline/worker.py
- **Committed in:** a622d2a

**4. [Rule 3 - Blocking] Fixed unused imports in integration test**
- **Found during:** Task 2 (pre-commit hook)
- **Issue:** ruff detected unused asyncio and AsyncMock imports
- **Fix:** Removed unused imports
- **Files modified:** tests/unit/test_pipeline/test_sandbox_integration.py
- **Committed in:** a622d2a

---

**Total deviations:** 4 auto-fixed (1 bug, 3 blocking)
**Impact on plan:** All auto-fixes necessary for type safety and lint compliance. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Sandbox subsystem complete and ready for use
- Set sandbox_enabled=True in PipelineConfig to activate subprocess isolation
- Default behavior (sandbox_enabled=False) preserves existing in-process execution
- Phase 8 complete: Task API (08-01), SSE events (08-02), and sandbox (08-03) all delivered

---

*Phase: 08-task-api-notifications*
*Completed: 2026-05-02*

## Self-Check: PASSED

All 5 source files verified present.
All 2 commit hashes verified in git log.
13 new tests passing (10 sandbox unit + 3 integration).
421 total pipeline tests passing (no regressions).
Linting clean (ruff check passes on all modified files).
Type checking clean (mypy passes on all modified files).
