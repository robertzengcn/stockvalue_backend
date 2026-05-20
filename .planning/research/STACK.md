# Technology Stack

**Project:** StockValueFinder v1.4 Financial Metrics Validation
**Researched:** 2026-05-20
**Scope:** Metric Registry (YAML), Golden Dataset, 3-layer verification (L1/L2/L3), Reconcile CLI, CI golden test markers

## Recommended Stack Changes

### New Dependencies

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| pyyaml | >=6.0.2 | Metric Registry YAML parsing and Golden Dataset manifest loading | Already installed (v6.0.3). `yaml.safe_load` is sufficient for all needs. |
| pydantic | >=2.12.5 | Metric Registry schema validation, Golden Dataset model loading | Already installed. Use Pydantic V2 frozen models to validate YAML-loaded dicts. |
| typer | >=0.15.0 | Reconcile CLI tool | Type-hint-driven CLI matching FastAPI patterns. Rich integration for colored diff output. |

### No New Infrastructure Required

All new features are code and data files only:

| Component | Already Exists | How Used |
|-----------|---------------|----------|
| pytest 9.0+ | Yes | Golden test runner via `pytest -m golden` |
| pytest-asyncio | Yes | Async golden tests against AKShare |
| hypothesis 6.15+ | Yes | L1 formula property-based tests (complement golden) |
| Rich 14.3.3 | Yes | Reconcile CLI colored diff tables |
| AKShare | Yes | L2/L3 tests, frozen JSON for CI |
| PostgreSQL | Yes | Not needed for validation system |
| Redis | Yes | Not needed for validation system |

### What NOT to Add

| Library | Why Rejected |
|---------|-------------|
| syrupy | Exact snapshot matching; financial metrics need tolerance-based comparison |
| deepdiff | 20+ dependencies for nested dict diffing we don't need; `math.isclose()` suffices |
| pytest-golden | Last release 2022, doctest-oriented, not numeric-tolerance-oriented |
| ruamel.yaml | YAML round-tripping we never use; PyYAML safe_load is sufficient |
| cerberus | Pydantic V2 already covers schema validation with better type safety |

## File Structure

```
stockvaluefinder/
  validation/                    # NEW module
    __init__.py
    metric_registry.yaml         # Single source of truth for all metrics
    schema.py                    # Pydantic models (frozen) for registry + golden data
    loader.py                    # YAML loading with lru_cache
    comparators.py               # Tolerance comparison utilities

tests/
  golden/                        # NEW test directory
    __init__.py
    conftest.py                  # Fixtures: golden_loader, registry, comparators
    manifest.yaml                # Master list of golden stocks
    test_l1_formula.py           # L1 formula verification
    test_l2_field_mapping.py     # L2 AKShare field mapping verification
    test_l3_golden.py            # L3 end-to-end golden tests
    600519.SH/2023/              # Golden data per stock/year
      expected_metrics.yaml
      provenance.md
      raw_akshare_income.json
      raw_akshare_balance.json
      raw_akshare_cashflow.json

stockvaluefinder/tools/
    __init__.py
    reconcile.py                 # Typer CLI entry point
```

## Confidence: HIGH

All new dependencies are minimal and well-established. No new infrastructure, databases, or Docker containers needed. The validation system is purely code + test data.
