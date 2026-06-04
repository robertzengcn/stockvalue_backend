---
phase: 21-l3-end-to-end-golden-testing
plan: 02
subsystem: testing
tags: [golden-testing, pytest-parametrize, tolerance-assertions, frozen-data, akshare]

# Dependency graph
requires:
  - phase: 21-01
    provides: L3 conftest fixtures (frozen_data_loader, compute_metrics_from_frozen, assert_metric_within_tolerance)
provides:
  - L3 frozen golden test suite parametrized over verified stocks
  - L3 live AKShare golden test for upstream API change detection
  - Inline diff-table helper for P0 failure diagnostics
affects: [21-03-diff-report, future-golden-tests]

# Tech tracking
tech-stack:
  added: []
  patterns: [parametrized-golden-tests, p0-hard-assert-p1-xfail, skip-null-expected]

key-files:
  created:
    - stockvaluefinder/tests/golden/test_l3_golden.py
    - stockvaluefinder/tests/golden/test_l3_golden_live.py
  modified:
    - stockvaluefinder/tests/golden/conftest.py
    - stockvaluefinder/tests/unit/test_l2/conftest.py

key-decisions:
  - "frozen_data_loader selects annual record by REPORT_DATE match instead of records[0]"
  - "compute_metrics_from_frozen extracts previous-year from same frozen JSON file"
  - "P0 failures are hard assertions, P1 failures use pytest.xfail (non-blocking)"
  - "Live test only verifies data is fetchable, does not compare values against expected"

patterns-established:
  - "Parametrize over _load_verified_ids() which reads manifest.yaml at collection time"
  - "Skip metrics with null expected values or uncomputable values using pytest.skip/continue"
  - "Boolean metrics converted to float (True=1.0, False=0.0) before tolerance comparison"

requirements-completed: [LV3-01, LV3-02, LV3-04, LV3-05]

# Metrics
duration: 10m
completed: "2026-05-21"
tasks: 2
files_modified: 4
---

# Phase 21 Plan 02: L3 Golden Pipeline Tests Summary

Parametrized frozen golden tests with P0 hard assertions and P1 xfail, plus live AKShare fetch test, all passing for 600519.SH anchor stock

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-21T14:30:26Z
- **Completed:** 2026-05-21T14:40:23Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Frozen golden P0/P1 tests fully passing for 600519.SH (13 P0 metrics + 3 P1 metrics verified)
- Live golden test scaffold ready for weekly AKShare API regression runs
- Metrics coverage test ensures every metric in expected_metrics.yaml is categorized

## Task Commits

Each task was committed atomically:

1. **Task 1 + Task 2: L3 frozen and live golden tests** - `3674543` (test)
   - Includes conftest.py bug fixes and L2 conftest.py NaN handling fix

## Files Created/Modified
- `stockvaluefinder/tests/golden/test_l3_golden.py` - Frozen golden P0/P1/metrics-counted tests
- `stockvaluefinder/tests/golden/test_l3_golden_live.py` - Live AKShare data fetch test
- `stockvaluefinder/tests/golden/conftest.py` - Fixed frozen_data_loader and compute_metrics_from_frozen
- `stockvaluefinder/tests/unit/test_l2/conftest.py` - Fixed NaN-to-None conversion in build_standardized_report_from_frozen

## Decisions Made
- frozen_data_loader selects annual record by matching REPORT_DATE to `{year}-12-31` rather than taking `records[0]` (which was the most recent quarterly report)
- compute_metrics_from_frozen extracts previous-year record from the same frozen JSON file rather than looking for a separate directory
- P0 failures are hard assertions (100% pass required), P1 failures use `pytest.xfail` (non-blocking, >=90% pass target)
- Live test only verifies data is fetchable with non-zero revenue -- does not compare values since live data may differ from frozen snapshots

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed frozen_data_loader selecting wrong record**
- **Found during:** Task 1 (P0 test skipped because all metrics were computed from wrong record)
- **Issue:** `frozen_data_loader` returned `records[0]` (most recent quarterly report) instead of the annual record for the requested fiscal year
- **Fix:** Added `_find_record_for_period()` helper that matches `REPORT_DATE` against `{year}-12-31`, updated loader to use it
- **Files modified:** stockvaluefinder/tests/golden/conftest.py
- **Verification:** P0 metrics now compute correctly from annual records
- **Committed in:** 3674543

**2. [Rule 1 - Bug] Fixed compute_metrics_from_frozen failing to find previous-year data**
- **Found during:** Task 1 (P0 test skipped because previous-year metrics were all None)
- **Issue:** `compute_metrics_from_frozen` looked for previous-year data in a separate directory `{ticker}/{prev_year}/`, but frozen JSON files contain ALL years in one file
- **Fix:** Load raw JSON files and use `_find_record_for_period()` to extract both current and previous year records from the same file
- **Files modified:** stockvaluefinder/tests/golden/conftest.py
- **Verification:** All YoY metrics (M-Score indices, F-Score, etc.) now compute correctly
- **Committed in:** 3674543

**3. [Rule 1 - Bug] Fixed build_standardized_report_from_frozen NaN handling**
- **Found during:** Task 1 (decimal.InvalidOperation when F-Score tried to convert string "None" to Decimal)
- **Issue:** `str(balance.get("LONG_LOAN", ...))` produced string "None" when the AKShare field was NaN (sanitized to Python None), causing `Decimal("None")` to raise InvalidOperation
- **Fix:** Replaced all `str(record.get(...))` calls with a `_field_str()` helper that skips None values and falls through to the next key or returns "0" default
- **Files modified:** stockvaluefinder/tests/unit/test_l2/conftest.py
- **Verification:** All 564 existing L1/L2 tests still pass; F-Score now computes correctly
- **Committed in:** 3674543

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs)
**Impact on plan:** All three fixes were necessary for the golden tests to run correctly. The bugs were in pre-existing code from Plan 21-01 and the L2 test infrastructure. No scope creep.

## Issues Encountered
None - all bugs were caught and fixed during execution

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- L3 golden test suite fully operational for 600519.SH
- Ready for Plan 21-03 (diff report tooling) to enhance failure diagnostics
- Additional stocks can be verified by setting `l3_verified: true` in manifest.yaml and adding expected_metrics.yaml

---
*Phase: 21-l3-end-to-end-golden-testing*
*Completed: 2026-05-21*
