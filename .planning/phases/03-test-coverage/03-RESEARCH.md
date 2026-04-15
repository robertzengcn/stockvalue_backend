# Phase 3: Test Coverage - Research

**Researched:** 2026-04-16
**Domain:** Python testing (pytest, pytest-asyncio, FastAPI TestClient, SQLAlchemy async testing)
**Confidence:** HIGH

## Summary

This phase adds comprehensive test coverage to achieve 80%+ across all core services, utilities, repositories, and API endpoints. The codebase currently sits at 34% coverage (2166 of 3293 statements uncovered) with 223 existing tests. The primary challenge is closing the 46-percentage-point gap across 15+ source files while maintaining the established testing patterns (hypothesis property-based tests, pytest-asyncio async tests, pytest-mock for mocking).

The codebase uses pure function services (risk_service, valuation_service, yield_service) that are straightforward to unit test -- pass inputs, assert outputs. Integration tests require FastAPI TestClient with mocked external services and a test PostgreSQL database (currently unavailable on localhost:5433, which must be resolved before integration test implementation).

**Primary recommendation:** Write unit tests first (services, utils) in priority order D-01, then set up test database infrastructure, then implement integration tests. Pure function tests require zero external dependencies and will provide the largest coverage boost per effort.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Business-critical first priority order: risk_service -> valuation_service -> yield_service -> data_service -> utils/repositories -> integration tests
- **D-02:** Full coverage push -- test everything with implementation code, not just the 4 core services in ROADMAP. Includes narrative_service (with mocked LLM), utils (errors, validators, cache), all 7 repositories, and all 3 API routes (risk, valuation, yield)
- **D-03:** Extend only -- assume existing tests are correct. Only add new tests for uncovered code paths. Do not rewrite or review existing test files
- **D-04:** Full E2E with database -- test the complete request->route->service->repo->DB->response cycle for all 3 API endpoints. Use FastAPI TestClient + real async database session + mocked external data sources (AKShare/efinance/Tushare)
- **D-05:** Separate test database on the same PostgreSQL instance -- use `stockvaluefinder_test` database. Create/drop tables via Alembic in test fixtures. Requires PostgreSQL running but no Docker overhead
- **D-06:** Narrative service tested with mocked LLM responses -- verify service handles responses correctly, graceful fallback to None on errors, and prompt formatting. Do not test LLM output quality
- **D-07:** Shared conftest factory pattern -- create factory functions in conftest.py (e.g., `make_financial_report(ticker, year, **overrides)`) returning realistic financial data dicts. Shared across all test files, tests customize specific fields via kwargs
- **D-08:** 600519.SH (Kweichow Moutai) as primary test stock -- well-known CSI 300 constituent with stable financials, enabling manual verification of calculation results. Use a second stock for edge case testing

