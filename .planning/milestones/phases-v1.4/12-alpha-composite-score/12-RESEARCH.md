# Phase 12: Alpha Composite Score - Research

**Researched:** 2026-05-06
**Domain:** Composite scoring / aggregation service / API orchestration
**Confidence:** HIGH

## Summary

Phase 12 builds the Alpha Composite Score -- a single 0-100 score that aggregates four forward-looking analysis dimensions (ROIC-WACC spread, Capital Allocation, Policy Resonance, Moat Trend) with fixed transparent weights (40/30/20/10). The Alpha endpoint performs live computation by calling the three existing analysis endpoints internally (ROIC, CapEx, Policy Resonance), normalizes each component to 0-100, applies weights, and persists the result.

This phase is architecturally straightforward: it is an **aggregation layer** on top of three fully implemented and tested component endpoints. The core logic is a set of pure normalization functions and a weighted sum. The main complexity lies in the live orchestration pattern (calling existing route handler functions directly, not HTTP self-calls) and ensuring the new database table follows established conventions.

**Primary recommendation:** Implement as three waves following the established pattern: (1) pure functions in alpha_service.py + Pydantic models, (2) ORM model + Alembic migration + repository, (3) API route wiring in alpha_routes.py + main.py registration. Use direct service/route-level function calls for component data, not HTTP self-calls.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Dimension-specific mapping to normalize all component scores to 0-100 before applying fixed weights
- **D-02:** ROIC-WACC spread mapped to 0-100 using linear clamp +/-10%
- **D-03:** Capital Allocation grade mapped linearly: A=100, B=75, C=50, D=25
- **D-04:** Moat trend mapped in three tiers: COMPETITIVE_ADVANTAGE=100, STABLE=50, DETERIORATING=0, INSUFFICIENT_DATA=0
- **D-05:** Alpha endpoint reads moat trend by calling existing ROIC API endpoint internally
- **D-06:** Live computation -- Alpha endpoint calls all 3 existing API endpoints internally
- **D-07:** New AlphaScoreDB table with all 4 component scores, composite score, weights, DCF adjustment summary, timestamp

