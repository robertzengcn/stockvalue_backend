---
phase: 22
plan: 01
subsystem: tools
tags: [reconcile, golden-data, frozen-pipeline, live-pipeline, cli-core]
dependency_graph:
  requires:
    - 17-01 (metric_registry.yaml)
    - 17-02 (MetricRegistry.check + ComparisonResult)
    - 18-01 (golden dataset structure)
    - 18-02 (frozen AKShare JSON + expected_metrics.yaml)
    - 21-01 (L3 pipeline compute_metrics_from_frozen logic)
  provides:
    - reconcile() frozen-mode reconciliation
    - reconcile_live() async live-mode reconciliation
    - ReconcileResult dataclass
    - compute_metrics_for_ticker() standalone L3 pipeline
    - load_manifest(), lookup_is_financial(), load_expected_metrics_for_ticker()
  affects: []
tech_stack:
  added: [tools/reconcile_core.py]
  patterns: [frozen-dataclass-result, pure-function-pipeline, async-live-data-path]
key_files:
  created:
    - stockvaluefinder/tools/__init__.py
    - stockvaluefinder/tools/reconcile_core.py
    - stockvaluefinder/tests/unit/test_tools/__init__.py
    - stockvaluefinder/tests/unit/test_tools/test_reconcile_core.py
  modified: []
decisions:
  - GOLDEN_DIR resolved via Path(__file__).parents[2] to reach stockvaluefinder/tests/golden (3 levels up from tools module)
  - Imported build_standardized_report_from_frozen and roic_inputs_from_frozen from test_l2/conftest as shared utilities
  - Replicated (not imported) compute_metrics_from_frozen logic from golden/conftest to avoid test fixture dependency in production code
  - reconcile_live() uses service.shutdown() (not close()) matching ExternalDataService API
metrics:
  duration_minutes: 15
  completed_date: "2026-05-21"
  tasks_total: 2
  tasks_completed: 2
  files_created: 4
  files_modified: 0
  tests_added: 8
---

# Phase 22 Plan 01: Reconcile Core Logic Summary

Pure-function reconciliation pipeline that loads golden expected values, computes metrics from frozen or live data, and compares using MetricRegistry tolerance system. Supports frozen mode (committed golden JSON, no network) and live mode (ExternalDataService + AKShare).

## What Was Built

### reconcile_core.py (792 lines)

- **ReconcileResult** frozen dataclass with ticker, year, comparisons list, summary dict, p0_all_pass flag, and skipped_metrics
- **reconcile()** -- frozen-mode pipeline: loads golden YAML, computes from frozen AKShare JSON, compares via registry.check(), returns structured result
- **reconcile_live()** -- async live-mode pipeline using ExternalDataService for real AKShare data, same comparison logic
- **compute_metrics_for_ticker()** -- standalone L3 pipeline replicating the golden conftest compute_metrics_from_frozen fixture: M-Score 8 indices + composite, F-Score, detect_存贷双高, goodwill ratio, profit-cash divergence, ROIC/NOPAT/invested capital
- **load_manifest()** -- loads manifest.yaml from golden dataset
- **lookup_is_financial()** -- ticker -> is_financial lookup from manifest
- **load_expected_metrics_for_ticker()** -- loads expected_metrics.yaml for any ticker/year
- **_compute_pass_rate_summary()** -- P0/P1 breakdown with pass rates and failure list

### Test Suite (8 tests, all passing)

- test_reconcile_full_600519: >= 10 comparisons, correct ticker/year
- test_reconcile_single_metric: metric="m_score" filters to exactly 1 entry
- test_reconcile_nonexistent_metric: empty comparisons for unknown metric name
- test_reconcile_p0_status: P0 metrics 100% pass for 600519.SH/2023
- test_reconcile_summary_counts: total == passed + failed
- test_reconcile_missing_ticker_raises: FileNotFoundError for 999999.SH
- test_load_manifest: 14 golden stocks
- test_lookup_is_financial: correct True/False/default values

## TDD Compliance

| Gate | Commit | Hash |
|------|--------|------|
| RED | test(22-01): add failing tests for reconcile core pipeline | ef910ce |
| GREEN | feat(22-01): add reconcile core logic with frozen and live data paths | f802cb5 |

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

The live-mode reconcile_live() handles missing data gracefully with try/except blocks (setting metrics to None when data is unavailable), but has no dedicated unit tests since it requires network access. The plan explicitly states "Unit tests should mock ExternalDataService" -- live-mode mocking tests are deferred to plan 22-02 or a follow-up.

## Threat Flags

No new security-relevant surface introduced beyond what the plan's threat model covers. The reconcile_live() path adds a network boundary (AKShare API calls), which is documented as T-22-04 (accept).

## Self-Check: PASSED

All 5 files verified present. Both commits (RED ef910ce, GREEN f802cb5) found in git log.
