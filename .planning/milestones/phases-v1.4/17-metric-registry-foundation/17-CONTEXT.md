# Phase 17: Metric Registry Foundation - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a YAML-based metric registry (`stockvaluefinder/validation/`) that catalogs all financial metrics across 7 analysis modules. It is the single source of truth that drives golden tests, the reconcile CLI, and CI validation. Every `calculate_*` function across all services gets a registry entry with its formula reference, input/output contract, tolerance specs, sector variants, and dependency chain.

This is purely developer infrastructure — no production API changes, no database migrations, no user-facing features.
</domain>

<decisions>
## Implementation Decisions

### Registry Granularity (D-01 through D-03)
- **D-01:** Every `calculate_*` function across all 7 analysis modules gets its own metric entry (~25-30 entries total). Sub-indices (DSRI, GMI, etc.) are registered independently from composites (M-Score). Intermediate calculations (NOPAT, invested_capital) are registered separately from their consumers (ROIC).
- **D-02:** The registry encodes metric dependency chains. Each entry has an optional `depends_on: [metric_names]` field so tests and CLI can compute upstream metrics first and reconcile whole chains.
- **D-03:** Each metric entry includes a function signature contract: `function` (module path + name), `params` (named inputs with types), `returns` (return type description). Tests and CLI can validate calls match the contract.

### YAML Design (D-04 through D-06)
- **D-04:** YAML is the source of truth (`metric_registry.yaml`). Pydantic V2 validates the entire YAML at load time via `MetricRegistry.model_validate(raw)`. No code generation — Python code reads YAML through the Pydantic model layer.
- **D-05:** Single unified Pydantic model hierarchy: `MetricRegistry → MetricDefinition → Tolerance / InputField / ReferenceValue / Variant`. All metric entries share the same schema. Category-specific fields are optional.
- **D-06:** Flat YAML dict keyed by metric name: `metrics: { dsri: {...}, gmi: {...}, m_score: {...}, roic: {...} }`. Each entry has a `category` field (risk, roic, valuation, yield, capex, policy, alpha) for filtering and grouping.

### Sector Variant Design (D-07 through D-08)
- **D-07:** Sector variants use a `variants` field per metric entry. Each named variant (e.g., `financial`, `non_financial`) overrides: `function`, `params`, `tolerance`. The base entry inherits shared config (formula_ref, category, display_name).
- **D-08:** Variant resolution is explicit: caller passes `sector` parameter (e.g., `"financial"` or `"non_financial"`) when querying the registry. The registry resolves the correct variant from the `variants` map.

### Query API (D-09 through D-011)
- **D-09:** API is a frozen `MetricRegistry` object, loaded once via `lru_cache` singleton (`load_metric_registry()`). Methods: `registry.get(name)`, `registry.get(name, sector="financial")`, `registry.metrics_by_category("risk")`, `registry.p0_metrics()`, `registry.all_metrics()`.
- **D-10:** Tolerance-based validation lives ON the registry: `registry.check(name, expected, computed, sector=None)` returns `ComparisonResult(passed, expected, computed, delta, tolerance_applied)`. The registry reads the tolerance from the metric/variant definition — callers don't need to look up tolerances separately. Comparators utility functions support but don't replace the registry method.
- **D-11:** All code lives in a new `stockvaluefinder/validation/` module — cleanly separated from production code (`models/`, `services/`, `api/`). Structure: `schema.py` (Pydantic models), `loader.py` (YAML loading + lru_cache), `comparators.py` (ComparisonResult dataclass + helper functions), `metric_registry.yaml` (the data).

### Claude's Discretion
- Exact Pydantic field names and optional vs required fields for MetricDefinition
- Whether `params` uses Pydantic model-based validation or simple type strings
- How `depends_on` is validated (cross-reference check at load time)
- Exact method signatures for MetricRegistry (balance of convenience vs surface area)
- Whether P0/P1/P2 priority is a field on each metric entry or derived from a separate priority config
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — REG-01 through REG-05 requirements for this phase
- `.planning/ROADMAP.md` §Phase 17 — Success criteria and plan structure

