---
phase: 19-l1-formula-verification
plan: 01
subsystem: testing
tags: [pytest, l1-formula, risk-service, m-score, f-score, beneish, piotroski]

# Dependency graph
requires:
  - phase: 17
    provides: validation module (Tolerance, compare_within_tolerance)
provides:
  - L1 formula verification tests for risk_service (52 tests)
  - l1_formula pytest marker registration
affects: [19-02, 23-01, CI]

# Tech tracking
tech-stack:
  added: []
  patterns: [l1_formula marker for CI gating, compare_within_tolerance for tolerance-based assertions]

key-files:
  created:
    - stockvaluefinder/tests/unit/test_services/test_l1_risk_service.py
  modified:
    - stockvaluefinder/pytest.ini

key-decisions:
  - "Used alias import (detect_cundai_shuanggao) for Chinese-named function detect_存贷双高 to avoid source encoding issues"
  - "Used formula-derived M-Score -1.509 instead of registry value -2.22 (registry value is incorrect for the given sub-index inputs)"

patterns-established:
  - "L1 test pattern: @pytest.mark.l1_formula class decorator, compare_within_tolerance for float assertions, direct equality for integers"
  - "Paper reference in docstrings (Beneish 1999, Piotroski 2000) for audit trail"

requirements-completed: [LV1-01, LV1-02, LV1-04, LV1-05]

# Metrics
duration: 5min
completed: 2026-05-21
---

# Phase 19 Plan 01: L1 Formula Verification for risk_service Summary

**52 L1 formula verification tests for risk_service: M-Score 8 sub-indices + composite, F-Score 9 binary components, detect_存贷双高, goodwill ratio, profit-cash divergence, and risk level determination**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-21T04:49:30Z
- **Completed:** 2026-05-21T04:54:55Z
- **Tasks:** 1
- **Files modified:** 2 (created 1, modified 1)

## Accomplishments
- M-Score composite tested against Beneish 1999 Table 3 formula-derived value (-1.509 within abs 0.05)
- All 8 M-Score sub-indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) verified with hand-computed inputs
- All 9 F-Score binary components tested at boundary conditions (score 0 and score 1 cases)
- Full F-Score integration: perfect company = 9, worst company = 0
- detect_存贷双高 tested at 1B/50% thresholds including asymmetric OR case
- calculate_goodwill_ratio tested at 30% boundary (inclusive=not excessive, exclusive=excessive)
- detect_profit_cash_divergence tested with profit-grows/OCF-declines scenario
- determine_risk_level tested at -1.78, -2.22 boundaries with red flag upgrades

## Task Commits

Each task was committed atomically:

1. **Task 1: Create L1 tests for M-Score 8 sub-indices, composite M-Score, F-Score, and risk helper functions** - `1680446` (test)

## Files Created/Modified
- `stockvaluefinder/tests/unit/test_services/test_l1_risk_service.py` - 784 lines, 52 L1 formula tests across 7 test classes
- `stockvaluefinder/pytest.ini` - Added `l1_formula` marker registration
- `stockvaluefinder/tests/unit/test_services/test_l1_capex_service.py` - Fixed unused imports blocking pre-commit hook (collateral from untracked file)

## Decisions Made
- Used alias import `detect_cundai_shuanggao` for Chinese-named function `detect_存贷双高` to ensure clean Python source encoding
- Used formula-derived M-Score -1.509 instead of registry value -2.22 (verified formula: -4.84 + 0.92*1.465 + 0.528*1.193 + 0.404*1.254 + 0.892*1.134 + 0.115*0.974 - 0.172*0.685 + 4.679*0.032 - 0.327*0.945 = -1.509)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed unused imports in untracked test_l1_capex_service.py**
- **Found during:** Task 1 (commit stage)
- **Issue:** Pre-commit ruff check failed on untracked test_l1_capex_service.py (grade_dividend_stability, grade_expansion_discipline imported but unused), blocking commit
- **Fix:** Removed unused imports from the pre-existing untracked file
- **Files modified:** stockvaluefinder/tests/unit/test_services/test_l1_capex_service.py
- **Verification:** Pre-commit hooks pass (mypy, ruff check, ruff format)
- **Committed in:** 1680446 (part of task commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal - only fixed a pre-existing linting issue in an unrelated untracked file to unblock the commit hook.

## Issues Encountered
- Initial test run had 6 NameError failures for `detect_存贷双高` because the import was missing from the import block. Fixed by adding the import with an ASCII alias.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- L1 formula tests for risk_service are complete and passing (52/52)
- l1_formula marker registered and discoverable via `pytest -m l1_formula`
- Ready for Plan 19-02: L1 tests for remaining services (roic, valuation, yield, capex, policy, alpha)

---
*Phase: 19-l1-formula-verification*
*Completed: 2026-05-21*

## Self-Check: PASSED

- FOUND: stockvaluefinder/tests/unit/test_services/test_l1_risk_service.py
- FOUND: .planning/phases/19-l1-formula-verification/19-01-SUMMARY.md
- FOUND: commit 1680446
- Test file: 816 lines (plan minimum: 200)
- All 52 tests passing, no external dependencies
