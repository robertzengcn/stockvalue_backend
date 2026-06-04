# Phase 12: Alpha Composite Score - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-06
**Phase:** 12-alpha-composite-score
**Areas discussed:** Score normalization, Moat trend data source, Orchestration approach, Persistence model

---

## Score Normalization (D-01 through D-04)

### Normalization Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Dimension-specific mapping | Each dimension uses its own mapping logic appropriate to its data type | ✓ |
| Universal linear scale | All dimensions mapped to 0-100 with same linear approach | |
| Z-score standardization | Statistical normalization based on distribution | |

**User's choice:** Dimension-specific mapping (Recommended)

### ROIC-WACC Spread Mapping (D-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Linear clamp ±10% | spread > +10% = 100, < -10% = 0, linear between | ✓ |
| Sigmoid mapping | Smooth S-curve, compressed at extremes | |
| Tiered bands | Fixed ranges (e.g., >8%=100, 4-8%=75, 0-4%=50, <0%=25) | |

**User's choice:** Linear clamp ±10% (Recommended)

### Capital Allocation Grade Mapping (D-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Linear 100/75/50/25 | A=100, B=75, C=50, D=25. Even 25-point steps | ✓ |
| Weighted 100/80/50/20 | A=100, B=80, C=50, D=20. Penalizes poor allocation | |
| Weighted 100/70/40/10 | A=100, B=70, C=40, D=10. Wider gaps | |

**User's choice:** Linear 100/75/50/25 (Recommended)

### Moat Trend Mapping (D-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Three-tier 100/50/0 | COMPETITIVE_ADVANTAGE=100, STABLE=50, DETERIORATING=0, INSUFFICIENT_DATA=0 | ✓ |
| Four-tier 100/50/25/0 | Gives some credit for deteriorating | |
| Even 100/67/33/0 | 33-point steps across data-bearing tiers | |

**User's choice:** Three-tier 100/50/0 (Recommended)

---

## Moat Trend Data Source (D-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Read from ROIC endpoint | Calls existing ROIC API internally. Fresh computation, adds latency | ✓ |
| Read from ROIC DB table | Reads persisted ROICResultDB. Fast but stale | |
| User input parameter | Caller provides moat_trend. Pushes complexity to caller | |

**User's choice:** Read from ROIC endpoint (Recommended)

---

## Orchestration Approach (D-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Live computation | Calls all 3 existing endpoints internally. Always up-to-date | ✓ |
| Cached DB reads | Reads component scores from database tables. Fast but stale | |
| DB-first with live fallback | Try DB first, fall back to live if missing. Complex | |

**User's choice:** Live computation (Recommended)

---

## Persistence Model (D-07)

| Option | Description | Selected |
|--------|-------------|----------|
| New AlphaScoreDB table | All 4 component scores, composite, weights, timestamp. Clean separation | ✓ |
| Extend ROICResultDB | Alpha column on existing table. Couples alpha to ROIC | |
| JSONB on valuation_results | Flexible but less structured | |

**User's choice:** New AlphaScoreDB table (Recommended)

---

## Claude's Discretion

- Exact field names and types in AlphaScoreDB ORM model
- Alembic migration details (table name, constraints, indexes)
- API endpoint path and request/response model structure
- AlphaScoreRepository method signatures
- Internal helper function organization within alpha_service.py
- Test file structure and test case selection
- How live endpoint calls are implemented (direct service calls vs HTTP requests)

## Deferred Ideas

None — discussion stayed within phase scope.
