---
phase: 17-metric-registry-foundation
plan: 01
subsystem: validation
tags: [pydantic, yaml, metric-registry, schema, frozen-models]
dependency_graph:
  requires: []
  provides: [metric-registry-schema, metric-registry-yaml]
  affects: [stockvaluefinder/validation/]
tech-stack:
  added: [pydantic-v2-frozen-models, yaml-validated-at-load]
  patterns: [frozen-pydantic-model-hierarchy, lru-cache-singleton-ready, sector-variant-override]
key-files:
  created:
    - stockvaluefinder/validation/__init__.py
    - stockvaluefinder/validation/schema.py
    - stockvaluefinder/validation/metric_registry.yaml
    - stockvaluefinder/tests/unit/test_validation/__init__.py
    - stockvaluefinder/tests/unit/test_validation/test_schema.py
  modified: []
decisions:
  - "D-05: Single unified Pydantic model hierarchy (Tolerance, InputField, ReferenceValue, Variant, MetricDefinition, MetricRegistry)"
  - "D-06: Flat YAML dict keyed by metric name with category field"
  - "D-07: Sector variants via variants field per metric entry, Variant merges into MetricDefinition on get()"
  - "D-04: YAML source of truth validated by Pydantic at load time via MetricRegistry.from_yaml()"
metrics:
  duration_seconds: 355
  completed_date: 2026-05-21
---

# Phase 17 Plan 01: Metric Registry Foundation Summary

Pydantic V2 frozen model hierarchy and YAML registry cataloging 28 financial metrics across 7 analysis modules, validated at load time.

## Results

| Metric | Value |
|--------|-------|
| Tasks completed | 2/2 |
| Tests passing | 33 (25 schema + 8 YAML loading) |
| Metric entries in registry | 28 across 7 categories |
| Duration | ~6 minutes |

## Task Summary

### Task 1: Create Pydantic schema models for metric registry

- **Commit:** a04d870
- **Files:** `validation/__init__.py`, `validation/schema.py`, `tests/unit/test_validation/__init__.py`, `tests/unit/test_validation/test_schema.py`
- **Details:** Implemented 6 frozen Pydantic V2 models (Tolerance, InputField, ReferenceValue, Variant, MetricDefinition, MetricRegistry) with cross-reference validation on depends_on, from_yaml() class method, and convenience query methods (get, metrics_by_category, p0_metrics, all_metrics). TDD approach: wrote 25 tests first (RED), then implemented (GREEN).

### Task 2: Create metric_registry.yaml with all 28 metric entries

- **Commit:** 8f3f597
- **Files:** `validation/metric_registry.yaml`, `tests/unit/test_validation/test_schema.py` (8 additional tests)
- **Details:** Created YAML with 28 metric entries across 7 categories: risk (13), roic (4), valuation (4), yield (2), capex (2), policy (2), alpha (1). Each entry has function path, params, returns, tolerance, formula_ref, priority, and dependency chains. NOPAT includes financial/non_financial sector variants. M-Score has depends_on all 8 sub-indices. Added 8 end-to-end tests loading the actual YAML file.

## Key Decisions

1. **Variant merging via get() method**: When `registry.get("nopat", sector="financial")` is called, the Variant overrides are merged into a new MetricDefinition by dumping the base model, applying overrides, and re-validating. This keeps MetricDefinition frozen while supporting sector-specific resolution.

2. **from_yaml_file() convenience method**: Added alongside from_yaml() for direct file loading, supporting downstream CLI and CI use cases (Phase 22).

3. **Tolerance model_validator**: Enforces at least one of absolute/relative at Pydantic validation time, ensuring every metric entry has a usable tolerance.

4. **depends_on cross-reference**: Model-level validator checks that all depends_on entries reference existing metric names in the registry. This catches structural errors at load time rather than at test execution time.

## Metric Coverage

| Category | Count | Metrics |
|----------|-------|---------|
| risk | 13 | dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata, m_score, f_score, detect_存贷双高, goodwill_ratio, profit_cash_divergence |
| roic | 4 | nopat (2 variants), invested_capital, roic, roic_wacc_spread |
| valuation | 4 | wacc, present_value, terminal_value, margin_of_safety |
| yield | 2 | net_dividend_yield, yield_gap |
| capex | 2 | buyback_yield, capital_allocation_score |
| policy | 2 | resonance_score, dcf_adjustment |
| alpha | 1 | alpha_score |

## Verification

- All 33 tests pass: `cd stockvaluefinder && DATABASE_URL=... uv run pytest tests/unit/test_validation/test_schema.py -v`
- YAML loads via public API: `cd stockvaluefinder && uv run python -c "from stockvaluefinder.validation import MetricRegistry; r = MetricRegistry.from_yaml_file('stockvaluefinder/validation/metric_registry.yaml'); print(f'Loaded {len(r.all_metrics())} metrics')"`
- Linting clean: `cd stockvaluefinder && uv run ruff check stockvaluefinder/validation/`
- Format clean: `cd stockvaluefinder && uv run ruff format --check stockvaluefinder/validation/`

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. The trust boundary (YAML -> Pydantic) is mitigated by schema validation at load time per T-17-01.

## Self-Check: PASSED

All 6 created files verified present. Both commit hashes (a04d870, 8f3f597) found in git log.
