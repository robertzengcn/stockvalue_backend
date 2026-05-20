# Research Summary — v1.4 Financial Metrics Validation

**Date:** 2026-05-20
**Status:** Complete

## Key Findings

### Stack Decisions
- **No new infrastructure needed** — validation is purely code + test data
- **No new dependencies beyond Typer** for Reconcile CLI (PyYAML, Pydantic, pytest, Rich already installed)
- Explicitly rejected: syrupy (exact snapshots won't work for tolerance-based comparison), deepdiff (dependency-heavy), pytest-golden (unmaintained)

### Architecture Decisions
- **Cross-cutting test-time concern** — no modification to production code (API routes, services, repos unchanged)
- New `stockvaluefinder/validation/` module with metric_registry.yaml, schema.py, loader.py, comparators.py
- New `tests/golden/` directory structure per stock/year with frozen AKShare JSON + expected_metrics.yaml
- New `stockvaluefinder/tools/reconcile.py` Typer CLI

### Patterns
- Metric Registry as YAML single source of truth, Pydantic-validated at load time
- Three-layer verification: L1 (formula), L2 (field mapping), L3 (end-to-end golden)
- Tolerance model: absolute OR relative per metric, driven by registry
- CI separation: frozen data tests on every PR, live tests weekly

### Pitfalls to Address
- AKShare field name instability between versions — mitigated by frozen JSON snapshots
- Bank/insurance financial sector accounting differences — sector variants in registry
- _coalesce_akshare_field multi-field fallback can silently pick wrong fields — L2 mapping tests
- Floating point precision — tolerance-based comparison, not exact equality
- Golden values become stale — provenance.md tracks source and verification date

## Open Questions
- Exact golden stock sample (12-15 CSI 300 stocks) to be defined in requirements
- Whether to include HK stocks (0700.HK) in initial golden set
- Weekly live job scheduling mechanism (GitHub Actions cron vs custom scheduler)
