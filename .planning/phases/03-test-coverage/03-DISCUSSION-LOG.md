# Phase 3: Test Coverage - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 03-test-coverage
**Areas discussed:** Test scope & priority, Integration test approach, Test data & fixtures

---

## Test scope & priority

| Option | Description | Selected |
|--------|-------------|----------|
| Business-critical first | Start with risk_service (8% coverage) since M-Score fraud detection is core value proposition | ✓ |
| Biggest gaps first | Start with largest coverage gaps regardless of business importance | |
| Pure functions first | Cover all pure calculation services first since they're easiest to test | |
| ROADMAP order | Follow TEST-01 through TEST-06 in order | |

**User's choice:** Business-critical first
**Notes:** Priority order: risk_service → valuation_service → yield_service → data_service → utils/repositories → integration tests

| Option | Description | Selected |
|--------|-------------|----------|
| Core 4 services only | Focus on risk, valuation, yield, data_service as specified in ROADMAP success criteria | |
| Core services + utils | Add utils (errors, validators, cache) to the 4 core services | |
| Full coverage push | Test everything with implementation code including narrative, utils, repos, API routes | ✓ |

**User's choice:** Full coverage push
**Notes:** Includes narrative_service (mocked LLM), utils, repositories, and all API routes

| Option | Description | Selected |
|--------|-------------|----------|
| Extend only | Assume existing tests correct, only add new tests for uncovered paths | ✓ |
| Review + extend | Review existing tests for quality gaps, fix issues, then extend | |

**User's choice:** Extend only
**Notes:** Do not rewrite existing test files — only add tests for uncovered code paths

---

## Integration test approach

| Option | Description | Selected |
|--------|-------------|----------|
| Full E2E with DB | Test complete request→route→service→repo→DB→response cycle with TestClient | ✓ |
| Service-layer integration only | Test route→service→mocked repo, skip actual database | |
| Both API E2E + repo tests | Full E2E for API + separate repository-level tests with real DB | |

**User's choice:** Full E2E with DB
**Notes:** Use FastAPI TestClient + real async DB session + mocked external data sources

| Option | Description | Selected |
|--------|-------------|----------|
| Separate test database | Use stockvaluefinder_test on same PostgreSQL instance | ✓ |
| SQLite in-memory | Faster but schema differences (no JSONB, no asyncpg) | |
| Docker PostgreSQL | Most isolated but slowest setup | |

**User's choice:** Separate test database
**Notes:** Create/drop tables via Alembic in test fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Mock LLM responses | Verify service behavior with canned responses, test graceful fallback | ✓ |
| Skip narrative tests | Don't test LLM-dependent code | |

**User's choice:** Mock LLM responses
**Notes:** Verify service handles responses correctly, graceful fallback to None on errors

---

## Test data & fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Shared conftest factories | Factory functions in conftest.py returning realistic data dicts with override kwargs | ✓ |
| Per-test inline data | Each test defines its own data inline | |
| Property-based (hypothesis) | Generate random financial data within valid ranges | |

**User's choice:** Shared conftest factories
**Notes:** e.g., `make_financial_report(ticker, year, **overrides)` — shared across all test files

| Option | Description | Selected |
|--------|-------------|----------|
| 600519.SH (Moutai) as primary | Well-known CSI 300 stock with stable financials for manual verification | ✓ |
| Fabricated generic data | Use generic tickers with fabricated but realistic data | |

**User's choice:** 600519.SH as primary test stock
**Notes:** Enables manual verification of calculation results against known financial data

---

## Claude's Discretion

- Exact factory function signatures and default values
- Which second stock to use for edge case testing
- conftest.py file organization (single vs multiple files)
- Test naming conventions within files
- Specific mock return values for external service mocks

## Deferred Ideas

None — discussion stayed within phase scope.
