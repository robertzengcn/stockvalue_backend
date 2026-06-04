---
phase: 10-capital-allocation-scorecard
plan: 01
subsystem: api
tags: [scipy, linregress, capital-allocation, scorecard, pydantic, frozen-dataclass]

# Dependency graph
requires:
  - phase: 09-roic-wacc-spread
    provides: ROIC-WACC spread data for blind expansion detection (ROIC < WACC check)
provides:
  - Pure calculation functions for buyback yield, dividend stability, expansion discipline, and combined scorecard
  - Capital allocation domain models (Pydantic) with frozen config
  - CapitalAllocationConfig frozen dataclass with all thresholds
affects: [10-02-capex-data-wiring, 10-03-capex-routes]

# Tech tracking
tech-stack:
  added: [scipy>=1.17.1, scipy-stubs>=1.17.0]
  patterns: [scipy-linregress-for-dpu-trend, abs-for-negative-capex, equal-weight-scorecard, missing-dimension-reweight]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/services/capex_service.py
    - stockvaluefinder/stockvaluefinder/models/capital_allocation.py
    - stockvaluefinder/tests/unit/test_services/test_capex_service.py
    - stockvaluefinder/tests/unit/test_models/test_capital_allocation_models.py
  modified:
    - stockvaluefinder/stockvaluefinder/config.py
    - stockvaluefinder/pyproject.toml

key-decisions:
  - "Used strict > threshold for CapEx growth (20% exactly does NOT trigger alert)"
  - "DPU slope threshold 0.05 per year for GROWTH/DECLINE classification"
  - "Missing buyback data reweights remaining dimensions to 50/50 instead of grade D"
  - "Expansion discipline: insufficient data = neutral grade C, not B"

patterns-established:
  - "scipy linregress with ordinal x-axis positions (reused from Phase 9 analyze_roic_trend)"
  - "abs() for CapEx values before computing growth ratio (cash flow outflow convention)"
  - "Grade-to-numeric mapping (A=4,B=3,C=2,D=1) with threshold-based reverse mapping"

requirements-completed: [CAPEX-01, CAPEX-02, CAPEX-03, CAPEX-04]

# Metrics
duration: 10min
completed: 2026-05-06
---

# Phase 10 Plan 01: Capital Allocation Calculation Engine Summary

**Pure calculation engine for capital allocation scorecard: buyback yield grading, DPU trend via scipy linregress, blind expansion detection, and combined A/B/C/D scorecard with equal-weight averaging and missing-dimension reweighting**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-05T22:13:44Z
- **Completed:** 2026-05-06T22:24:01Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Seven pure calculation functions in capex_service.py with full type hints and docstrings
- Eight Pydantic domain models with frozen configuration for capital allocation
- CapitalAllocationConfig frozen dataclass with all threshold constants
- 91 tests (51 service + 40 model) all passing with ruff and mypy clean
- 100% test coverage on capex_service.py and capital_allocation.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Domain models and config** - `6a5c62f` (feat)
2. **Task 2: capex_service pure functions** - `f113fd4` (feat)

_Note: TDD RED/GREEN gates were executed in-memory (write tests, verify fail, implement, verify pass) before committing each task atomically._

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/services/capex_service.py` - 7 pure functions: calculate_buyback_yield, grade_buyback_yield, classify_dividend_stability, grade_dividend_stability, detect_blind_expansion, grade_expansion_discipline, calculate_capital_allocation_score
- `stockvaluefinder/stockvaluefinder/models/capital_allocation.py` - 8 Pydantic models: CapitalAllocationGrade, DividendTrend, BuybackYieldResult, DividendStabilityResult, ExpansionDisciplineResult, CapitalAllocationRequest, CapitalAllocationResult, CapitalAllocationScoreCreate
- `stockvaluefinder/stockvaluefinder/config.py` - Added CapitalAllocationConfig frozen dataclass and capital_allocation field to AppConfig
- `stockvaluefinder/tests/unit/test_services/test_capex_service.py` - 51 unit tests for all pure functions
- `stockvaluefinder/tests/unit/test_models/test_capital_allocation_models.py` - 40 unit tests for models and config
- `stockvaluefinder/pyproject.toml` - Added scipy>=1.17.1 and scipy-stubs>=1.17.0

## Decisions Made
- CapEx growth threshold uses strict > (not >=): 20% exactly does NOT trigger blind expansion alert
- DPU trend threshold of 0.05 per year (absolute slope) classifies growth vs decline
- Missing buyback data reweights remaining two dimensions to 50/50 (per RESEARCH.md anti-pattern 5)
- Expansion discipline with insufficient data grades neutral C, not generous B
- classify_dividend_stability accepts list[float | None] to handle real-world data with gaps

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed scipy and scipy-stubs dependencies**
- **Found during:** Task 2 (capex_service tests)
- **Issue:** scipy not in worktree pyproject.toml; linregress import failed
- **Fix:** Added scipy>=1.17.1 and scipy-stubs>=1.17.0 via uv add
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** All 51 tests pass, mypy clean

**2. [Rule 1 - Bug] Fixed HK ticker test pattern mismatch**
- **Found during:** Task 1 (model tests)
- **Issue:** Test used "00700.HK" (5 digits) but pattern requires 6 digits
- **Fix:** Changed test to use "007000.HK" to match project ticker convention
- **Files modified:** test_capital_allocation_models.py
- **Verification:** All 40 model tests pass

---

**Total deviations:** 2 auto-fixed (1 blocking dependency, 1 test bug)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## TDD Gate Compliance

The plan has type: tdd requiring RED/GREEN/REFACTOR gate commits. Due to pre-commit hooks requiring mypy/ruff clean code, tests and implementation were committed together per task. The TDD cycle was executed in-memory:

- RED: Tests written first, verified to fail with ImportError before implementation
- GREEN: Implementation written to pass all tests, verified with pytest
- REFACTOR: Code formatted by ruff-format during pre-commit

Missing separate test(...) commits is a minor deviation from strict TDD gate format, but the RED/GREEN cycle was honored in execution.

## Next Phase Readiness
- Pure calculation engine ready for Plan 10-02 (data service wiring: buyback data fetch, DPU retrieval, CapEx multi-year)
- All exported function signatures stable, downstream plans can import directly
- CapitalAllocationConfig thresholds tunable without code changes

---
*Phase: 10-capital-allocation-scorecard*
*Completed: 2026-05-06*
