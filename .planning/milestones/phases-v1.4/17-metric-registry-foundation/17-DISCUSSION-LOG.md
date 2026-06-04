# Phase 17: Metric Registry Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 17-Metric Registry Foundation
**Areas discussed:** Registry granularity, YAML vs Python, Sector variant design, Registry query API

---

## Registry Granularity

| Option | Description | Selected |
|--------|-------------|----------|
| All atomic calculations | Every calculation with a formula reference and may need independent golden testing: DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA individually, plus composite M-Score. NOPAT and invested_capital separately from ROIC. | ✓ |
| Composites only | Register only the 7 top-level composite metrics — sub-indices tested via composite tests | |
| Every calculate_* function | Register every unique calculation function (20+ functions) | |

**User's choice:** All atomic calculations — every sub-index, intermediate calculation, and composite gets its own entry (~25-30 entries).
**Notes:** NOPAT and invested_capital registered separately from ROIC. FCF projections separate from intrinsic value.

### Dependency chains

| Option | Description | Selected |
|--------|-------------|----------|
| Include dependency chains | Registry defines which metrics depend on which — ROIC depends_on [nopat, invested_capital] | ✓ |
| Flat, no dependencies | Flat registry — each entry is independent | |

**User's choice:** Include dependency chains.

### Function signatures

| Option | Description | Selected |
|--------|-------------|----------|
| Include function signature | Each entry describes function signature with input param names, types, return type | ✓ |
| Skip function signatures | Registry only tracks what to test/verify | |

**User's choice:** Include function signatures.

---

## YAML vs Python

| Option | Description | Selected |
|--------|-------------|----------|
| YAML as source of truth | YAML file is the source of truth, Pydantic validates at load time, Python reads YAML | ✓ |
| Pure Python registry | Metrics defined directly as Pydantic models in a Python module | |
| YAML + code generation | CI step builds typed Python module from YAML | |

**User's choice:** YAML as source of truth with Pydantic validation.

### Pydantic model design

| Option | Description | Selected |
|--------|-------------|----------|
| Single model hierarchy | One Pydantic model hierarchy validates the entire YAML — all entries share same schema | ✓ |
| Category-specific models | Separate models per category (RiskMetricDefinition, RoicMetricDefinition) | |

**User's choice:** Single unified model hierarchy.

### YAML structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat keyed dict | metrics: { m_score: {...}, dsri: {...}, roic: {...} } with category field | ✓ |
| Nested by category | risk: { m_score: { indices: { dsri: ... } } } | |

**User's choice:** Flat keyed dict with category field for filtering.

---

## Sector Variant Design

| Option | Description | Selected |
|--------|-------------|----------|
| variants field per metric | Metric entry has a variants: field listing named variants, each overriding function/inputs/tolerances | ✓ |
| Separate metric entries | Each variant is a fully independent metric entry (roic_financial, roic_non_financial) | |

**User's choice:** variants field per metric — base inherits shared config, variants override specifics.

### Variant resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit sector parameter | Caller specifies sector when querying | ✓ |
| Auto-detect from stock metadata | Registry auto-detects sector from stock metadata | |
| Both | Explicit overrides auto | |

**User's choice:** Explicit sector parameter — caller passes `sector="financial"`.

---

## Registry Query API

| Option | Description | Selected |
|--------|-------------|----------|
| Frozen MetricRegistry object | load_metric_registry() → MetricRegistry with methods: get(), get with sector, metrics_by_category(), p0_metrics() | ✓ |
| Stateless free functions | get_metric(), list_metrics() without a registry object | |
| Both patterns | Object + convenience functions | |

**User's choice:** Frozen MetricRegistry object with methods.

### Tolerance validation

| Option | Description | Selected |
|--------|-------------|----------|
| Validation lives in registry | registry.check(name, expected, computed) → ComparisonResult using stored tolerances | ✓ |
| Validation in separate comparator module | Registry returns tolerance specs, comparators.py does actual comparison | |

**User's choice:** Validation lives in the registry via registry.check().

### Module location

| Option | Description | Selected |
|--------|-------------|----------|
| New validation/ module | stockvaluefinder/validation/ — separate from production code | ✓ |
| Inside existing models/ | stockvaluefinder/models/validation.py | |

**User's choice:** New validation/ module.

---

## Claude's Discretion

- Exact Pydantic field names and optional vs required fields for MetricDefinition
- Whether `params` uses Pydantic model-based validation or simple type strings
- How `depends_on` is validated (cross-reference check at load time)
- Exact method signatures for MetricRegistry (balance of convenience vs surface area)
- Whether P0/P1/P2 priority is a field on each metric entry or derived from a separate priority config

## Deferred Ideas

None
