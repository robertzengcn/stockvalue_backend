---
phase: 30-pledge-risk-calculation
verified: 2026-06-06T13:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 30: Pledge Risk Calculation Verification Report

**Phase Goal:** System grades equity pledge risk across company ratio, controlling shareholder ratio, and closeout safety margin, applying combination upgrade rules and merging with financial risk.
**Verified:** 2026-06-06T13:00:00Z
**Status:** PASSED
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | System grades company overall pledge risk into LOW/MEDIUM/HIGH based on company pledge ratio thresholds | VERIFIED | `determine_company_pledge_risk()` at line 39 of `pledge_risk_service.py`: <10% LOW, 10-20% LOW+note, 20-30% MEDIUM, >30% HIGH. Parametrized tests in `TestCompanyPledgeRisk` (12 boundary cases) all pass. |
| 2 | System identifies controlling shareholder and grades their pledge risk | VERIFIED | `find_controlling_holder()` at line 217 returns holder with highest `pledged_to_holding_ratio`, first-in-list tie-break (D-06). `determine_holder_pledge_risk()` at line 80: <30% LOW, 30-50% LOW+note, 50-80% MEDIUM, >80% HIGH. Zero-pledge returns None (D-07). Tests in `TestFindControllingHolder` and `TestHolderPledgeRisk` pass. |
| 3 | System calculates closeout safety margin and grades it; HK returns supported=false | VERIFIED | `calculate_closeout_safety_margin()` at line 123: formula `(latest-closeout)/closeout*100`. `determine_closeout_risk()` at line 148: >50% LOW, 30-50% LOW+note, 20-30% MEDIUM, <20% HIGH. `is_hk_ticker()` at line 253 returns `True` for `.HK` suffix; `analyze()` returns `supported=False` with `UNAVAILABLE` freshness and warning. Tests in `TestCloseoutMargin`, `TestHKTicker`, `TestPledgeRiskAnalyzerBasic` pass. |
| 4 | System applies combination upgrade rules and merges pledge risk with financial risk | VERIFIED | 5 separate pure functions: `check_high_pledge_with_price_drop` (line 274), `check_holder_over_80` (line 301), `check_closeout_margin_low` (line 322), `check_high_pledge_with_financial_high` (line 343), `check_high_pledge_with_存贷双高` (line 372). All evaluated with no short-circuit (D-05). `merge_risk_levels()` at line 402 takes max by `_RISK_ORDER`; pledge can only upgrade, never downgrade. `analyze()` orchestration at line 468 calls all 5 rules, determines upgrade level, merges with financial risk. Integration test scenario 3 verifies all 5 rules trigger simultaneously producing 5 combination_upgrades. |
| 5 | System classifies data freshness as CURRENT/STALE/UNAVAILABLE | VERIFIED | `determine_data_freshness()` at line 184: <=10 days CURRENT, >10 days STALE, None UNAVAILABLE. Tests in `TestDataFreshness` verify all boundaries including 10-day boundary and future dates. |

**Score:** 5/5 truths verified

### Deferred Items

