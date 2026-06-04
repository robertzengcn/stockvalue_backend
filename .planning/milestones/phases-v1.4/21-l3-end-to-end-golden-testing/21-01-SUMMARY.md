---
phase: 21-l3-end-to-end-golden-testing
plan: 01
subsystem: validation
tags: [golden-testing, conftest, fixtures, pytest-markers]
dependency_graph:
  requires: [phase-17, phase-18, phase-20]
  provides: [l3-golden-conftest-fixtures, golden-markers]
  affects: [tests/golden/conftest.py, pytest.ini]
tech_stack:
  added: [pytest-session-fixtures, decimal-Decimal]
  patterns: [fixture-closure-cache, index-key-mapping]
key_files:
  created: []
  modified:
    - stockvaluefinder/tests/golden/conftest.py
    - stockvaluefinder/pytest.ini
decisions:
  - Lazy-import L2 helpers inside fixture body to avoid circular dependency at module level
  - Handle missing previous-year data by setting all YoY metrics to None rather than failing
  - Goodwill ratio computed even without previous year since it only needs current-year data
  - Boolean metrics converted to float (True=1.0, False=0.0) for tolerance comparison
metrics:
  duration: 4m
  completed: "2026-05-21"
  tasks: 2
  files_modified: 2
---

# Phase 21 Plan 01: L3 Golden Conftest Fixtures Summary

L3 golden test conftest with 6 session-scoped fixtures (metric_registry_fixture, frozen_data_loader, load_expected_metrics, compute_metrics_from_frozen, assert_metric_within_tolerance) plus golden/golden_live pytest markers.

## Completed Tasks

### Task 1: Register golden and golden_live pytest markers
- Added `golden` marker for L3 end-to-end pipeline tests (frozen data, no network)
- Added `golden_live` marker for L3 tests against live AKShare API (requires network, run weekly)
- Commit: `2ab8499`

### Task 2: Add L3 pipeline fixtures to golden conftest.py
- Added 6 new session-scoped fixtures extending the existing 5 golden conftest fixtures
- `metric_registry_fixture`: wraps `load_metric_registry()` singleton
- `frozen_data_loader`: loads raw_akshare JSON files with NaN sanitization and closure cache
- `load_expected_metrics`: loads expected_metrics.yaml with caching
- `compute_metrics_from_frozen`: full L3 pipeline (M-Score 8 indices, composite M-Score, F-Score, detect_存贷双高, goodwill ratio, profit-cash divergence, ROIC/NOPAT/invested capital)
- `assert_metric_within_tolerance`: tolerance-based assertion using `registry.check()` with boolean-to-float conversion
- Commit: `7646765`

## Verification Results

1. `pytest tests/golden/conftest.py --co -q` -- collected without import errors
2. `pytest --markers` -- lists golden and golden_live markers correctly
3. Existing L1 and L2 tests: 564 passed, 0 failed
4. Module-level imports verified: _sanitize_nan, INDEX_KEY_MAP, _METRICS_REQUIRING_EXTERNAL_DATA, all service functions
5. Metric registry loads correctly (28 metrics)

## Deviations from Plan

None - plan executed exactly as written.

## Key Implementation Details

- `INDEX_KEY_MAP` maps 8 short keys (dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata) to long keys expected by `calculate_beneish_m_score`
- `_METRICS_REQUIRING_EXTERNAL_DATA` frozenset contains 12 metric names that require market data (wacc, present_value, terminal_value, margin_of_safety, net_dividend_yield, yield_gap, buyback_yield, capital_allocation_score, resonance_score, dcf_adjustment, alpha_score, roic_wacc_spread)
- `compute_metrics_from_frozen` handles missing previous-year data by checking file existence and setting YoY-dependent metrics to None
- Goodwill ratio is computed even without previous year since it only needs current-year balance sheet data
- ROIC computation uses `roic_inputs_from_frozen` for raw field extraction rather than the standardized report
