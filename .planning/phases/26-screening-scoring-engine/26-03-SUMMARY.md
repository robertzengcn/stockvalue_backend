---
phase: 26-screening-scoring-engine
plan: 03
subsystem: screening
tags: [pure-functions, deterministic-templates, compliance-enforcement, no-llm, reason-generation]

# Dependency graph
requires:
  - phase: 26-01
    provides: "CandidateReasons, CompositeScore, CompositeScoreComponents models"
  - phase: 26-02
    provides: "Composite scorer outputs consumed by reason generator"
provides:
  - "reason_generator.py: generate_reasons() with 4 domain-specific helpers for deterministic reason and risk flag generation"
  - "30 new tests covering all 19 planned scenarios plus edge cases"
affects: [27-scanner-orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns: [deterministic-template-reason-generation, compliance-fallback-risk-flag, domain-specific-helper-functions]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/market_scanner/reason_generator.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_reason_generator.py
  modified: []

key-decisions:
  - "Combined TDD RED+GREEN commits due to pre-commit mypy hook requiring type-complete code"
  - "Added edge case tests beyond the 19 planned scenarios (negative margin, zero margin, zero yield gap, moderate risk, moderate composite, red flag truncation, combined scenarios)"

patterns-established:
  - "reason_generator.py: Pure-function module with generate_reasons() dispatching to 4 domain helpers that append to shared lists"
  - "Compliance enforcement via both CandidateReasons model validation (min_length=1) and fallback generic flag"

requirements-completed: [SCR-06]

# Metrics
duration: 3min
completed: 2026-06-04
---

# Phase 26 Plan 03: Deterministic Reason Generator Summary

**Deterministic reason generator producing structured selection reasons and risk flags from computed metrics using template-based generation with actual values -- no LLM involvement, compliance-enforced with always >= 1 risk flag, 30 tests passing (248 total in market_scanner)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-04T10:23:22Z
- **Completed:** 2026-06-04T10:27:16Z
- **Tasks:** 1
- **Files modified:** 2 (2 created, 0 modified)

## Accomplishments
- reason_generator.py with generate_reasons() public function and 4 domain-specific helper functions: _generate_valuation_reasons, _generate_risk_reasons, _generate_yield_reasons, _generate_composite_reasons
- Valuation reasons: safety margin above/below/zero/negative thresholds with actual percentage values
- Risk reasons/flags: risk level (HIGH/CRITICAL/MEDIUM/LOW) with M-Score values, red flag aggregation (max 3), profit-cash divergence, excessive goodwill, cun-dai-shuang-gao, Piotroski F-Score (high/low)
- Yield reasons/flags: positive/negative/zero yield gap with actual percentage values
- Composite reasons: strong (>=70) and moderate (>=50) ranking with actual score values
- Compliance enforcement: CandidateReasons model validates min_length=1 on risk_flags AND fallback generic flag when no specific risks found
- Zero LLM imports -- purely deterministic template-based text generation with actual metric values
- 30 new tests covering all 19 planned scenarios plus edge cases (negative margin, zero margin, zero yield gap, moderate risk, moderate composite, red flag truncation, combined multi-domain scenarios)
- 248 total market_scanner tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Deterministic reason generator with compliance enforcement** - `c3a4428` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/market_scanner/reason_generator.py` - generate_reasons() with 4 domain helpers, pure-function module (created)
- `stockvaluefinder/tests/unit/test_market_scanner/test_reason_generator.py` - 30 tests covering all reason/flag generation rules (created)

## Decisions Made
- **Combined TDD RED+GREEN commits:** Pre-commit mypy hook requires type-complete code, making separate RED commits with failing imports impossible. Both test and implementation committed together per Phase 25/26 precedent.
- **Extended test coverage beyond plan:** Added 11 additional tests beyond the 19 planned scenarios covering edge cases (negative/zero margin of safety, zero yield gap, moderate risk level, missing RiskScore, moderate composite score, red flag truncation, combined multi-domain scenarios).

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

**Note:** Due to the pre-commit mypy hook requiring type-complete code, separate RED commits (with failing imports) are not possible. Both test and implementation are committed together in a single GREEN commit per task.

- GREEN gate (Task 1): 30 reason generator tests pass, 248 total market_scanner tests pass
- REFACTOR gate: Code formatted by ruff, no additional refactoring needed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- reason_generator.py complete and ready for Phase 27 (scan orchestration)
- Phase 27 will orchestrate coarse_screener + composite_scorer + reason_generator to produce MarketScanCandidateDB records
- All 3 Phase 26 modules (coarse_screener.py, composite_scorer.py, reason_generator.py) are complete with 248 tests total

---
*Phase: 26-screening-scoring-engine*
*Completed: 2026-06-04*

## Self-Check: PASSED

- reason_generator.py verified present
- test_reason_generator.py verified present
- 26-03-SUMMARY.md verified present
- Commit c3a4428 verified in git log
- 30 tests in test_reason_generator.py
- 248 total tests passing in test_market_scanner/
- ruff check: All checks passed
- mypy: Success: no issues found in 6 source files
- LLM imports in reason_generator.py: 0 (verified)
