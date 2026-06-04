# Phase 10: Capital Allocation Scorecard - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can assess how well management deploys capital through three dimensions: buyback yield (shareholder returns), dividend stability (income consistency), and expansion discipline (avoiding value-destroying growth). The combined scorecard produces a single A/B/C/D rating. This phase depends on Phase 9's ROIC-WACC spread for blind expansion detection (ROIC < WACC AND CapEx surge).

</domain>

<decisions>
## Implementation Decisions

### Buyback Data Strategy
- **D-01:** AKShare `stock_repurchase_em()` returns ALL ~5088 A-share stocks. Fetch full dataset, cache in Redis with 24h TTL, filter for requested ticker on read. Consistent with existing caching pattern.
- **D-02:** Buyback yield uses annual repurchase amount from the most recent full fiscal year. Formula: `buyback_yield = annual_repurchase_amount / market_cap`. Aligned with annual report cycle, consistent with other per-year metrics.

### Dividend Stability Method
- **D-03:** Use existing DividendDataDB (dividend_per_share + fiscal_year) for 5-year DPU trend. Fall back to AKShare fresh fetch if DB has no data for the ticker. Leverages existing dividend infrastructure.
- **D-04:** DPU trend classification via scipy `linregress` on 5-year data — consistent with Phase 9 moat detection pattern. Slope > threshold = "growth", slope < -threshold = "decline", between = "stable". Reuse `analyze_roic_trend` pattern from roic_service.

### Blind Expansion Threshold
- **D-05:** Blind expansion alert triggers when ROIC < WACC AND YoY CapEx growth > 20%. The 20% threshold is a common academic benchmark for aggressive expansion. Requires 2 years of CapEx data.
- **D-06:** CapEx data from existing AKShare financial data — the field `购建固定资产、无形资产和其他长期资产支付的现金` is already extracted by `get_financial_report()`. Extend multi-year fetch to include CapEx.

### Scorecard Weighting
- **D-07:** Combined scorecard uses letter grades A/B/C/D. Each dimension independently rated, then averaged with equal weights (1/3 each): buyback yield, dividend stability, expansion discipline. A = strong capital allocation, D = poor.
- **D-08:** Equal weighting (33/33/33) for the three dimensions. Simple, transparent, no bias toward any single capital allocation signal.

### Claude's Discretion
- Exact thresholds for A/B/C/D grade boundaries per dimension
- API endpoint path and request/response model structure
- New ORM model field names and Alembic migration details
- Internal helper function organization within capex_service.py
- Test file structure and test case selection

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Alpha Engine PRD
- `doc/Alpha_Engine_V2.0/Alpha_Engine_V2.0.md` — Original PRD with capital allocation scoring specification

### Existing Code (critical for this phase)
- `stockvaluefinder/stockvaluefinder/services/roic_service.py` — Phase 9 ROIC service with `analyze_roic_trend()` pattern to reuse for DPU trend
- `stockvaluefinder/stockvaluefinder/external/data_service.py` — `get_roic_inputs()` and `get_multi_year_roic_inputs()` to extend with CapEx data
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` — `fetch_multi_year_financials()` pattern to follow; CapEx field `购建固定资产...` already extracted
- `stockvaluefinder/stockvaluefinder/db/models/dividend.py` — Existing DividendDataDB with `dividend_per_share` and `fiscal_year` fields
- `stockvaluefinder/stockvaluefinder/repositories/dividend_repo.py` — `get_by_ticker()` and `get_by_ticker_and_year()` for existing dividend data access
- `stockvaluefinder/stockvaluefinder/services/yield_service.py` — Existing dividend yield gap analysis
- `stockvaluefinder/stockvaluefinder/repositories/roic_repo.py` — `upsert_by_ticker_year()` pattern to follow
- `stockvaluefinder/stockvaluefinder/config.py` — Frozen dataclass config pattern; add CapitalAllocationConfig

### Project Context
- `.planning/PROJECT.md` — Current milestone goals, validated requirements, constraints
- `.planning/REQUIREMENTS.md` — CAPEX-01 through CAPEX-04 requirements
- `.planning/ROADMAP.md` — Phase 10 goal, success criteria, dependencies
- `.planning/phases/09-roic-wacc-spread/09-CONTEXT.md` — Phase 9 decisions (WACC, sector detection, trend analysis)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `analyze_roic_trend()` in roic_service.py: scipy linregress pattern — reuse for DPU stability trend
- `DividendDataDB` with `dividend_per_share` + `fiscal_year`: existing 5-year DPU data source
- `DividendRepository.get_by_ticker()`: fetch dividend history from DB
- `AKShareClient.fetch_multi_year_financials()`: multi-year financial data with CapEx field available
- `upsert_by_ticker_year()` in roic_repo.py: repository pattern for per-year persistence
- `CacheManager` in utils/cache.py: Redis caching with TTL and decorator pattern

### Established Patterns
- Pure function services: All calculations are stateless pure functions in `services/` directory
- Frozen config dataclasses: Add CapitalAllocationConfig with `frozen=True`
- API envelope: `ApiResponse[T]` with success/data/error fields
- Route pattern: `POST /api/v1/analyze/{domain}` with dependency injection
- Letter grade enums: Use `StrEnum` pattern consistent with RiskLevel, ValuationLevel

### Integration Points
- Phase 9 ROIC-WACC API: `POST /api/v1/analyze/roic` — blind expansion check queries ROIC < WACC
- AKShare `stock_repurchase_em()`: New data source for buyback data (not yet in codebase)
- Existing dividend infrastructure: DB models, repository, AKShare fetch
- CapEx from financials: Already extracted in `get_financial_report()` under cash flow fields
- New `capex_routes.py` — New API route for capital allocation scorecard
- New `capex_service.py` — New service for buyback yield, dividend stability, expansion discipline calculations

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

*Phase: 10-Capital Allocation Scorecard*
*Context gathered: 2026-05-05*
