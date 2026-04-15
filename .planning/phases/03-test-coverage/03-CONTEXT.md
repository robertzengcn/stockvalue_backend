# Phase 3: Test Coverage - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Achieve 80%+ test coverage across all core services and API endpoints. The phase adds both unit tests (for pure calculation functions in risk/valuation/yield/data services) and integration tests (for API routes with TestClient + real test database + mocked external services). Extends existing test files rather than rewriting them.

Scope: Unit tests for all services (risk, valuation, yield, data, narrative), utils (errors, validators, cache), repository layer, and API route integration tests. Does NOT include: RAG pipeline tests (scaffolding), agent tests (scaffolding), calculation_sandbox tests (TODO stub), or E2E user flow tests.

</domain>

<decisions>
## Implementation Decisions

### Test scope & priority

- **D-01:** Business-critical first priority order: risk_service → valuation_service → yield_service → data_service → utils/repositories → integration tests
- **D-02:** Full coverage push — test everything with implementation code, not just the 4 core services in ROADMAP. Includes narrative_service (with mocked LLM), utils (errors, validators, cache), all 7 repositories, and all 3 API routes (risk, valuation, yield)
- **D-03:** Extend only — assume existing tests are correct. Only add new tests for uncovered code paths. Do not rewrite or review existing test files

### Integration test approach

- **D-04:** Full E2E with database — test the complete request→route→service→repo→DB→response cycle for all 3 API endpoints. Use FastAPI TestClient + real async database session + mocked external data sources (AKShare/efinance/Tushare)
- **D-05:** Separate test database on the same PostgreSQL instance — use `stockvaluefinder_test` database. Create/drop tables via Alembic in test fixtures. Requires PostgreSQL running but no Docker overhead
- **D-06:** Narrative service tested with mocked LLM responses — verify service handles responses correctly, graceful fallback to None on errors, and prompt formatting. Do not test LLM output quality

### Test data & fixtures

- **D-07:** Shared conftest factory pattern — create factory functions in conftest.py (e.g., `make_financial_report(ticker, year, **overrides)`) returning realistic financial data dicts. Shared across all test files, tests customize specific fields via kwargs
- **D-08:** 600519.SH (Kweichow Moutai) as primary test stock — well-known CSI 300 constituent with stable financials, enabling manual verification of calculation results. Use a second stock for edge case testing

### Claude's Discretion

- Exact factory function signatures and default values
- Which second stock to use for edge case testing
- conftest.py file organization (single vs multiple files)
- Test naming conventions within files
- Specific mock return values for external service mocks

### Folded Todos

None.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Testing infrastructure
- `stockvaluefinder/pytest.ini` — pytest configuration (asyncio mode, coverage settings)
- `stockvaluefinder/tests/unit/` — existing test directory structure and patterns
- `.planning/codebase/TESTING.md` — test infrastructure analysis, coverage gaps, existing patterns

### Source files requiring tests (priority order)
- `stockvaluefinder/stockvaluefinder/services/risk_service.py` — M-Score (8%), F-Score, anomaly detection (533 lines, 229 statements)
- `stockvaluefinder/stockvaluefinder/services/valuation_service.py` — DCF, WACC, terminal value (25% coverage)
- `stockvaluefinder/stockvaluefinder/services/yield_service.py` — dividend yield, yield gap (41% coverage)
- `stockvaluefinder/stockvaluefinder/external/data_service.py` — multi-source fallback, field mapping (1187 lines)
- `stockvaluefinder/stockvaluefinder/services/narrative_service.py` — LLM narrative generation (21% coverage)
- `stockvaluefinder/stockvaluefinder/utils/validators.py` — input validation (0% coverage)
- `stockvaluefinder/stockvaluefinder/utils/errors.py` — exception hierarchy (34% coverage)
- `stockvaluefinder/stockvaluefinder/utils/cache.py` — Redis CacheManager (16% coverage)
- `stockvaluefinder/stockvaluefinder/repositories/` — all 7 repository files (24-42% coverage)
- `stockvaluefinder/stockvaluefinder/api/risk_routes.py` — risk analysis endpoint
- `stockvaluefinder/stockvaluefinder/api/valuation_routes.py` — DCF valuation endpoint
- `stockvaluefinder/stockvaluefinder/api/yield_routes.py` — yield gap endpoint

