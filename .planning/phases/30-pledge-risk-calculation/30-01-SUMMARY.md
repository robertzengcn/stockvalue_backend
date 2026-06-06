---
phase: 30-pledge-risk-calculation
plan: 01
subsystem: pledge-risk
tags: [risk-grading, tdd, pure-functions, pydantic]
dependency_graph:
  requires: [Phase 29 - EquityPledgeSnapshot, EquityPledgeDetail, DataFreshness]
  provides: [PledgeRiskResult, PledgeRiskAnalyzer, 7 grading functions]
  affects: [stockvaluefinder/models/equity_pledge.py, stockvaluefinder/services/pledge_risk_service.py]
tech_stack:
  added: []
  patterns: [threshold-grading, frozen-pydantic-models, stateless-analyzer-class]
key_files:
  created:
    - stockvaluefinder/stockvaluefinder/services/pledge_risk_service.py
    - stockvaluefinder/tests/unit/test_services/test_pledge_risk_service.py
  modified:
    - stockvaluefinder/stockvaluefinder/models/equity_pledge.py
decisions:
  - Closeout margin boundary: exactly 30% maps to LOW+note (>=30 threshold), exactly 20% maps to MEDIUM (>=20 threshold)
  - Red flags collected from risk object notes rather than local variables to handle None-controlling-holder path
  - Merge logic stubbed in analyzer (returns max of pledge/financial levels) -- full combination rules in Plan 02
metrics:
  duration: 9min
  completed: 2026-06-06
  tasks: 2
  tests: 80
  coverage: 100%
---

# Phase 30 Plan 01: Pledge Risk Grading Pure Functions Summary

Pledge risk result models (6 frozen Pydantic models) and 7 pure grading functions with PledgeRiskAnalyzer class implementing threshold-based risk grading for company pledge ratio, controlling shareholder ratio, and closeout safety margin across RISK-01 through RISK-09.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Define pledge risk result models | d630363 | equity_pledge.py, test_pledge_risk_service.py |
| 2 | Implement pure grading functions and PledgeRiskAnalyzer | 64cb4c9 | pledge_risk_service.py, test_pledge_risk_service.py |

## Key Implementation Details

### Models Added to equity_pledge.py

- `PledgeRiskGrade` -- base grading result with risk_level and notes
- `CompanyPledgeRisk` -- RISK-01 company pledge ratio grading result
- `HolderPledgeRisk` -- RISK-02 controlling shareholder risk result
- `CloseoutRisk` -- RISK-03 closeout safety margin risk result
- `RiskLevelBreakdown` -- RISK-05 merge breakdown (financial vs pledge)
- `PledgeRiskResult` -- complete analysis result consumed by Phase 31

All models use `frozen=True` following existing risk.py pattern.

### Pure Functions in pledge_risk_service.py

| Function | Requirement | Purpose |
|----------|-------------|---------|
| `determine_company_pledge_risk` | RISK-01 | Grade company ratio: <10% LOW, 10-20% LOW+note, 20-30% MEDIUM, >30% HIGH |
| `determine_holder_pledge_risk` | RISK-02 | Grade holder ratio: <30% LOW, 30-50% LOW+note, 50-80% MEDIUM, >80% HIGH |
| `calculate_closeout_safety_margin` | RISK-03 | Formula: (price - closeout) / closeout * 100 |
| `determine_closeout_risk` | RISK-03 | Grade margin: >50% LOW, 30-50% LOW+note, 20-30% MEDIUM, <20% HIGH |
| `determine_data_freshness` | RISK-07 | CURRENT if <=10 days, STALE if >10 days, UNAVAILABLE if None |
| `find_controlling_holder` | RISK-08 | Find highest pledged_to_holding_ratio with first-in-list tie-breaking |
| `is_hk_ticker` | RISK-09 | Simple .endswith(".HK") check |

### PledgeRiskAnalyzer.analyze()

Orchestrates all grading dimensions. Handles:
- HK tickers: returns `supported=False` with UNAVAILABLE data quality
- None snapshot: grades all dimensions as LOW with data-unavailable notes
- Zero-pledge: returns LOW holder risk with no controlling holder identified (D-07)
- Controlling holder: uses find_controlling_holder for holder grading and closeout margin
- Risk merge: stubbed as max(pledge, financial) -- combination upgrade rules deferred to Plan 02

## Test Coverage

- 80 tests across 8 test classes
- Parametrized threshold boundary tests for RISK-01, RISK-02, RISK-03
- None handling verified for every grading function
- Tie-breaking test for find_controlling_holder (D-06)
- Zero-pledge test returning LOW with no holder (D-07)
- HK ticker returns supported=False with no calculations (RISK-09)
- Data freshness boundary at 10/11 days (RISK-07)
- 100% coverage on pledge_risk_service.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed closeout risk threshold boundary**
- **Found during:** Task 2 test execution
- **Issue:** margin=30.0 was incorrectly graded as MEDIUM because the `>30` comparison excluded the exact boundary
- **Fix:** Changed to `>=30` so that exactly 30% falls in the 30-50% LOW+note range
- **Files modified:** pledge_risk_service.py
- **Commit:** 64cb4c9

**2. [Rule 1 - Bug] Fixed UnboundLocalError in PledgeRiskAnalyzer.analyze()**
- **Found during:** Task 2 test execution (test_analyzer_none_snapshot)
- **Issue:** `holder_notes` and `closeout_notes` local variables were only defined inside the `if controlling is not None` branch but referenced unconditionally in red_flags construction
- **Fix:** Changed red_flags to collect from `company_risk.notes`, `holder_risk.notes`, `closeout_risk.notes` (the risk objects) instead of local variables
- **Files modified:** pledge_risk_service.py
- **Commit:** 64cb4c9

## TDD Gate Compliance

- RED gate: test(30-01) commit `d630363` contains failing model tests before implementation
- GREEN gate: feat(30-01) commit `64cb4c9` contains passing implementation and grading function tests
- Both gates present and in correct order

## Known Stubs

- `PledgeRiskAnalyzer.analyze()` merge logic uses simple `max(pledge, financial)` without combination upgrade rules (RISK-04 rules 1-5). Plan 02 will implement the 5 combination upgrade functions and full merge logic with audit trail.

## Threat Flags

No new threat surface introduced. All functions are pure with no I/O, no external calls, and no network access.

## Self-Check: PASSED

- FOUND: stockvaluefinder/stockvaluefinder/services/pledge_risk_service.py
- FOUND: stockvaluefinder/tests/unit/test_services/test_pledge_risk_service.py
- FOUND: .planning/phases/30-pledge-risk-calculation/30-01-SUMMARY.md
- FOUND: commit d630363 (Task 1: models and model tests)
- FOUND: commit 64cb4c9 (Task 2: grading functions and analyzer)
