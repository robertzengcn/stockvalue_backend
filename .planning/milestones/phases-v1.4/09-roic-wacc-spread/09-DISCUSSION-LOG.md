# Phase 9: ROIC-WACC Spread Analysis - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 09-ROIC-WACC Spread Analysis
**Areas discussed:** WACC approach, Multi-year data flow, Moat trend rules, Edge case policy

---

## WACC Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing | Add optional debt_weight, cost_of_debt, tax_rate params with defaults of 0. Backward compatible. | ✓ |
| New separate function | Keep calculate_wacc untouched, create calculate_true_wacc() | |
| Refactor DCF too | Refactor DCF to also use true WACC. Changes existing behavior. | |

**User's choice:** Extend existing (backward compatible)
**Notes:** Existing DCF calls continue to work unchanged. New ROIC-WACC calls pass debt params.

| Option | Description | Selected |
|--------|-------------|----------|
| Implied from financials | finance_expense / total_interest_bearing_debt from AKShare | ✓ |
| Fixed spread over Rf | Rf + 2% spread. Simpler but less accurate. | |

**User's choice:** Implied from financials (Recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Full breakdown | Show Ke, Kd, D/E ratio, tax rate, weights in response | ✓ |
| Simple: value only | Just WACC value and spread. Components in audit_trail only. | |

**User's choice:** Full breakdown

---

## Multi-Year Data Flow

| Option | Description | Selected |
|--------|-------------|----------|
| Extend AKShareClient | Add fetch_multi_year_financials(ticker, years=3) to existing client | ✓ |
| New ROIC data service | Create separate ROICDataService for ROIC-specific fetching | |

**User's choice:** Extend AKShareClient

| Option | Description | Selected |
|--------|-------------|----------|
| Redis cached | Cache multi-year data with 24h TTL, consistent with existing pattern | ✓ |
| Fetch on demand | Fetch fresh each call. Simpler but 3x API calls. | |

**User's choice:** Redis cached

---

## Moat Trend Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Three-state | Widening / Narrowing / Stable with 0.005/yr threshold | ✓ |
| Binary (moat/not) | Just widening or not. Simpler classification. | |

**User's choice:** Three-state with slope > 0.005/yr threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Generic labels | Competitive Advantage / Deteriorating / Stable | ✓ |
| PRD-style moat types | Intangible Asset Moat / Scale Moat based on absolute ROIC | |

**User's choice:** Generic labels (no moat type heuristics at this stage)

---

## Edge Case Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Flag as N/A | Return ROIC = None with flag. Safe, no misleading values. | ✓ |
| Compute anyway | Return negative ROIC. Mathematically correct but misleading. | |

**User's choice:** Flag as N/A

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-detect | From stock.sector field in database. Transparent to user. | ✓ |
| User-specified | User passes sector_type in API request. | |

**User's choice:** Auto-detect from stock.sector

| Option | Description | Selected |
|--------|-------------|----------|
| OPERATE_PROFIT vs EBIT | Financial: OPERATE_PROFIT*(1-T), Non-fin: (TOTAL_PROFIT+FINANCE_EXPENSE)*(1-T) | ✓ |
| Different formula | Let me specify a different approach. | |

**User's choice:** OPERATE_PROFIT for financials, EBIT-based for non-financials

---

## Claude's Discretion

- Exact API endpoint path and request/response model structure
- New ORM model field names and Alembic migration details
- Internal helper function organization within roic_service.py
- Test file structure and test case selection

## Deferred Ideas

None — discussion stayed within phase scope.
