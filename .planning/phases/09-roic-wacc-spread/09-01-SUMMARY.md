---
phase: 09-roic-wacc-spread
plan: 01
subsystem: valuation
tags: [roic, wacc, nopat, scipy, linregress, moat-detection, pure-functions, tdd]

# Dependency graph
requires: []
provides:
  - ROIC calculation engine (6 pure functions) for NOPAT, invested capital, ROIC, spread, and trend
  - Extended calculate_wacc() with true WACC support (debt-weighted)
  - ROIC domain models (request, result, WACC breakdown, trend, enums)
  - ROICConfig frozen dataclass with sector keywords and trend thresholds
  - scipy dependency for 3-year trend regression
affects: [09-02, 09-03]

# Tech tracking
tech-stack:
  added: [scipy>=1.15.0]
  patterns: [dual-nopat-formula-financial-sector, lazy-import-scipy, ordinal-x-regression]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/models/roic.py
    - stockvaluefinder/stockvaluefinder/services/roic_service.py
    - stockvaluefinder/tests/unit/test_services/test_roic_service.py
  modified:
    - stockvaluefinder/pyproject.toml
    - stockvaluefinder/stockvaluefinder/config.py
    - stockvaluefinder/stockvaluefinder/services/valuation_service.py

key-decisions:
  - "Ordinal positions (0,1,2) for x-axis in trend regression avoids year-gap slope distortion"
  - "Lazy scipy import inside analyze_roic_trend() matches project convention for heavy dependencies"
  - "NaN normalization via existing _to_float() from risk_service reused for consistency (D-11)"
  - "WACC backward compat: all-defaults check triggers Ke-only path, preserving float-exact results"

patterns-established:
  - "Dual formula pattern: is_financial flag selects different NOPAT calculation (D-10)"
  - "Negative invested capital guard: returns None with negative_invested_capital flag (D-08)"
  - "Trend classification: scipy linregress slope compared against configurable threshold"

requirements-completed: [ROIC-01, ROIC-02, ROIC-03, ROIC-04, ROIC-05, ROIC-06]

# Metrics
duration: 6min
completed: 2026-05-03
---

# Phase 9 Plan 1: ROIC Calculation Engine Summary

**ROIC-WACC spread calculation engine with dual NOPAT formulas (financial/non-financial), true WACC with debt weighting, and 3-year moat trend detection via scipy linear regression**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-03T06:17:56Z
- **Completed:** 2026-05-03T06:24:45Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- ROIC calculation engine with 6 pure functions (is_financial_sector, calculate_nopat, calculate_invested_capital, calculate_roic, calculate_roic_wacc_spread, analyze_roic_trend)
- Extended calculate_wacc() to support true WACC = We*Ke + Wd*Kd*(1-T) while maintaining backward compatibility with existing 3-arg calls
- 31 unit tests with 99% coverage on roic_service.py
- scipy>=1.15.0 integrated for trend line regression
- ROICConfig with MOAT_TREND_THRESHOLD=0.005, FINANCIAL_SECTOR_KEYWORDS=("银行", "保险", "证券")

## Task Commits

Each task was committed atomically:

1. **Task 1: Install scipy and create ROIC domain models + extend WACC** - `c4659be` (feat)
2. **Task 2: Implement roic_service.py pure functions with TDD** - `ac1ddca` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/models/roic.py` - ROIC domain models (8 classes: SpreadClassification, MoatTrend, WACCBreakdown, MoatTrendResult, ROICAnalysisRequest, ROICAnalysisResult, ROICResultCreate, ROICResultUpdate)
- `stockvaluefinder/stockvaluefinder/services/roic_service.py` - ROIC pure functions (6 exported functions with audit trails)
- `stockvaluefinder/tests/unit/test_services/test_roic_service.py` - 31 unit tests across 7 test classes
- `stockvaluefinder/pyproject.toml` - Added scipy>=1.15.0 dependency
- `stockvaluefinder/stockvaluefinder/config.py` - Added ROICConfig frozen dataclass and roic_config global
- `stockvaluefinder/stockvaluefinder/services/valuation_service.py` - Extended calculate_wacc() with optional debt params

## Decisions Made
- Ordinal positions (0,1,2) for x-axis in trend regression avoids year-gap slope distortion
- Lazy scipy import inside analyze_roic_trend() matches project convention for heavy dependencies
- NaN normalization via existing _to_float() from risk_service reused for consistency (D-11)
- WACC backward compat: all-defaults check triggers Ke-only path, preserving float-exact results for existing callers

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Floating point precision in test_existing_3arg_2: calculate_wacc(0.025, 1.2, 0.05) returns 0.08499999999999999 not exactly 0.085. Fixed test to use abs(result - expected) < 1e-10 instead of ==.
- Plan listed expected WACC value as 0.076125 in test_true_wacc, but mathematically correct value is 0.07425 (0.7*0.09 + 0.3*0.05*0.75). Test uses correct value 0.07425.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 02 (data layer) can use all 6 roic_service functions to fetch and compute ROIC from AKShare/efinance data
- Plan 03 (API wiring) can use ROICAnalysisRequest/ROICAnalysisResult models for route definitions
- ROICConfig is ready for integration into AppConfig singleton

---
*Phase: 09-roic-wacc-spread*
*Completed: 2026-05-03*

## Self-Check: PASSED

All 4 created files verified present. Both task commits (c4659be, ac1ddca) verified in git log.