### Claude's Discretion
- Exact factory function signatures and default values
- Which second stock to use for edge case testing
- conftest.py file organization (single vs multiple files)
- Test naming conventions within files
- Specific mock return values for external service mocks

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEST-01 | Unit tests for risk_service (M-Score calculation, F-Score, anomaly detection) with 80%+ coverage | risk_service.py has 833 lines, 8 public functions + 1 orchestrator + 2 helper classes. All are pure functions. Key functions: calculate_beneish_m_score, calculate_mscore_indices (8 indices from raw financials), calculate_piotroski_f_score (9 signals), detect_存贷双高, calculate_goodwill_ratio, detect_profit_cash_divergence, determine_risk_level, analyze_financial_risk (orchestrator) |
| TEST-02 | Unit tests for valuation_service (DCF, WACC, terminal value) with 80%+ coverage | valuation_service.py has 340 lines, 6 pure functions + 1 orchestrator + 1 service class. Key functions: calculate_wacc, project_fcf, calculate_present_value, calculate_terminal_value, calculate_margin_of_safety, determine_valuation_level, analyze_dcf_valuation |
| TEST-03 | Unit tests for yield_service (dividend yield, yield gap, tax calculation) with 80%+ coverage | yield_service.py has 197 lines, 3 pure functions + 1 orchestrator + 1 service class. Key functions: calculate_net_dividend_yield, calculate_yield_gap, determine_yield_recommendation, analyze_yield_gap |
| TEST-04 | Unit tests for data_service (multi-source fallback, data normalization) with 80%+ coverage | data_service.py has 1187 lines. Key methods: get_financial_report, get_current_price, get_free_cash_flow, get_shares_outstanding, get_dividend_yield, get_stock_basic. All use fallback chain: AKShare -> efinance -> Tushare -> Mock |
| TEST-05 | Integration tests for API endpoints (risk, valuation, yield) with mocked external services | 3 route files: risk_routes.py (POST /api/v1/analyze/risk), valuation_routes.py (POST /api/v1/analyze/dcf + POST /api/v1/analyze/dcf/explain), yield_routes.py (POST /api/v1/analyze/yield). Each uses FastAPI Depends for data_service and db session |
| TEST-06 | Integration tests for database persistence (CRUD operations, migrations) | 7 repository files with BaseRepository generic pattern. Key repos: risk_repo (upsert_by_report_id), valuation_repo (get_by_valuation_id), yield_repo, stock_repo (get_by_ticker), financial_repo, dividend_repo, rate_repo |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Already installed, configured, 223 tests running [VERIFIED: uv run pytest --co] |
| pytest-asyncio | 1.3.0 | Async test support | Required for all async services and routes [VERIFIED: pyproject.toml] |
| pytest-cov | 7.0.0 | Coverage reporting | Configured in pytest.ini with html + term-missing [VERIFIED: pytest.ini] |
| pytest-mock | 3.15.1 | Mocking via mocker fixture | Used throughout existing tests [VERIFIED: existing test patterns] |
| hypothesis | 6.151.9 | Property-based testing | Already used in risk_service and valuation_service tests [VERIFIED: existing tests] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27+ | Async HTTP for TestClient | FastAPI TestClient uses httpx internally [CITED: FastAPI docs] |
| SQLAlchemy | 2.0+ | Async ORM for test database | Required for integration test fixtures [VERIFIED: codebase] |
| asyncpg | 0.31+ | PostgreSQL async driver | Required for real database integration tests [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Real PostgreSQL test DB | SQLite in-memory | SQLite lacks pgvector, JSONB, and enum support that codebase uses. Would require significant model changes. Not viable. |
| pytest-asyncio mode=auto | Explicit @pytest.mark.asyncio | auto mode already configured in pytest.ini; changing would require updating 223 existing tests |

**Installation:**
```bash
# All dependencies already installed via pyproject.toml
uv sync
```

**Version verification:** All versions confirmed via `uv run python -c "import X; print(X.__version__)"` on 2026-04-16.

## Architecture Patterns

### Recommended Test Structure
```
stockvaluefinder/tests/
  conftest.py                     # Shared fixtures (factories, db session, test client)
  unit/
    test_services/
      test_risk_service.py        # EXTEND: add missing function tests
      test_valuation_service.py   # EXTEND: add analyze_dcf_valuation, DCFValuationService
      test_yield_service.py       # EXTEND: add analyze_yield_gap, YieldAnalyzer
      test_narrative_service.py   # EXTEND: add generate_dcf_explanation tests
      test_narrative_prompts.py   # Keep as-is
    test_external/
      test_data_service.py        # EXTEND: add more fallback paths, normalization
      test_data_service_cache.py  # EXTEND: add more cache scenarios
    test_utils/
      test_validators.py          # NEW: all 5 validator functions
      test_cache_utils.py         # EXTEND: add CacheManager method tests
    test_api/
      test_risk_routes.py         # Keep existing, add integration versions later
      test_dependencies.py        # Keep as-is
    test_config.py                # Keep as-is
    test_main_lifespan.py         # Keep as-is
  integration/
    __init__.py
    conftest.py                   # DB fixtures: test engine, session, table creation
    test_repositories.py          # NEW: all 7 repository CRUD tests
    test_risk_api_e2e.py          # NEW: risk endpoint with real DB
    test_valuation_api_e2e.py     # NEW: valuation endpoint with real DB
    test_yield_api_e2e.py         # NEW: yield endpoint with real DB
  contract/                       # Existing contract tests - keep as-is
```

### Pattern 1: Pure Function Unit Tests
**What:** Services use pure functions -- no side effects, no I/O, deterministic.
**When to use:** All service-level tests (risk, valuation, yield calculations).
**Example:**
```python
# Source: established pattern from test_yield_service.py
class TestMScoreIndices:
    """Test M-Score index calculations from raw financial data."""

    def test_calculate_mscore_indices_with_moutai_data(self):
        """DSRI, GMI, SGI etc. should match hand-calculated values."""
        current = make_financial_report(ticker="600519.SH", year=2023)
        previous = make_financial_report(ticker="600519.SH", year=2022)

        result = calculate_mscore_indices(current, previous, source_name="AKShare")

        assert result["dsri"] > 0
        assert "non_calculable" in result
        assert "audit_trail" in result
        assert len(result["audit_trail"]) == 8  # one per index
```

### Pattern 2: Factory Fixture Pattern
**What:** conftest.py factory functions returning realistic financial data dicts.
**When to use:** Every test that needs financial report data.
**Example:**
```python
# Source: CONTEXT.md D-07
@pytest.fixture
def make_financial_report():
    """Factory for financial report dicts with Moutai-like defaults."""
    def _factory(
        ticker: str = "600519.SH",
        year: int = 2023,
        **overrides,
    ) -> dict[str, Any]:
        defaults = {
            "ticker": ticker,
            "fiscal_year": year,
            "revenue": 127554000000,
            "net_income": 74734000000,
            "operating_cash_flow": 58150000000,
            "accounts_receivable": 3500000000,
            "cost_of_goods": 15840000000,
            "total_current_assets": 180000000000,
            "total_assets": 255000000000,
            "ppe": 25000000000,
            "sga_expense": 4500000000,
            "total_liabilities": 75000000000,
            "cash_and_equivalents": 150000000000,
            "interest_bearing_debt": 2000000000,
            "goodwill": 500000000,
            "equity_total": 180000000000,
            "assets_total": 255000000000,
            "liabilities_total": 75000000000,
            "gross_margin": 0.876,
            "shares_outstanding": 1256197900,
        }
        return {**defaults, **overrides}
    return _factory
```

### Pattern 3: Async Database Fixture (Integration Tests)
**What:** Create/drop tables per test session using SQLAlchemy metadata.
**When to use:** Integration tests requiring real database operations.
**Example:**
```python
# Source: FastAPI + SQLAlchemy async testing pattern
# integration/conftest.py
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://svf_admin:Fo41_2vhaOHKnBAyMUToMA@localhost:5433/stockvaluefinder_test",
)

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine):
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
```

### Pattern 4: FastAPI TestClient with Dependency Overrides
**What:** Override get_db and get_initialized_data_service for integration tests.
**When to use:** API endpoint E2E tests.
**Example:**
```python
# Source: FastAPI testing docs
@pytest_asyncio.fixture
async def client(test_engine):
    from stockvaluefinder.main import app
    from stockvaluefinder.db.base import get_db

    async def override_get_db():
        async with async_sessionmaker(test_engine)() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
```

### Anti-Patterns to Avoid
- **Testing implementation details:** Do not assert on private helper `_to_float` directly; test through public functions. [ASSUMED]
- **Mocking what you own:** Only mock external services (AKShare, Redis, LLM). Do not mock risk_service when testing risk_routes. [ASSUMED]
- **Shared mutable state between tests:** Each test must create its own data. The db_session fixture rolls back after each test. [ASSUMED]
- **Testing LLM output quality:** Narrative tests verify graceful fallback only, not the quality of generated text. [LOCKED: D-06]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test database setup | Custom CREATE TABLE SQL | SQLAlchemy `Base.metadata.create_all()` | Schema stays in sync with ORM models |
| Async test fixtures | Manual event loop management | pytest-asyncio `@pytest_asyncio.fixture` | Handles loop lifecycle, cleanup |
| Mock data responses | Custom mock classes | `unittest.mock.AsyncMock` + factory dicts | Existing pattern, mocker fixture available |
| Coverage reporting | Manual coverage tracking | pytest-cov with `--cov` flag | Already configured in pytest.ini |
| HTTP test client | Raw httpx calls | `fastapi.testclient.TestClient` | Handles ASGI lifecycle, dependency injection |

**Key insight:** The codebase already has well-established patterns for async testing, mocking, and property-based testing. The new tests should follow these exact patterns rather than introducing new testing paradigms.

## Common Pitfalls

### Pitfall 1: Division by Zero in Financial Ratios
**What goes wrong:** Many M-Score indices divide by revenue, total_assets, or previous-year values. Zero values cause ZeroDivisionError or infinity results.
**Why it happens:** Real financial data can have zero revenue (pre-revenue companies), zero total_assets (data errors), or zero previous-year denominators.
**How to avoid:** Test with zero denominators explicitly. The code uses `_safe_ratio` helper that returns None for zero denominators, and `_to_float` that returns 0.0 for NaN/None. Verify these code paths execute correctly.
**Warning signs:** Tests that only use "normal" positive financial data; no coverage for the `non_calculable` list in mscore_indices result.

### Pitfall 2: DataValidationError Not Raised When Expected
**What goes wrong:** `calculate_mscore_indices` validates required fields, but tests may not trigger the validation if they pass complete data dicts.
**Why it happens:** The factory pattern generates complete data by default, making it easy to skip testing missing-field scenarios.
**How to avoid:** Explicitly test `DataValidationError` is raised when required fields like "revenue", "total_assets" are missing from current_report or previous_report. Use `pytest.raises(DataValidationError)`.
**Warning signs:** risk_service coverage stays below 80% because the validation branches are untested.

### Pitfall 3: pytest-asyncio Scope Mismatch
**What goes wrong:** Using `@pytest.fixture` (sync) for async resources, or `scope="session"` fixtures without `@pytest_asyncio.fixture`.
**Why it happens:** The distinction between pytest and pytest-asyncio fixture decorators is subtle.
**How to avoid:** Use `@pytest_asyncio.fixture` for any fixture that uses `await`. Use `scope="session"` only for the test engine. Regular fixtures use function scope.
**Warning signs:** `RuntimeError: Event loop is closed` or `coroutine was never awaited` errors.

### Pitfall 4: Test Database Not Isolated
**What goes wrong:** Integration tests writing to the development database instead of the test database.
**Why it happens:** DATABASE_URL env var defaults to dev database in `db/base.py`.
**How to avoid:** Set `TEST_DATABASE_URL` explicitly in integration test conftest.py. Override `get_db` dependency. Roll back after each test.
**Warning signs:** Tests pass but dev database has test data in it.

### Pitfall 5: Frozen Pydantic Models in Tests
**What goes wrong:** Trying to modify RiskScore, ValuationResult, or YieldGap objects in tests fails because they are `frozen=True`.
**Why it happens:** These models use `model_config = {"frozen": True}` per conventions.
**How to avoid:** Create new instances instead of modifying existing ones. Use `model_copy(update={...})` for variations.
**Warning signs:** `ValidationError: Instance is frozen` in test output.

### Pitfall 6: RiskScoreCreate Requires Too Many Fields
**What goes wrong:** Creating `RiskScoreCreate` instances for repository tests requires 20+ fields, making test setup verbose.
**Why it happens:** RiskScoreCreate inherits from RiskScoreBase and adds M-Score, F-Score, anomaly detection, goodwill, divergence data.
**How to avoid:** Create a `make_risk_score_create` factory fixture that provides sensible defaults. Tests override only the fields they need.
**Warning signs:** Tests spending more lines on fixture setup than on actual assertions.

## Code Examples

Verified patterns from existing codebase and official docs:

### Existing Risk Service Test Pattern (extend this)
```python
# Source: stockvaluefinder/tests/unit/test_services/test_risk_service.py
from stockvaluefinder.services.risk_service import calculate_mscore_indices
from stockvaluefinder.utils.errors import DataValidationError

def test_calculate_mscore_indices_missing_revenue():
    """Should raise DataValidationError when revenue is missing."""
    current = {"ticker": "600519.SH", "fiscal_year": 2023}
    previous = make_financial_report(year=2022)

    with pytest.raises(DataValidationError, match="Missing required M-Score fields"):
        calculate_mscore_indices(current, previous)
```

### Narrative Service Test Pattern (extend this)
```python
# Source: stockvaluefinder/tests/unit/test_services/test_narrative_service.py
from stockvaluefinder.services.narrative_service import NarrativeService

@pytest.mark.asyncio
async def test_generate_dcf_explanation_success():
    """Test DCF explanation generation with mocked LLM."""
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "step_by_step": "step content",
        "data_inputs": "data content",
        "wacc_explanation": "wacc content",
        "fcf_analysis": "fcf content",
        "reliability": "reliability content",
        "conclusion": "conclusion content",
    })

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    svc = NarrativeService()
    svc._llm = mock_llm
    svc._llm_initialized = True
    svc._provider_name = "deepseek"

    result = await svc.generate_dcf_explanation(
        ticker="600519.SH",
        result_data={"intrinsic_value": 220000, "audit_trail": {}},
    )
    assert result is not None
    assert result.step_by_step == "step content"
```

### Cache Manager Method Test Pattern (extend this)
```python
# Source: stockvaluefinder/tests/unit/test_utils/test_cache_utils.py
@pytest.mark.asyncio
async def test_cache_manager_delete_existing_key():
    """delete() should return True when key exists."""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(return_value=1)

    cache = CacheManager(redis_url="redis://localhost:6379/0")
    cache._redis = mock_redis
    cache._connected = True

    result = await cache.delete("test_key")
    assert result is True
    mock_redis.delete.assert_called_once_with("test_key")
```

### Validator Test Pattern (NEW)
```python
# Source: stockvaluefinder/stockvaluefinder/utils/validators.py
from stockvaluefinder.utils.validators import validate_ticker_format, validate_market_enum

def test_validate_ticker_valid_sh():
    assert validate_ticker_format("600519.sh") == "600519.SH"

def test_validate_ticker_invalid_format():
    with pytest.raises(ValueError, match="Invalid ticker format"):
        validate_ticker_format("INVALID")

def test_validate_market_enum_from_string():
    result = validate_market_enum("A_SHARE")
    assert result == Market.A_SHARE

def test_validate_positive_decimal_negative_value():
    with pytest.raises(ValueError, match="must be positive"):
        validate_positive_decimal(-1.0, "test_field")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pytest-asyncio loop fixture | asyncio_mode = auto | pytest-asyncio 0.21+ | No need for `@pytest.mark.asyncio` decorator; auto mode already configured |
| unittest.mock | pytest-mock (mocker fixture) | pytest-mock 3.x | Cleaner mock lifecycle, automatic cleanup |
| Static test data | Factory fixtures | pytest best practice | More maintainable, customizable per test |
| Alembic migrations in tests | metadata.create_all() | SQLAlchemy 2.0+ | Faster test setup, no migration files needed |

**Deprecated/outdated:**
- `@pytest.mark.asyncio` decorator: Not needed with `asyncio_mode = auto` in pytest.ini. Existing tests still use it, but new tests do not need it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PostgreSQL can be started on localhost:5433 for integration tests | Environment Availability | Integration tests blocked; only unit tests possible until DB is available |
| A2 | Alembic migrations are up-to-date and `Base.metadata.create_all()` produces correct schema | Architecture Patterns | Integration tests may fail with schema mismatches |
| A3 | `Base` from `db.base.py` has all model imports resolved so `metadata.create_all()` creates all tables | Architecture Patterns | Some tables may not be created, integration tests fail |
| A4 | The existing 223 tests pass reliably (no flaky tests) | Standard Stack | If existing tests are flaky, extending them introduces confusion |
| A5 | `stockvaluefinder_test` database can be created on the same PostgreSQL instance | Architecture Patterns | Need to create the database before tests run |

## Open Questions

1. **PostgreSQL availability on localhost:5433**
   - What we know: PostgreSQL is NOT currently running on port 5433 (verified via `pg_isready`)
   - What's unclear: Is Docker available? Is there a docker-compose file? Must the user start PostgreSQL manually?
   - Recommendation: Plan should include a Wave 0 step to verify/start PostgreSQL. Integration tests should be marked with `@pytest.mark.integration` and skippable if database unavailable. Consider `pytest.mark.skipif` with a check function.

2. **Stock model import chain for Base.metadata**
   - What we know: `db/base.py` defines Base but does not import models
   - What's unclear: Do the model files in `db/models/` auto-register with Base?
   - Recommendation: Verify that importing all model files populates `Base.metadata`. May need explicit imports in integration conftest.py.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Runtime | Y | 3.12.4 | -- |
| pytest 9.0.2 | Testing | Y | 9.0.2 | -- |
| pytest-asyncio | Async tests | Y | 1.3.0 | -- |
| pytest-cov | Coverage | Y | 7.0.0 | -- |
| pytest-mock | Mocking | Y | 3.15.1 | -- |
| hypothesis | Property tests | Y | 6.151.9 | -- |
| PostgreSQL 5433 | Integration tests | N | -- | Skip integration tests, unit tests only |
| Redis | Cache tests | N | -- | Mock Redis with AsyncMock (existing pattern) |

**Missing dependencies with no fallback:**
- PostgreSQL on localhost:5433: Required for integration tests (TEST-05, TEST-06). Unit tests can proceed without it. Plan should structure work so unit tests are completed first, then integration tests in a separate wave that requires DB setup.

**Missing dependencies with fallback:**
- Redis: Not required. All cache tests use mock Redis (AsyncMock) as established in existing test_data_service_cache.py and test_cache_utils.py patterns.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | stockvaluefinder/pytest.ini |
| Quick run command | `uv run pytest tests/unit/test_services/test_risk_service.py -x -q` |
| Full suite command | `uv run pytest --cov=stockvaluefinder --cov-report=term-missing -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | M-Score index calculation correctness | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | Y (extend) |
| TEST-01 | F-Score signal detection | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | Y (extend) |
| TEST-01 | detect_存贷双高 anomaly flagging | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | Y (extend) |
| TEST-01 | Division by zero and missing field handling | unit | `uv run pytest tests/unit/test_services/test_risk_service.py -x` | N (add) |
| TEST-02 | WACC, FCF, terminal value formulas | unit | `uv run pytest tests/unit/test_services/test_valuation_service.py -x` | Y (extend) |
| TEST-02 | analyze_dcf_valuation orchestrator | unit | `uv run pytest tests/unit/test_services/test_valuation_service.py -x` | N (add) |
| TEST-02 | DCFValuationService.analyze wrapper | unit | `uv run pytest tests/unit/test_services/test_valuation_service.py -x` | N (add) |
| TEST-03 | Net dividend yield with tax | unit | `uv run pytest tests/unit/test_services/test_yield_service.py -x` | Y (extend) |
| TEST-03 | analyze_yield_gap orchestrator | unit | `uv run pytest tests/unit/test_services/test_yield_service.py -x` | N (add) |
| TEST-03 | YieldAnalyzer.analyze wrapper | unit | `uv run pytest tests/unit/test_services/test_yield_service.py -x` | N (add) |
| TEST-04 | AKShare->efinance->Tushare fallback chain | unit | `uv run pytest tests/unit/test_external/test_data_service.py -x` | Y (extend) |
| TEST-04 | Field normalization and mapping | unit | `uv run pytest tests/unit/test_external/test_data_service.py -x` | N (add) |
| TEST-04 | Cache miss/hit in data_service methods | unit | `uv run pytest tests/unit/test_external/test_data_service_cache.py -x` | Y (extend) |
| TEST-05 | POST /api/v1/analyze/risk end-to-end | integration | `uv run pytest tests/integration/test_risk_api_e2e.py -x` | N (create) |
| TEST-05 | POST /api/v1/analyze/dcf end-to-end | integration | `uv run pytest tests/integration/test_valuation_api_e2e.py -x` | N (create) |
| TEST-05 | POST /api/v1/analyze/yield end-to-end | integration | `uv run pytest tests/integration/test_yield_api_e2e.py -x` | N (create) |
| TEST-06 | Repository CRUD with real DB | integration | `uv run pytest tests/integration/test_repositories.py -x` | N (create) |
| TEST-06 | Alembic migration creates correct schema | integration | `uv run pytest tests/integration/test_repositories.py::test_schema -x` | N (create) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_services/ -x -q` (fast, <30s)
- **Per wave merge:** `uv run pytest --cov=stockvaluefinder -v` (full suite)
- **Phase gate:** `uv run pytest --cov=stockvaluefinder --cov-report=term-missing` with 80%+ on all target modules

### Wave 0 Gaps
- [ ] `tests/unit/test_utils/test_validators.py` -- covers validators.py (0% coverage, all 5 functions)
- [ ] `tests/integration/conftest.py` -- shared DB fixtures (test engine, session factory, table creation)
- [ ] `tests/integration/test_repositories.py` -- repository CRUD tests
- [ ] `tests/integration/test_risk_api_e2e.py` -- risk API E2E tests
- [ ] `tests/integration/test_valuation_api_e2e.py` -- valuation API E2E tests
- [ ] `tests/integration/test_yield_api_e2e.py` -- yield API E2E tests
- [ ] PostgreSQL on localhost:5433 with `stockvaluefinder_test` database created

## Security Domain

> This phase is purely about adding tests to existing code. No new code with security implications is being written.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Tests verify validators reject invalid inputs (malformed tickers, negative values) |
| V11 Error Handling | yes | Tests verify error responses don't leak internal details |

### Known Threat Patterns for Testing Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via test data | Tampering | Parameterized queries via SQLAlchemy ORM (already in use) |
| Test data leaking to production | Information Disclosure | Separate test database + rollback fixtures |

## Sources

### Primary (HIGH confidence)
- Existing test files in `stockvaluefinder/tests/` - patterns, conventions, mocking strategies [VERIFIED: file reads]
- `stockvaluefinder/pytest.ini` - framework configuration [VERIFIED: file read]
- `stockvaluefinder/pyproject.toml` - dependency versions [VERIFIED: file read]
- Source files: risk_service.py, valuation_service.py, yield_service.py, validators.py, errors.py, cache.py, narrative_service.py [VERIFIED: file reads]

### Secondary (MEDIUM confidence)
- CONTEXT.md canonical references - established testing patterns and coverage gaps [CITED: CONTEXT.md]
- TESTING.md analysis - infrastructure assessment [CITED: .planning/codebase/TESTING.md]

### Tertiary (LOW confidence)
- Alembic schema correctness with `Base.metadata.create_all()` [ASSUMED - needs verification at integration test time]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all dependencies verified via installed versions and existing test runs
- Architecture: HIGH - codebase fully read, patterns well-established
- Pitfalls: HIGH - derived from actual code analysis (division by zero paths, frozen models, async scope)
- Integration test setup: MEDIUM - depends on PostgreSQL availability which is currently not running

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable: pytest/SQLAlchemy versions unlikely to change)
