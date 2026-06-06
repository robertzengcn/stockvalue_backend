---
phase: 30-pledge-risk-calculation
plan: 02
subsystem: pledge-risk
tags: [combination-rules, merge-logic, red-flags, tdd, orchestration]
dependency_graph:
  requires: [Phase 29 - EquityPledgeSnapshot, EquityPledgeDetail, Phase 30 Plan 01 - grading functions]
  provides: [5 combination upgrade rules, merge_risk_levels, complete PledgeRiskAnalyzer.analyze()]
  affects: [stockvaluefinder/services/pledge_risk_service.py]
tech_stack:
  added: []
  patterns: [combination-upgrade-rules, risk-level-merge, no-short-circuit-evaluation]
key_files:
  created: []
  modified:
    - stockvaluefinder/stockvaluefinder/services/pledge_risk_service.py
    - stockvaluefinder/stockvaluefinder/tests/unit/test_services/test_pledge_risk_service.py
decisions:
  - All 5 combination rules evaluated independently with no short-circuit (D-05)
  - Combination rule upgrade always sets pledge_risk_level to at least HIGH when any rule triggers
  - None snapshot produces pledge_risk_level=None in merge (distinct from zero-pledge LOW)
  - Red flags aggregated from dimension notes + combination rule flags
metrics:
  duration: 11min
  completed: 2026-06-06
  tasks: 2
  tests: 125
  coverage: 100%
---

# Phase 30 Plan 02: Combination Upgrade Rules and Analyzer Orchestration Summary

Five combination upgrade rules (RISK-04), risk level merge logic (RISK-05), red flag generation (RISK-06), and complete PledgeRiskAnalyzer.analyze() orchestration producing full PledgeRiskResult for all scenarios.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement combination upgrade rules and merge logic | 0998c86 | pledge_risk_service.py, test_pledge_risk_service.py |
| 2 | Complete PledgeRiskAnalyzer.analyze() orchestration | c435cf3 | pledge_risk_service.py, test_pledge_risk_service.py |

## Key Implementation Details

### Combination Upgrade Rules (RISK-04)

Five separate pure functions following D-04, each returning `tuple[bool, str | None]`:

| Function | Trigger | Red Flag Format |
|----------|---------|-----------------|
| `check_high_pledge_with_price_drop` | company_pledge >30% AND 1yr drop <-30% | "公司质押比例{ratio}%超30%且近一年跌幅{change}%超30%" |
| `check_holder_over_80` | holder_pledge >80% | "控股股东质押比例{ratio}%超过80%阈值" |
| `check_closeout_margin_low` | safety_margin <20% | "平仓线安全距离{margin}%低于20%阈值" |
| `check_high_pledge_with_financial_high` | company_pledge >20% AND financial HIGH/CRITICAL | "公司质押比例{ratio}%超20%且财务风险为{level}" |
| `check_high_pledge_with_存贷双高` | company_pledge >20% AND "存贷双高" in financial_red_flags | "公司质押比例{ratio}%超20%且存在存贷双高" |

All 5 rules always evaluated (no short-circuit) per D-05, producing a full audit trail.

### Merge Logic (RISK-05)

`merge_risk_levels(financial_risk_level, pledge_risk_level)` uses `_RISK_ORDER` dict to take the higher of two levels. Pledge can only upgrade, never downgrade financial risk. `merge_reason` populated when pledge is higher.

### Complete analyze() Orchestration

PledgeRiskAnalyzer.analyze() implements a 10-step pipeline:
1. HK check -> unsupported result (RISK-09)
2. Data freshness computation (RISK-07)
3. Grade company risk (RISK-01)
4. Find controlling holder (RISK-08)
5. Grade holder risk (RISK-02)
6. Calculate closeout margin and risk (RISK-03)
7. Evaluate all 5 combination rules (RISK-04, D-05)
8. Determine pledge risk level (max of dimensions + upgrade)
9. Merge with financial risk via merge_risk_levels (RISK-05)
10. Collect red flags from notes + combination rules (RISK-06)

### None Snapshot Handling

When snapshot is None (data unavailable), `pledge_risk_level` is set to `None` (not LOW) to signal that pledge risk could not be assessed. This preserves the financial risk level unchanged. Dimension risks still default to LOW with data-unavailable notes for UI display.

## Test Coverage

- 125 tests across 15 test classes
- TestCombinationRule1-5: triggered/not-triggered + boundary tests for each rule
- TestMergeRiskLevels: upgrade, no-upgrade, same-level, None pledge, CRITICAL handling
- TestRedFlagFormat: exact Chinese string content with data values
- TestPledgeRiskAnalyzerIntegration: 6 scenarios covering normal, multiple rules, zero-pledge, HK, data-unavailable
- 100% coverage on pledge_risk_service.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Bug] Fixed test fixture for scenario 1 (closeout margin calculation)**
- **Found during:** Task 2 integration test execution
- **Issue:** Test fixture used latest_price=80, estimated_closeout_price=100 which produces margin=-20%, triggering combination rule 3 unexpectedly
- **Fix:** Changed fixture to latest_price=130, estimated_closeout_price=100 (margin=30%, safe)
- **Files modified:** test_pledge_risk_service.py
- **Commit:** c435cf3

**2. [Rule 2 - Missing] Added None snapshot pledge_risk_level=None handling**
- **Found during:** Task 2 integration test execution
- **Issue:** analyze() computed pledge_risk_level=LOW from None-data dimensions instead of None, which would incorrectly signal "assessed as LOW" rather than "could not assess"
- **Fix:** Added explicit check for `snapshot is None` to set pledge_risk_level=None, skipping dimension aggregation
- **Files modified:** pledge_risk_service.py
- **Commit:** c435cf3

## TDD Gate Compliance

- RED gate: test(30-02) commit `0998c86` contains failing tests for combination rules and merge
- GREEN gate: feat(30-02) commit `c435cf3` contains passing implementation and integration tests
- Both gates present and in correct order

## Known Stubs

None - all planned functionality is fully implemented.

## Threat Flags

No new threat surface introduced. All functions are pure with no I/O, no external calls, and no network access. Rule 5 substring match on financial_red_flags is defensive per T-30-03.

## Self-Check: PASSED

- FOUND: stockvaluefinder/stockvaluefinder/services/pledge_risk_service.py
- FOUND: stockvaluefinder/tests/unit/test_services/test_pledge_risk_service.py
- FOUND: commit 0998c86 (Task 1: combination rules and merge tests)
- FOUND: commit c435cf3 (Task 2: analyze() orchestration and integration tests)
