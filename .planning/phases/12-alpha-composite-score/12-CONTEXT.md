# Phase 12: Alpha Composite Score - Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can see a single composite Alpha score that aggregates all forward-looking analysis dimensions (ROIC-WACC spread, Capital Allocation, Policy Resonance, Moat trend) with transparent fixed weighting and full audit trail. The single API endpoint calls all three existing analysis endpoints internally (live computation), normalizes each component to 0-100, applies fixed weights (40/30/20/10), persists the result in a new AlphaScoreDB table, and returns the complete breakdown including input values, intermediate calculations, and weight assignments.

</domain>

<decisions>
## Implementation Decisions

### Score Normalization
- **D-01:** Dimension-specific mapping to normalize all component scores to 0-100 before applying fixed weights. Each dimension uses its own mapping logic appropriate to its data type (continuous spread → linear clamp, letter grade → point map, 0-100 score → pass-through, enum → tier map).
- **D-02:** ROIC-WACC spread mapped to 0-100 using linear clamp ±10%. spread > +10% = 100, spread < -10% = 0, linear interpolation between. Handles the continuous nature of the spread value.
- **D-03:** Capital Allocation grade mapped linearly: A=100, B=75, C=50, D=25. Even 25-point steps. Simple, transparent, easy to audit.
- **D-04:** Moat trend mapped in three tiers: COMPETITIVE_ADVANTAGE=100, STABLE=50, DETERIORATING=0, INSUFFICIENT_DATA=0. Binary split: widening moat is rewarded, anything else is not.

### Data Source for Moat Trend
- **D-05:** Alpha endpoint reads moat trend by calling the existing ROIC API endpoint internally (POST /api/v1/analyze/roic). This triggers fresh computation including multi-year AKShare fetch and trend regression. Ensures up-to-date moat data at the cost of added latency.

### Orchestration Approach
- **D-06:** Live computation — Alpha endpoint calls all 3 existing API endpoints internally (ROIC, CapEx, Policy Resonance) to get fresh component scores. Always up-to-date, provides full audit trail with actual input values. Acceptable latency tradeoff for accuracy.

### Persistence Model
- **D-07:** New AlphaScoreDB table with all 4 component scores (roic_wacc_score, capex_score, policy_score, moat_score), composite alpha score, weights used, DCF adjustment summary, and timestamp. Clean separation from existing tables, queryable history, follows standard pattern.

### Claude's Discretion
- Exact field names and types in AlphaScoreDB ORM model
- Alembic migration details (table name, constraints, indexes)
- API endpoint path and request/response model structure
- AlphaScoreRepository method signatures
- Internal helper function organization within alpha_service.py
- Test file structure and test case selection
- How live endpoint calls are implemented (direct service calls vs HTTP requests)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Alpha Engine PRD
- `doc/Alpha_Engine_V2.0/Alpha_Engine_V2.0.md` — Original PRD with composite Alpha scoring specification, fixed weights

### Existing Component Endpoints (critical — Alpha endpoint calls these)
- `stockvaluefinder/stockvaluefinder/api/roic_routes.py` — POST /api/v1/analyze/roic returns ROICAnalysisResult with moat_trend (MoatTrendResult)
- `stockvaluefinder/stockvaluefinder/api/capex_routes.py` — POST /api/v1/analyze/capex returns CapitalAllocationResult with overall_grade (A/B/C/D)
- `stockvaluefinder/stockvaluefinder/api/policy_routes.py` — POST /api/v1/analyze/policy/resonance returns ResonanceResult with resonance_score (0-100)

### Domain Models (data structures for component scores)
- `stockvaluefinder/stockvaluefinder/models/roic.py` — ROICAnalysisResult, MoatTrendResult, MoatTrend enum (COMPETITIVE_ADVANTAGE, STABLE, DETERIORATING, INSUFFICIENT_DATA)
- `stockvaluefinder/stockvaluefinder/models/capital_allocation.py` — CapitalAllocationResult, CapitalAllocationGrade enum (A, B, C, D)
- `stockvaluefinder/stockvaluefinder/models/policy.py` — ResonanceResult (resonance_score 0-100, tier, matched_policies)
- `stockvaluefinder/stockvaluefinder/models/enums.py` — ResonanceTier, SpreadClassification, existing enum patterns

### Existing Patterns (follow these)
- `stockvaluefinder/stockvaluefinder/config.py` — Frozen dataclass config pattern; add AlphaConfig with weights
- `stockvaluefinder/stockvaluefinder/repositories/base.py` — Generic BaseRepository pattern for AlphaScoreRepository
- `stockvaluefinder/stockvaluefinder/models/api.py` — ApiResponse[T] generic envelope
- `stockvaluefinder/stockvaluefinder/db/models/` — ORM model patterns (roic.py, policy.py for recent examples)

### Project Context
- `.planning/PROJECT.md` — Current milestone goals, validated requirements, constraints
- `.planning/REQUIREMENTS.md` — ALPHA-01, ALPHA-02, ALPHA-03 requirements
- `.planning/ROADMAP.md` — Phase 12 goal, success criteria, dependencies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- ROIC route handler: Returns ROICAnalysisResult with spread (float) and moat_trend (MoatTrendResult with MoatTrend enum). Alpha endpoint extracts spread for D-02 and moat_trend.trend for D-04.
- CapEx route handler: Returns CapitalAllocationResult with overall_grade (CapitalAllocationGrade A/B/C/D). Alpha endpoint maps grade to 0-100 via D-03.
- Policy resonance route handler: Returns ResonanceResult with resonance_score (0-100 float). Alpha endpoint uses score directly (already 0-100, no mapping needed).
- BaseRepository: Generic CRUD with upsert pattern. Reuse for AlphaScoreRepository.
- ApiResponse[T]: Generic envelope for consistent API responses.
- Existing Alembic migrations (011, 012, 013): Follow pattern for migration 014.

### Established Patterns
- Pure function services: All calculations as stateless pure functions in services/ directory
- Frozen config dataclasses: Add AlphaConfig with frozen=True (weights: 0.40, 0.30, 0.20, 0.10)
- API envelope: ApiResponse[T] with success/data/error fields
- Route pattern: POST /api/v1/analyze/{domain} with dependency injection
- Wave-based plans: Pure functions → Data layer → API wiring (3 plans, 3 waves)

### Integration Points
- ROIC endpoint (POST /api/v1/analyze/roic): Called internally for ROIC-WACC spread + moat trend
- CapEx endpoint (POST /api/v1/analyze/capex): Called internally for capital allocation grade
- Policy resonance endpoint (POST /api/v1/analyze/policy/resonance): Called internally for policy resonance score
- New alpha_routes.py: New API route for composite Alpha endpoint
- New alpha_service.py: New service for normalization, weighting, composite calculation
- New AlphaScoreDB ORM model: New database table for persistence
- Alembic migration 014: Schema for alpha_scores table

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

*Phase: 12-alpha-composite-score*
*Context gathered: 2026-05-06*
