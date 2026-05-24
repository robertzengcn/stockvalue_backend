---
phase: 24-golden-dataset-expansion
plan: 02
subsystem: testing
tags: [golden-dataset, m-score, f-score, roic, nopat, technology, real-estate, non-financial]

# Dependency graph
requires:
  - phase: 24-01
    provides: Generalized compute_golden_values.py with --ticker/--year CLI
provides:
  - Populated expected_metrics.yaml for ZTE (000063.SZ) and Vanke (000002.SZ)
  - Computed provenance.md for ZTE and Vanke with sector-specific notes
  - Non-financial NOPAT branch validation (is_financial=False, TOTAL_PROFIT + FINANCE_EXPENSE)
  - Real-estate sector stress test for NOPAT with large positive FINANCE_EXPENSE
affects: [reconcile-core, golden-test-suite]

# Tech tracking
tech-stack:
  added: []
  patterns: [non-financial NOPAT branch validation, sector-specific provenance annotations]

key-files:
  created: []
  modified:
    - stockvaluefinder/tests/golden/000063.SZ/2023/expected_metrics.yaml
    - stockvaluefinder/tests/golden/000063.SZ/2023/provenance.md
    - stockvaluefinder/tests/golden/000002.SZ/2023/expected_metrics.yaml
    - stockvaluefinder/tests/golden/000002.SZ/2023/provenance.md
    - stockvaluefinder/tests/golden/manifest.yaml

key-decisions:
  - "Kept l3_verified=false for both ZTE and Vanke pending human annual-report cross-verification"
  - "Set source_page to pending_human_review for all 16 populated metrics per stock"
  - "Set verified_by to automated_compute_pending_human_review"
  - "Documented FINANCE_EXPENSE sign convention: ZTE has negative (net finance income), Vanke has positive (interest expense)"

patterns-established:
  - "Two-tier verification pattern consistent with 24-01: automated compute first, then human annual-report cross-check"

requirements-completed: [GOLD-02, GOLD-03, LV3-01, LV3-02]

# Metrics
duration: 6min
completed: 2026-05-23
---

# Phase 24 Plan 02: Golden Dataset Expansion (Non-Financial Stocks) Summary

**Populated ZTE (technology) and Vanke (real estate) golden metrics from frozen AKShare using non-financial NOPAT branch, with sector-specific annotations pending human annual-report cross-verification**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-23T03:29:57Z
- **Completed:** 2026-05-23T03:37:40Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- ZTE (000063.SZ) golden values computed: NOPAT=8.24B, IC=118.1B, ROIC=6.98%, M-Score=-2.6009, F-Score=6
- Vanke (000002.SZ) golden values computed: NOPAT=23.0B, IC=508.2B, ROIC=4.53%, M-Score=-2.2018, F-Score=3
- Non-financial NOPAT branch exercised for both stocks: (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)
- Vanke FINANCE_EXPENSE stress test: large positive 3.71B interest expense from 257.7B interest-bearing debt
- ZTE FINANCE_EXPENSE edge case: negative -1.1B (net finance income, not expense)
- Provenance annotated with sector-specific notes (R&D capitalization for tech, presale revenue and high leverage for real estate)
- All 22 golden tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Compute + annotate ZTE (000063.SZ) golden metrics** - `f6eb437` (feat)
2. **Task 2: Compute + annotate Vanke (000002.SZ) golden metrics** - `c020471` (feat)
3. **Task 3: Update manifest notes, keep l3_verified false, verify golden tests** - `f44f13a` (chore)