### Validation Plan (primary design document)
- `doc/financial_metrics_validation_plan.md` — Full validation system design: 3-layer model (L1/L2/L3), metric registry spec, golden dataset structure, tolerances, reconcile CLI

### Existing code to follow
- `stockvaluefinder/stockvaluefinder/models/risk.py` — IndexAuditDetail frozen model (value/numerator/denominator/source_fields pattern)
- `stockvaluefinder/stockvaluefinder/config.py` — lru_cache singleton pattern (`AppConfig.get_instance()`)
- `stockvaluefinder/stockvaluefinder/services/risk_service.py` — calculate_beneish_m_score, calculate_mscore_indices (8 sub-indices), calculate_piotroski_f_score, calculate_goodwill_ratio
- `stockvaluefinder/stockvaluefinder/services/roic_service.py` — calculate_nopat, calculate_invested_capital, calculate_roic, calculate_roic_wacc_spread
- `stockvaluefinder/stockvaluefinder/services/valuation_service.py` — calculate_wacc, calculate_present_value, calculate_terminal_value, calculate_margin_of_safety
- `stockvaluefinder/stockvaluefinder/services/yield_service.py` — calculate_net_dividend_yield, calculate_yield_gap
- `stockvaluefinder/stockvaluefinder/services/capex_service.py` — calculate_buyback_yield, calculate_capital_allocation_score
- `stockvaluefinder/stockvaluefinder/services/policy_service.py` — calculate_resonance_score, calculate_dcf_adjustment
- `stockvaluefinder/stockvaluefinder/services/alpha_service.py` — calculate_alpha_score

### Conventions
- `.planning/codebase/CONVENTIONS.md` — Pydantic frozen models, Python 3.12+ type syntax, immutability patterns, naming conventions
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **IndexAuditDetail** (`models/risk.py:12`): Frozen Pydantic model with value/numerator/denominator/source_fields. The metric registry's ReferenceValue model mirrors this pattern.
- **AppConfig.get_instance()** (`config.py:312`): lru_cache singleton. Same pattern for `load_metric_registry()`.
- **calculate_* naming convention**: 20+ functions across 7 services all follow `calculate_{metric}` — registry `function` fields point to these.

### Established Patterns
- **Frozen Pydantic models**: All config/models use `frozen=True`. MetricRegistry and all sub-models follow this.
- **Google-style docstrings**: Registry module docstrings must match project style.
- **Python 3.12+ types**: `X | Y`, `list[X]`, `dict[str, Any]`. No Optional/List from typing.
- **Absolute imports**: `from stockvaluefinder.validation.schema import MetricRegistry`.

### Integration Points
- **No production code changes needed**: This is purely a new module at `stockvaluefinder/validation/`.
- **Downstream consumers**: Phase 18 (golden dataset), Phase 19 (L1 tests), Phase 21 (L3 tests), Phase 22 (CLI) will all import from `stockvaluefinder.validation`.
- **CI**: `python -c "from stockvaluefinder.validation import load_metric_registry; load_metric_registry()"` validates registry at CI time.
</code_context>

<specifics>
## Specific Ideas

- Registry must support both absolute and relative tolerances per metric. Some metrics (F-Score) require exact match (absolute=0). M-Score needs ±0.05 absolute. ROIC needs ±1% relative.
- The `variants` design is motivated by ROIC's financial vs non-financial NOPAT formula difference. Other metrics (M-Score, F-Score) default to a single `default` variant.
- `depends_on` chains: e.g., `m_score` depends_on `[dsri, gmi, aqi, sgi, depi, sgai, lvgi, tata]`; `roic` depends_on `[nopat, invested_capital]`; `roic_wacc_spread` depends_on `[roic, wacc]`.
- L1 reference values from published papers go in each metric entry's `reference_values` list — these drive Phase 19 tests.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.
</deferred>

---
*Phase: 17-Metric Registry Foundation*
*Context gathered: 2026-05-20*
