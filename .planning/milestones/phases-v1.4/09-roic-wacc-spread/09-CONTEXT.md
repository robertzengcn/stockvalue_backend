# Phase 9: ROIC-WACC Spread Analysis - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can evaluate whether a stock creates or destroys value by comparing its return on invested capital (ROIC) against its weighted average cost of capital (WACC), with 3-year trend detection for competitive moat identification. This phase delivers: ROIC calculation, true WACC calculation (with debt weighting), spread classification, sector-aware NOPAT, edge case handling, and moat trend detection.

</domain>

<decisions>
## Implementation Decisions

### WACC Approach
- **D-01:** Extend existing `calculate_wacc()` in `valuation_service.py` with optional debt parameters (`debt_weight`, `cost_of_debt`, `tax_rate`) defaulting to 0. Existing DCF calls continue to work unchanged (Ke-only). New ROIC-WACC calls pass debt params for true WACC.
- **D-02:** Cost of debt (Kd) is implied from financials: `finance_expense / total_interest_bearing_debt` from AKShare balance sheet data.
- **D-03:** ROIC-WACC API response includes full WACC breakdown: Ke, Kd, D/E ratio, tax rate, equity weight, debt weight.

### Multi-Year Data Flow
- **D-04:** Add `fetch_multi_year_financials(ticker, years=3)` method to existing `AKShareClient`. Calls AKShare API once (returns all years), filters in-memory for the requested years.
- **D-05:** Multi-year financial data cached in Redis with 24h TTL, consistent with existing financials caching pattern.

### Moat Trend Rules
- **D-06:** Three-state trend classification using `scipy.stats.linregress` on 3-year ROIC-WACC spread: "Competitive Advantage" (slope > 0.005/yr), "Deteriorating" (slope < -0.005/yr), "Stable" (between ±0.005/yr).
- **D-07:** Generic labels only — "Competitive Advantage", "Deteriorating", "Stable". No PRD-specific moat type heuristics (intangible/scale) at this stage.

### Edge Case Policy
- **D-08:** Negative invested capital (cash > equity + debt): return ROIC = None with flag `negative_invested_capital`. Do NOT compute negative ROIC value.
- **D-09:** Auto-detect financial sector from `stock.sector` field in database. If sector contains "银行", "保险", or "证券", use financial NOPAT formula.
- **D-10:** Financial sector NOPAT: `OPERATE_PROFIT * (1 - tax_rate)`. Non-financial sector NOPAT: `(TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)`.
- **D-11:** NaN debt fields (debt-free companies): normalize to 0.0. WACC for debt-free companies equals Ke (cost of equity only), same as existing behavior.

### Claude's Discretion
- Exact API endpoint path and request/response model structure
- New ORM model field names and Alembic migration details
- Internal helper function organization within roic_service.py
- Test file structure and test case selection

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Alpha Engine PRD
- `doc/Alpha_Engine_V2.0/Alpha_Engine_V2.0.md` — Original PRD with ROIC-WACC specification, moat detection concept, and capital allocation scoring

### Existing Code (critical for this phase)
- `stockvaluefinder/stockvaluefinder/services/valuation_service.py` — Contains existing `calculate_wacc()` at line 11 (Ke-only, must extend), `analyze_dcf_valuation()` at line 207 (calls calculate_wacc)
- `stockvaluefinder/stockvaluefinder/services/risk_service.py` — Contains `_safe_ratio()` pattern for handling division edge cases (reuse pattern for negative IC handling)
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` — Contains `get_financial_report()`, `get_balance_sheet()` methods to extend with multi-year fetching
- `stockvaluefinder/stockvaluefinder/config.py` — Frozen dataclass config pattern; add ROIC-specific config
- `stockvaluefinder/stockvaluefinder/utils/cache.py` — Redis CacheManager with decorator pattern for caching

### Research (informed decisions)
- `.planning/research/STACK.md` — AKShare field mapping for ROIC inputs (TOTAL_PROFIT, FINANCE_EXPENSE, INCOME_TAX, OPERATE_PROFIT, etc.)
- `.planning/research/PITFALLS.md` — WACC Ke-only pitfall, financial sector NOPAT, negative invested capital handling
- `.planning/research/SUMMARY.md` — Phase ordering rationale, dependency analysis

### Project Context
- `.planning/PROJECT.md` — Current milestone goals, validated requirements, constraints
- `.planning/REQUIREMENTS.md` — ROIC-01 through ROIC-06 requirements
- `.planning/ROADMAP.md` — Phase 9 goal, success criteria, dependencies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `calculate_wacc()` in valuation_service.py: Extend with optional debt params (backward compatible)
- `_safe_ratio()` in risk_service.py: Pattern for handling division-by-zero and edge cases in financial ratios
- `AKShareClient.get_financial_report()`: Single-period financial data fetching, extend for multi-year
- `CacheManager` in utils/cache.py: Redis caching with TTL and decorator pattern
- `BaseRepository[T]` in repositories/base.py: Generic CRUD repository pattern

### Established Patterns
- Pure function services: All calculations are stateless pure functions in `services/` directory
- Frozen config dataclasses: `ValuationConfig`, `RiskConfig`, etc. with `frozen=True`
- API envelope: `ApiResponse[T]` with success/data/error fields
- Request models: Pydantic BaseModel with Field validation
- ORM models in `db/models/`: Map to Pydantic domain models via `models/`
- Route pattern: `POST /api/v1/analyze/{domain}` with dependency injection

### Integration Points
- `valuation_service.py:207` — Where calculate_wacc is called for DCF; must remain backward compatible
- `akshare_client.py` — Where new multi-year fetch methods are added
- `config.py` — Where new ROICConfig frozen dataclass is added
- New `roic_routes.py` — New API route file for ROIC-WACC analysis endpoint
- New `roic_service.py` — New service for ROIC calculation, NOPAT, invested capital
- New `db/models/roic.py` — New ORM model for persisting ROIC analysis results

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. All decisions are captured in the Implementation Decisions section above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 9-ROIC-WACC Spread Analysis*
*Context gathered: 2026-05-03*