### Existing test files (to extend, not rewrite)
- `stockvaluefinder/tests/unit/test_services/test_risk_service.py` — 33KB, existing risk tests
- `stockvaluefinder/tests/unit/test_services/test_valuation_service.py` — existing valuation tests
- `stockvaluefinder/tests/unit/test_services/test_yield_service.py` — existing yield tests
- `stockvaluefinder/tests/unit/test_external/test_data_service.py` — existing data service tests
- `stockvaluefinder/tests/unit/test_external/test_data_service_cache.py` — existing cache tests
- `stockvaluefinder/tests/unit/test_api/test_risk_routes.py` — existing risk route tests
- `stockvaluefinder/tests/unit/test_api/test_dependencies.py` — existing DI tests
- `stockvaluefinder/tests/unit/test_services/test_narrative_service.py` — existing narrative tests
- `stockvaluefinder/tests/unit/test_services/test_narrative_prompts.py` — existing prompt tests
- `stockvaluefinder/tests/unit/test_utils/test_cache_utils.py` — existing cache util tests

### Phase 1 context (M-Score calculation logic)
- `.planning/phases/01-m-score-real-calculation/01-CONTEXT.md` — M-Score field mapping table, calculation function design, audit trail format

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pytest-asyncio` already configured — all async test patterns established
- `pytest-mock` available — mocking pattern for external services already used in existing tests
- `hypothesis` available — property-based testing infrastructure ready if needed
- `pytest-cov` configured — coverage reporting already works
- `TestClient` from FastAPI — standard pattern for API integration tests
- Existing conftest.py files — patterns for fixtures already established

### Established Patterns
- Unit tests in `tests/unit/test_services/` for services, `tests/unit/test_external/` for data clients, `tests/unit/test_api/` for routes
- Async test functions using `async def test_` with `pytest-asyncio`
- External API calls mocked with `pytest-mock` (mocker fixture)
- Pure function services mean unit tests are straightforward: pass inputs, assert outputs
- Data source fallback chain tested via mocking each source's return values

### Integration Points
- Test database: need `stockvaluefinder_test` database on localhost:5433 (same PostgreSQL instance as dev)
- Test fixtures: need `get_db` override in conftest.py to point to test database
- Alembic migrations: run against test database to create/drop schema
- Environment: `DATABASE_URL` override needed for test session

### Current Coverage Snapshot
| Module | Coverage | Gap Size |
|--------|----------|----------|
| risk_service.py | 8% | 211 statements uncovered |
| cache.py | 16% | 143 statements uncovered |
| narrative_service.py | 21% | 73 statements uncovered |
| valuation_service.py | 25% | 45 statements uncovered |
| yield_service.py | 41% | 16 statements uncovered |
| validators.py | 0% | 42 statements uncovered |
| errors.py | 34% | 25 statements uncovered |
| Repositories | 24-42% | Multiple files |
| **Total** | **34%** | **2166 statements uncovered** |

</code_context>

<specifics>
## Specific Ideas

- Use 600519.SH (Kweichow Moutai) financials as the "golden dataset" — known stock with publicly available financials for manual verification
- M-Score test data should include two consecutive years of financial reports (as required by the year-over-year calculation in Phase 1)
- Edge cases to cover: division by zero in financial ratios, missing fields triggering DataValidationError, zero revenue, negative cash flow, extreme values
- Integration tests should verify the full `ApiResponse[T]` envelope structure (success, data, error fields)
- Cache tests already partially written — extend for uncovered decorator patterns and TTL logic

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-test-coverage*
*Context gathered: 2026-04-16*