No deferred items. All success criteria from ROADMAP.md are met within this phase.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `stockvaluefinder/services/pledge_risk_service.py` | Pure functions for pledge risk grading, combination rules, merge logic, PledgeRiskAnalyzer class | VERIFIED | 666 lines. 13 pure functions + PledgeRiskAnalyzer class. All functions synchronous, no I/O. |
| `stockvaluefinder/models/equity_pledge.py` | Result models: PledgeRiskGrade, CompanyPledgeRisk, HolderPledgeRisk, CloseoutRisk, RiskLevelBreakdown, PledgeRiskResult | VERIFIED | 210 lines. 6 frozen Pydantic models added after existing Phase 29 models. |
| `tests/unit/test_services/test_pledge_risk_service.py` | Unit tests covering RISK-01 through RISK-09 | VERIFIED | 1149 lines. 125 tests across 15 test classes. All pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pledge_risk_service.py` | `equity_pledge.py` | `from stockvaluefinder.models.equity_pledge import ...` | WIRED | Imports 8 models from equity_pledge module |
| `pledge_risk_service.py` | `enums.py` | `from stockvaluefinder.models.enums import DataFreshness, RiskLevel` | WIRED | RiskLevel used in grading, DataFreshness used in freshness classification |
| `PledgeRiskAnalyzer.analyze()` | 5 combination rules | Direct function calls | WIRED | Lines 597-624: all 5 `check_*` functions called sequentially with no short-circuit |
| `PledgeRiskAnalyzer.analyze()` | `merge_risk_levels()` | Direct function call | WIRED | Line 650: merges financial and pledge risk levels |
| `check_high_pledge_with_存贷双高` | `risk_service.py` red flags | Substring match | WIRED | Matches exact flag format at risk_service.py line 750: "存贷双高: High cash and high debt anomaly detected" |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `PledgeRiskAnalyzer.analyze()` | `company_ratio` | `snapshot.company_pledge_ratio` | Percentage from Phase 29 data | FLOWING |
| `PledgeRiskAnalyzer.analyze()` | `holder_ratio` | `controlling.pledged_to_holding_ratio` | Percentage from Phase 29 detail | FLOWING |
| `PledgeRiskAnalyzer.analyze()` | `margin` | `calculate_closeout_safety_margin(latest_price, estimated_closeout_price)` | Computed from holder detail | FLOWING |
| `PledgeRiskAnalyzer.analyze()` | `combination_upgrades` | All 5 `check_*` functions evaluated | Red flag strings with actual values | FLOWING |
| `PledgeRiskAnalyzer.analyze()` | `pledge_risk_level` | `max(company, holder, closeout, upgrade)` | Computed risk level | FLOWING |
| `PledgeRiskAnalyzer.analyze()` | `risk_level_breakdown` | `merge_risk_levels(financial, pledge)` | Merged result | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 125 tests pass | `uv run pytest tests/unit/test_services/test_pledge_risk_service.py -v` | 125 passed, 0 failed | PASS |
| 100% coverage on pledge_risk_service | `--cov=stockvaluefinder.services.pledge_risk_service` | 161 statements, 0 missed, 100% coverage | PASS |

### Probe Execution

Step 7c: SKIPPED -- this phase does not declare or imply probe-based verification. No `scripts/*/tests/probe-*.sh` files exist.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RISK-01 | 30-01 | Company pledge risk grading (LOW/MEDIUM/HIGH) | SATISFIED | `determine_company_pledge_risk()` with parametrized tests at 12 boundary values |
| RISK-02 | 30-01 | Controlling shareholder pledge risk grading | SATISFIED | `determine_holder_pledge_risk()` with parametrized tests at 11 boundary values |
| RISK-03 | 30-01 | Closeout safety margin calculation and grading | SATISFIED | `calculate_closeout_safety_margin()` + `determine_closeout_risk()` with 16 combined tests |
| RISK-04 | 30-02 | 5 combination upgrade rules | SATISFIED | 5 separate pure functions, each with triggered/not-triggered/boundary tests |
| RISK-05 | 30-02 | Risk merge (pledge only upgrades) | SATISFIED | `merge_risk_levels()` with 7 test cases including CRITICAL handling |
| RISK-06 | 30-02 | Red flag generation with actual data values | SATISFIED | `TestRedFlagFormat` verifies Chinese string content with actual percentage values |
| RISK-07 | 30-01 | Data freshness classification | SATISFIED | `determine_data_freshness()` with boundary tests at 10/11 days |
| RISK-08 | 30-01 | Controlling shareholder identification | SATISFIED | `find_controlling_holder()` with tie-break (D-06) and zero-pledge (D-07) tests |
| RISK-09 | 30-01 | HK ticker returns supported=false | SATISFIED | `is_hk_ticker()` + `analyze()` early return with unsupported result |

No orphaned requirements found. All 9 RISK requirements from REQUIREMENTS.md map to this phase and are satisfied.

### Anti-Patterns Found

No anti-patterns detected. No TBD, FIXME, XXX, TODO, HACK, or PLACEHOLDER markers found. No empty implementations or stub return values in any file modified by this phase.

### Locked Decisions Verification

| Decision | Description | Status | Evidence |
|----------|-------------|--------|----------|
| D-01 | PledgeRiskAnalyzer in separate `pledge_risk_service.py` | VERIFIED | File exists at `services/pledge_risk_service.py`, class at line 454 |
| D-02 | Single `analyze()` method returning PledgeRiskResult | VERIFIED | Method signature at line 468, returns PledgeRiskResult |
| D-03 | Result models in `equity_pledge.py` | VERIFIED | 6 models added after existing Phase 29 models (lines 96-210) |
| D-04 | 5 separate pure functions for combination rules | VERIFIED | Lines 274, 301, 322, 343, 372 |
| D-05 | All 5 rules always evaluated (no short-circuit) | VERIFIED | Lines 597-624 in analyze(): all 5 rules called unconditionally |
| D-06 | Tie-breaking by first-in-list order | VERIFIED | Line 242-244: strict `>` comparison preserves first-in-list |
| D-07 | Zero-pledge returns None holder with LOW risk | VERIFIED | Lines 556-563: empty details path produces LOW holder risk |
| D-08 | Red flags as plain Chinese strings with data values | VERIFIED | TestRedFlagFormat verifies exact string content for all 5 rules |

### Human Verification Required

No human verification items identified. All success criteria are pure calculation functions verified by automated tests.

### Gaps Summary

No gaps found. All 5 ROADMAP success criteria are verified against the actual codebase. All 9 RISK requirements are satisfied. All 8 locked decisions are respected. Test coverage is 100% on `pledge_risk_service.py` with 125 tests passing.

---

_Verified: 2026-06-06T13:00:00Z_
_Verifier: Claude (gsd-verifier)_
