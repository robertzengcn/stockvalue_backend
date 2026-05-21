---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Financial Metrics Validation
status: executing
stopped_at: ""
last_updated: "2026-05-21T22:17:16Z"
last_activity: 2026-05-21
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 15
  completed_plans: 14
  percent: 93
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-20)

**Core value:** Help individual value investors quickly screen CSI 300 stocks for fraud risk and intrinsic value, replacing hours of manual annual report reading with automated, auditable analysis.
**Current focus:** v1.4 Financial Metrics Validation

## Current Position

Phase: 23 complete
Plan: 23-01 complete
Status: CI integration complete (GitHub Actions workflow with 4 jobs, validate_registry pre-commit hook)
Last activity: 2026-05-21 -- Phase 23 Plan 01 complete (GitHub Actions validation workflow + pre-commit registry hook)

Progress: [###########   ] 93%

## Phase 17 Summary (Complete)
- 17-01: Pydantic schema models + metric_registry.yaml (28 entries across 7 categories)
- 17-02: lru_cache loader, comparators (ComparisonResult), registry.check() method
- 60 tests passing, 98-100% coverage on validation module

## Phase 18 Summary (Complete)
- 18-01: Golden dataset directory structure, manifest.yaml, expected_metrics.yaml templates, conftest.py fixtures
- 18-02: 42 frozen AKShare JSON files (14 stocks x 3 statements), 600519.SH golden values computed from production calculate_* functions, 14 provenance.md files, compute_golden_values.py script

## Phase 19 Summary (Complete)
- 19-01: L1 formula tests for risk_service (52 tests: M-Score 8 sub-indices, composite, F-Score 9 components, detect_存贷双高, goodwill ratio, profit-cash divergence, risk level)
- 19-02: L1 formula tests for 6 remaining services (109 tests: roic x17, valuation x20, yield x13, capex x21, policy x10, alpha x28)
- Total L1 tests: 161, all passing, all marked @pytest.mark.l1_formula
- l1_formula marker registered in pytest.ini

## Phase 20 Summary (Complete)
- 20-01: L2 snapshot + traceability tests (217 tests: 210 snapshot x 14 stocks, 7 traceability for 600519.SH anchor)
- 20-02: L2 cross-source + sector-branch tests (186 tests: 127 cross-source, 59 sector-branch)
- build_standardized_report_from_frozen helper replicates data_service report building from frozen JSON
- Financial stock exemptions for structurally absent fields (banking/insurance)
- Simulated efinance dicts validate AKShare/efinance field mapping equivalence
- NOPAT formula branch verification: financial (OPERATE_PROFIT) vs non-financial (TOTAL_PROFIT + FINANCE_EXPENSE)
- l2_mapping marker registered in pytest.ini
- Total L2 tests: 403, all passing

## Phase 21 Summary (In Progress)
- 21-01: L3 golden conftest fixtures (6 session-scoped fixtures: metric_registry_fixture, frozen_data_loader, load_expected_metrics, compute_metrics_from_frozen, assert_metric_within_tolerance) + golden/golden_live markers in pytest.ini
- compute_metrics_from_frozen runs full L3 pipeline: M-Score 8 indices, composite M-Score, F-Score, detect_存贷双高, goodwill ratio, profit-cash divergence, ROIC/NOPAT/invested capital
- INDEX_KEY_MAP maps 8 short keys to long keys for calculate_beneish_m_score
- Handles missing previous-year data by setting YoY metrics to None
- 12 metrics requiring external market data set to None
- 21-03: L3 diff report utilities (generate_diff_report, format_diff_table, diff_report_to_json, summarize_pass_rates) + 5 tests including 600519.SH/2023 integration
- Fixed conftest.py goodwill Decimal conversion bug for None/"None" string values
- All existing 564 L1+L2 tests still pass

## Phase 22 Summary (Complete)
- 22-01: Reconcile core logic (ReconcileResult frozen dataclass, reconcile frozen-mode, reconcile_live async live-mode, compute_metrics_for_ticker standalone L3 pipeline, load_manifest, lookup_is_financial, load_expected_metrics_for_ticker, _compute_pass_rate_summary) + 8 unit tests passing for 600519.SH/2023
- 22-02: Typer CLI with Rich colored tables, JSON mode (--json), verbose audit trail (--verbose/-v), single-metric filter (--metric), live mode (--live), exit codes (0/1/2), path sanitization + 7 unit tests passing

## Phase 23 Summary (Complete)
- 23-01: GitHub Actions workflow (.github/workflows/validation.yml) with 4 jobs: l1-formula, l2-mapping, golden (PR/push gates), golden-live-scheduled (weekly cron + workflow_dispatch); validate_registry.py script; pre-commit validate-registry hook

## Session Continuity

Phase 23 complete. All v1.4 phases done. Plan 23-01 complete (GitHub Actions validation workflow + pre-commit registry hook).