### Claude's Discretion
- Exact field names and types in AlphaScoreDB ORM model
- Alembic migration details (table name, constraints, indexes)
- API endpoint path and request/response model structure
- AlphaScoreRepository method signatures
- Internal helper function organization within alpha_service.py
- Test file structure and test case selection
- How live endpoint calls are implemented (direct service calls vs HTTP requests)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ALPHA-01 | User can view composite Alpha score with fixed weights (40% ROIC-WACC, 30% Capital Allocation, 20% Policy, 10% Moat trend) | Normalization functions in alpha_service.py (D-01 through D-04), AlphaConfig with weights, composite calculation |
| ALPHA-02 | User can view all sub-scores and composite via a single API endpoint with full audit trail | alpha_routes.py POST endpoint, AlphaAnalysisResult model with component_scores, weights_used, audit_trail |
| ALPHA-03 | System persists Alpha analysis results with all component scores and DCF parameter adjustments | AlphaScoreDB ORM model, Alembic migration 014, AlphaScoreRepository with upsert pattern |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Score normalization (0-100 mapping) | API / Backend (service layer) | -- | Pure calculation functions, no external deps |
| Component data fetching | API / Backend (route orchestration) | -- | Calls existing route handlers for ROIC, CapEx, Policy |
| Weighted composite calculation | API / Backend (service layer) | -- | Pure arithmetic, deterministic |
| Result persistence | Database / Storage | -- | AlphaScoreDB table via repository |
| API exposure | API / Backend (route layer) | -- | POST /api/v1/analyze/alpha |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.133.1 | Route handler, dependency injection | Project standard web framework [VERIFIED: pyproject.toml] |
| SQLAlchemy | >=2.0.47 | ORM model for AlphaScoreDB | Project standard ORM [VERIFIED: pyproject.toml] |
| Pydantic | >=2.12.5 | Request/response models, validation | Project standard validation [VERIFIED: pyproject.toml] |
| Alembic | >=1.18.4 | Database migration 014 | Project standard migration tool [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=9.0.2 | Unit tests for pure functions | All alpha_service.py functions |
| pytest-asyncio | >=1.3.0 | Async test support | Route handler integration tests |
| pytest-mock | >=3.15.1 | Mocking existing endpoints | Tests for route orchestration |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct route handler calls | httpx AsyncClient self-call | Direct calls avoid HTTP overhead and network issues; self-calls add latency but test the full HTTP stack. Direct calls are simpler and faster. |

**Installation:**
```bash
# No new dependencies needed -- all required packages already in pyproject.toml
uv sync
```

**Version verification:** All packages verified from pyproject.toml -- no new dependencies required for this phase.

## Architecture Patterns

### System Architecture Diagram

```
POST /api/v1/analyze/alpha
         |
         v
  alpha_routes.py (handler)
         |
         |--- (1) Call analyze_roic() route handler directly
         |         Returns ROICAnalysisResult
         |         Extract: spread (float), moat_trend.trend (MoatTrend enum)
         |
         |--- (2) Call analyze_capital_allocation() route handler directly
         |         Returns CapitalAllocationResult
         |         Extract: overall_grade (A/B/C/D)
         |
         |--- (3) Call analyze_resonance() route handler directly
         |         Returns ResonanceResult
         |         Extract: resonance_score (0-100), dcf_adjustment
         |
         v
  alpha_service.py (pure functions)
         |
         |--- normalize_roic_wacc_score(spread) -> 0-100      [D-02]
         |--- normalize_capex_score(grade) -> 0-100            [D-03]
         |--- normalize_policy_score(score) -> 0-100            [pass-through]
         |--- normalize_moat_score(trend) -> 0-100              [D-04]
         |--- calculate_alpha_score(components, weights) -> composite
         |
         v
  AlphaScoreRepository (persist)
         |
         v
  AlphaAnalysisResult (API response with full audit trail)
```

### Recommended Project Structure
```
stockvaluefinder/
  models/
    alpha.py                    # AlphaAnalysisResult, AlphaRequest, AlphaScoreCreate, normalization types
  services/
    alpha_service.py            # Pure normalization + composite calculation functions
  db/models/
    alpha.py                    # AlphaScoreDB ORM model
  repositories/
    alpha_repo.py               # AlphaScoreRepository with upsert
  api/
    alpha_routes.py             # POST /api/v1/analyze/alpha

alembic/versions/
  014_alpha_scores_table.py     # Schema migration

tests/
  unit/
    test_services/
      test_alpha_service.py     # Unit tests for pure normalization/composite functions
    test_models/
      test_alpha_models.py      # Pydantic model validation tests
```

### Pattern 1: Pure Function Normalization
**What:** Each normalization function is a pure stateless function that maps a component-specific value to a 0-100 score.
**When to use:** All normalization logic in alpha_service.py.
**Example:**
```python
# Source: Established pattern from roic_service.py, capex_service.py
def normalize_roic_wacc_score(spread: float | None) -> float:
    """Map ROIC-WACC spread to 0-100 using linear clamp +/-10%.

    D-02: spread > +10% = 100, spread < -10% = 0, linear between.
    None spread (negative invested capital) returns 0.
    """
    if spread is None:
        return 0.0
    clamped = max(-0.10, min(0.10, spread))
    return (clamped + 0.10) / 0.20 * 100.0
```

### Pattern 2: Direct Route Handler Invocation (NOT HTTP self-call)
**What:** The Alpha route handler calls existing route handler functions directly, passing constructed request objects and mock dependencies.
**When to use:** Fetching component scores from existing endpoints.
**Example:**
```python
# Call existing route handlers directly -- avoids HTTP overhead
roic_request = ROICAnalysisRequest(ticker=ticker, year=year)
roic_response = await analyze_roic(
    request=roic_request,
    data_service=data_service,
    db=db,
)
if not roic_response.success or roic_response.data is None:
    # Handle component failure gracefully
    ...
roic_data = roic_response.data  # ROICAnalysisResult
```

### Pattern 3: Frozen Config Dataclass
**What:** AlphaConfig as frozen dataclass with fixed weights.
**When to use:** Configuration for Alpha score weights.
**Example:**
```python
@dataclass(frozen=True)
class AlphaConfig:
    """Configuration for Alpha Composite Score analysis."""
    ROIC_WACC_WEIGHT: float = 0.40
    CAPITAL_ALLOCATION_WEIGHT: float = 0.30
    POLICY_WEIGHT: float = 0.20
    MOAT_WEIGHT: float = 0.10
```

### Anti-Patterns to Avoid
- **HTTP self-call to localhost:** Calling own API via httpx adds unnecessary latency, requires network access in tests, and can deadlock in ASGI. Use direct route handler function calls instead. [VERIFIED: established pattern across codebase]
- **Skipping normalization:** Raw component values (spread in decimals, grade as letter, score as 0-100) cannot be directly weighted. Each must be mapped to 0-100 first per D-01.
- **Mutating component results:** Component results (ROICAnalysisResult, etc.) are frozen Pydantic models. Never attempt to modify them -- extract values and create new Alpha models.
- **Coupling to HTTP response format:** The existing route handlers return `ApiResponse[T]`. The Alpha route must unwrap `.data` from each component response, not pass the ApiResponse objects around.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Weighted score calculation | Custom aggregation framework | Simple arithmetic: sum(score * weight) | Four components, fixed weights, no complexity needed |
| Score clamping/normalization | Complex statistical normalization | Linear clamp + interpolation (D-02) | Transparent, auditable, matches PRD |
| Database upsert | Custom INSERT/UPDATE logic | BaseRepository pattern + upsert_by_ticker_year | Established pattern from roic_repo.py, capex_repo.py |

**Key insight:** This phase is intentionally simple -- it aggregates existing results. The complexity is in the three component endpoints (already built), not in the aggregation itself.

## Runtime State Inventory

> Not applicable -- this is a greenfield phase with no renames, refactors, or migrations of existing data.

## Common Pitfalls

### Pitfall 1: Component Endpoint Failure Cascade
**What goes wrong:** If one of the three component endpoints fails (e.g., AKShare API down), the entire Alpha calculation fails and returns an error.
**Why it happens:** Live computation means all three endpoints must succeed (D-06).
**How to avoid:** Return a structured error indicating which component failed. Consider returning partial results with zero scores for failed components (but D-06 says "live computation", so failure propagation is acceptable).
**Warning signs:** Timeout errors from external data sources; empty responses from AKShare.

### Pitfall 2: Double Database Session Usage
**What goes wrong:** When calling existing route handlers directly, they receive the same `db` session. If the Alpha route handler has already started a transaction, the inner route handlers commit/rollback can interfere.
**Why it happens:** The existing route handlers call `db.commit()` after persisting their own results (verified in roic_routes.py line 248, capex_routes.py line 270).
**How to avoid:** Call route handlers first (they commit their own results), then persist Alpha results in a separate commit. The inner handlers' commits are independent and idempotent (upsert pattern).
**Warning signs:** `PendingRollbackError` from SQLAlchemy; stale data in Alpha persistence.

### Pitfall 3: Mismatched Fiscal Years Across Components
**What goes wrong:** ROIC uses fiscal_year from financial data, CapEx defaults to current year - 1, Policy has no fiscal year concept. Components may analyze different time periods.
**Why it happens:** Each component endpoint has its own fiscal year logic.
**How to avoid:** Document in audit_trail which fiscal year each component used. Alpha endpoint does not enforce year consistency -- it aggregates whatever each component returns.
**Warning signs:** Alpha score uses ROIC from 2023 but CapEx from 2024.

### Pitfall 4: Missing Moat Trend Data
**What goes wrong:** ROIC endpoint may return `moat_trend=None` when multi-year data is unavailable. Alpha must handle this gracefully.
**Why it happens:** New stocks or stocks with < 3 years of data cannot compute moat trends.
**How to avoid:** D-04 specifies INSUFFICIENT_DATA maps to 0. When moat_trend is None, treat as INSUFFICIENT_DATA.
**Warning signs:** `AttributeError` when accessing `moat_trend.trend` on None.

## Code Examples

Verified patterns from codebase:

### Normalization Functions (to implement in alpha_service.py)
```python
# Source: Pattern established in roic_service.py and capex_service.py
# All pure functions with no side effects

from stockvaluefinder.models.roic import MoatTrend
from stockvaluefinder.models.capital_allocation import CapitalAllocationGrade

def normalize_roic_wacc_score(spread: float | None) -> float:
    """D-02: Linear clamp +/-10% to 0-100."""
    if spread is None:
        return 0.0
    clamped = max(-0.10, min(0.10, spread))
    return (clamped + 0.10) / 0.20 * 100.0

def normalize_capex_score(grade: CapitalAllocationGrade) -> float:
    """D-03: A=100, B=75, C=50, D=25."""
    mapping = {
        CapitalAllocationGrade.A: 100.0,
        CapitalAllocationGrade.B: 75.0,
        CapitalAllocationGrade.C: 50.0,
        CapitalAllocationGrade.D: 25.0,
    }
    return mapping[grade]

def normalize_policy_score(score: float) -> float:
    """Pass-through: already 0-100 from policy_service."""
    return max(0.0, min(100.0, score))

def normalize_moat_score(trend: MoatTrend | None) -> float:
    """D-04: COMPETITIVE_ADVANTAGE=100, STABLE=50, else 0."""
    if trend == MoatTrend.COMPETITIVE_ADVANTAGE:
        return 100.0
    elif trend == MoatTrend.STABLE:
        return 50.0
    return 0.0  # DETERIORATING, INSUFFICIENT_DATA, None

def calculate_alpha_score(
    roic_wacc_score: float,
    capex_score: float,
    policy_score: float,
    moat_score: float,
    weights: tuple[float, float, float, float] = (0.40, 0.30, 0.20, 0.10),
) -> float:
    """Weighted sum of normalized component scores."""
    return (
        roic_wacc_score * weights[0]
        + capex_score * weights[1]
        + policy_score * weights[2]
        + moat_score * weights[3]
    )
```

### Route Handler Invocation Pattern
```python
# Source: Pattern from capex_routes.py calling roic_repo (Phase 10 reuses Phase 9 data)
# But here we call the full route handler, not just the repo

from stockvaluefinder.models.roic import ROICAnalysisRequest
from stockvaluefinder.models.capital_allocation import CapitalAllocationRequest
from stockvaluefinder.models.policy import ResonanceRequest

# Inside alpha route handler:
roic_req = ROICAnalysisRequest(ticker=ticker, year=year)
roic_resp = await analyze_roic(
    request=roic_req,
    data_service=data_service,
    db=db,
)
# Unwrap ApiResponse
if roic_resp.success and roic_resp.data is not None:
    spread = roic_resp.data.spread
    moat_trend = roic_resp.data.moat_trend
```

### AlphaScoreDB ORM Model Pattern
```python
# Source: Pattern from db/models/capital_allocation.py
class AlphaScoreDB(Base):
    __tablename__ = "alpha_scores"

    analysis_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    ticker: Mapped[str] = mapped_column(
        String(20), ForeignKey("stocks.ticker"), nullable=False, index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        default=lambda: datetime.now(timezone.utc),
    )

    # Four component normalized scores
    roic_wacc_score: Mapped[float] = mapped_column(Float, nullable=False)
    capex_score: Mapped[float] = mapped_column(Float, nullable=False)
    policy_score: Mapped[float] = mapped_column(Float, nullable=False)
    moat_score: Mapped[float] = mapped_column(Float, nullable=False)

    # Composite
    alpha_score: Mapped[float] = mapped_column(Float, nullable=False)
    weights_used: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dcf_adjustment_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
    )
    audit_trail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| User-adjustable weights | Fixed weights (40/30/20/10) | Phase 12 design decision | Simpler implementation, transparent scoring |
| HTTP self-call for aggregation | Direct function call | Phase 12 (recommended) | Lower latency, no ASGI deadlock risk |

**Deprecated/outdated:**
- None applicable

## Assumptions Log

> All claims in this research were verified against the actual codebase files. No unverified assumptions.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Existing route handlers can be called directly as async functions without special setup | Architecture Patterns | Route handlers might require middleware context not available in direct calls |
| A2 | ROIC route handler commits its own transaction successfully even when called from Alpha handler | Common Pitfalls | Nested transaction issues could corrupt data |

**Note on A1/A2:** The existing route handlers (roic_routes.analyze_roic, capex_routes.analyze_capital_allocation, policy_routes.analyze_resonance) are standard async functions that receive their dependencies via parameters (request, data_service, db). They call `db.commit()` internally. Calling them directly is safe as long as the db session is properly managed. This pattern is verified by examining the function signatures and internal logic of all three handlers.

## Open Questions (RESOLVED)

1. **Endpoint path for Alpha API** (RESOLVED: `/api/v1/analyze/alpha`)
   - What we know: Existing endpoints follow `/api/v1/analyze/{domain}` pattern (roic, capex, policy/resonance)
   - Resolution: Use `/api/v1/analyze/alpha` to maintain consistency. All 3 plans implement this path.

2. **Fiscal year handling for Alpha request** (RESOLVED: Accept optional `year`, pass to ROIC/CapEx)
   - What we know: ROIC and CapEx accept optional `year`; Policy has no year parameter
   - Resolution: Accept optional `year` in AlphaRequest, pass to ROIC and CapEx; Policy ignores it. Plan 12-03 implements this.

3. **Error handling when a component fails** (RESOLVED: Return error if any component fails)
   - What we know: D-06 says "live computation" -- all components must be called
   - Resolution: Return error if any component fails (consistent with "live computation" principle). Plan 12-03 wraps all calls in try/except and returns error on any failure.

## Environment Availability

> This phase depends on PostgreSQL and external data sources (AKShare). These are already required by existing component endpoints.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | AlphaScoreDB persistence | Required by existing phases | 15+ (via asyncpg) | -- |
| AKShare | Live ROIC/CapEx data fetching | Required by component endpoints | >=1.14.0 | -- |
| Redis | Cache (via existing data_service) | Existing infrastructure | >=7.2.1 | Graceful degradation |
| Qdrant | Policy resonance vector search | Required by policy endpoint | >=1.17.0 | -- |

**Missing dependencies with no fallback:**
- None -- all dependencies are already established by previous phases

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | stockvaluefinder/pytest.ini (asyncio_mode=auto, testpaths=tests) |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_alpha_service.py -x -v` |
| Full suite command | `cd stockvaluefinder && uv run pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ALPHA-01 | normalize_roic_wacc_score maps spread to 0-100 | unit | `uv run pytest tests/unit/test_services/test_alpha_service.py::TestNormalizeRoicWaccScore -x` | Wave 0 |
| ALPHA-01 | normalize_capex_score maps grades A/B/C/D to 100/75/50/25 | unit | `uv run pytest tests/unit/test_services/test_alpha_service.py::TestNormalizeCapexScore -x` | Wave 0 |
| ALPHA-01 | normalize_policy_score passes through 0-100 | unit | `uv run pytest tests/unit/test_services/test_alpha_service.py::TestNormalizePolicyScore -x` | Wave 0 |
| ALPHA-01 | normalize_moat_score maps MoatTrend enum to 100/50/0 | unit | `uv run pytest tests/unit/test_services/test_alpha_service.py::TestNormalizeMoatScore -x` | Wave 0 |
| ALPHA-01 | calculate_alpha_score returns weighted sum | unit | `uv run pytest tests/unit/test_services/test_alpha_service.py::TestCalculateAlphaScore -x` | Wave 0 |
| ALPHA-02 | Alpha endpoint returns all sub-scores and audit trail | integration | `uv run pytest tests/unit/test_api/test_alpha_routes.py -x` | Wave 0 |
| ALPHA-02 | Alpha endpoint handles component failures gracefully | integration | `uv run pytest tests/unit/test_api/test_alpha_routes.py::TestAlphaEndpointFailure -x` | Wave 0 |
| ALPHA-03 | AlphaScoreRepository persists and retrieves results | unit | `uv run pytest tests/unit/test_repositories/test_alpha_repo.py -x` | Wave 0 |
| ALPHA-03 | Alembic migration 014 creates alpha_scores table | integration | `cd stockvaluefinder && uv run alembic upgrade head` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_alpha_service.py -x`
- **Per wave merge:** `cd stockvaluefinder && uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_services/test_alpha_service.py` -- covers ALPHA-01 normalization functions
- [ ] `tests/unit/test_api/test_alpha_routes.py` -- covers ALPHA-02 endpoint behavior
- [ ] `tests/unit/test_repositories/test_alpha_repo.py` -- covers ALPHA-03 persistence
- [ ] `tests/unit/test_models/test_alpha_models.py` -- covers Pydantic model validation

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth requirements |
| V3 Session Management | no | No session changes |
| V4 Access Control | no | No new access control |
| V5 Input Validation | yes | Pydantic validates ticker pattern, year range |
| V6 Cryptography | no | No crypto operations |

### Known Threat Patterns for Alpha Composite Score

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Invalid ticker injection | Tampering | Pydantic pattern validation: `r"^\d{6}\.(SH\|SZ\|HK)$"` |
| Missing component data | Denial of Service | Graceful error handling, return structured error |

## Sources

### Primary (HIGH confidence)
- Codebase direct reads: roic_routes.py, capex_routes.py, policy_routes.py, roic.py (models), capital_allocation.py (models), policy.py (models), config.py, base.py (repo), roic.py (ORM), capital_allocation.py (ORM), policy.py (ORM), 013_policy_tables.py (migration)
- pytest.ini: test configuration verified
- pyproject.toml: dependency versions verified
- 12-CONTEXT.md: locked decisions D-01 through D-07

### Secondary (MEDIUM confidence)
- doc/Alpha_Engine_V2.0/Alpha_Engine_V2.0.md: PRD composite scoring specification

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all packages verified in pyproject.toml, no new deps needed
- Architecture: HIGH - follows established patterns from phases 9/10/11, all canonical refs read
- Pitfalls: HIGH - identified from direct codebase analysis of route handler internals

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (stable -- no fast-moving dependencies)