## Files Created/Modified
- `stockvaluefinder/tests/golden/000063.SZ/2023/expected_metrics.yaml` - 16 populated metrics from frozen AKShare (technology sector, non-financial)
- `stockvaluefinder/tests/golden/000063.SZ/2023/provenance.md` - Status COMPUTED with tech-sector notes (R&D capitalization, long-cycle contracts, negative FINANCE_EXPENSE)
- `stockvaluefinder/tests/golden/000002.SZ/2023/expected_metrics.yaml` - 16 populated metrics from frozen AKShare (real estate, non-financial)
- `stockvaluefinder/tests/golden/000002.SZ/2023/provenance.md` - Status COMPUTED with real-estate notes (presale revenue, high leverage, large FINANCE_EXPENSE)
- `stockvaluefinder/tests/golden/manifest.yaml` - Updated provenance and notes for ZTE and Vanke

## Decisions Made
- Kept l3_verified=false for both stocks until human cross-verifies against annual report PDFs
- Set source_page to "pending_human_review" for all 16 populated metrics per stock, following the 24-01 pattern
- Set verified_by to "automated_compute_pending_human_review" to distinguish from fully verified stocks
- Documented FINANCE_EXPENSE sign convention difference: ZTE has negative value (net finance income), Vanke has large positive value (interest expense) -- this is the key stress test for the non-financial NOPAT branch

## Deviations from Plan

### Plan Modifications (per important_notes)

**1. Tasks 1 and 2 adapted from manual cross-verification to automated-compute-pending-review**
- **Reason:** Cannot download PDF annual reports as an automated executor
- **Adaptation:** Ran compute_golden_values.py to populate values, set source_page to "pending_human_review", set verified_by to "automated_compute_pending_human_review", set provenance.md status to "COMPUTED (pending human verification)"
- **Impact:** Values are deterministic and correct from frozen AKShare; human needs to cross-verify with annual report PDF and update source_page/verified_date/verified_by

**2. Task 3 modified: manifest NOT flipped to l3_verified: true**
- **Reason:** l3_verified must remain false until human cross-verification is complete
- **Adaptation:** Updated manifest notes and provenance fields only; kept l3_verified=false
- **Impact:** Golden test suite parametrization remains at 1 stock (600519.SH) until human verifies ZTE and Vanke

### Auto-fixed Issues

None - plan executed without unexpected issues.

---

**Total deviations:** 2 plan modifications + 0 auto-fixes
**Impact on plan:** All deviations necessary per important_notes instructions. Human verification step properly deferred.

## Issues Encountered
None - compute_golden_values.py worked correctly for both tickers on first run.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| source_page: pending_human_review | 000063.SZ/2023/expected_metrics.yaml (16 entries) | Requires human to look up page numbers in ZTE annual report PDF |
| source_page: pending_human_review | 000002.SZ/2023/expected_metrics.yaml (16 entries) | Requires human to look up page numbers in Vanke annual report PDF |
| verified_date: null | 000063.SZ/2023/expected_metrics.yaml | Set after human cross-verification |
| verified_date: null | 000002.SZ/2023/expected_metrics.yaml | Set after human cross-verification |
| l3_verified: false | manifest.yaml (000063.SZ, 000002.SZ) | Flipped to true only after human cross-verification |

## User Setup Required

**Human verification required for ZTE and Vanke:**
1. Download ZTE 2023 annual report from CNINFO (search "中兴通讯 000063")
2. Download Vanke 2023 annual report from CNINFO (search "万科A 000002")
3. Cross-verify P0 metrics against annual report financial statements
4. Update source_page fields with actual page citations (e.g., "p.45")
5. Set verified_date and verified_by in expected_metrics.yaml
6. Flip l3_verified to true in manifest.yaml
7. Run `pytest -m golden` to confirm expanded parametrization passes

## Next Phase Readiness
- Phase 24 plan 02 execution complete with both non-financial stocks computed
- Combined with 24-01 (ICBC + Ping An), 4 stocks now have computed values pending human verification
- Once human verifies all 4 stocks, golden test count will expand from 22 to ~110 tests (5 stocks total including Moutai)
- Reconcile CLI will work for all stocks once l3_verified is flipped

---
*Phase: 24-golden-dataset-expansion*
*Completed: 2026-05-23*

## Self-Check: PASSED

All 6 files verified present. All 3 commit hashes verified in git log.
