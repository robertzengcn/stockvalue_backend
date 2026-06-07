# Phase 31: Persistence & API Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-07
**Phase:** 31-persistence-api-integration
**Areas discussed:** Persistence scope, API response design, Migration strategy, Narrative integration

---

## Persistence Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full separation | Two new tables for raw pledge data + JSONB on risk_scores for computed results | ✓ |
| JSONB-only on risk_scores | Only JSONB columns on risk_scores, no separate tables | |

**User's choice:** Full separation (Recommended)
**Notes:** Matches DB-01/DB-02 (separate tables) and DB-03 (JSONB on risk_scores). Clean separation between raw data history and analysis output.

---

## API Response Design

| Option | Description | Selected |
|--------|-------------|----------|
| Embed in existing /analyze/risk | Add pledge_risk fields to existing response, include_pledge_risk param | ✓ |
| Separate /analyze/pledge-risk endpoint | New endpoint for pledge data, requires two API calls | |

**User's choice:** Embed in existing /analyze/risk (Recommended)
**Notes:** Single API call returns everything. include_pledge_risk=true default. Matches API-01/API-02/API-03.

---

## Migration Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Single migration 021 | Creates new tables + adds nullable JSONB columns to risk_scores atomically | ✓ |
| Two separate migrations | 021 for tables, 022 for risk_scores columns | |

**User's choice:** Single migration 021 (Recommended)
**Notes:** Simpler, atomic. Existing rows get NULL values naturally via nullable columns.

---

## Narrative Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing risk prompt | Add pledge paragraph to build_risk_prompt() with guardrails | ✓ |
| Separate narrative call | Generate pledge narrative separately, two LLM calls | |

**User's choice:** Extend existing risk prompt (Recommended)
**Notes:** Single LLM call. Guardrails: no fabrication, "unavailable" when missing, omit closeout when null. Matches NARR-01/NARR-02/NARR-03/NARR-04.

---

## Claude's Discretion

- Exact ORM model field types and column definitions
- Repository method signatures and upsert/replace-all logic
- Response model structure for pledge_risk object
- Alembic migration file structure
- Narrative prompt text and guardrail phrasing
- Error handling for pledge data fetch failures

## Deferred Ideas

None -- discussion stayed within phase scope.
