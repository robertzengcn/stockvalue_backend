# Testing Infrastructure

## Test Framework

### Configuration
- **pytest** with `pytest.ini` at `stockvaluefinder/pytest.ini`
- **pytest-asyncio** for async test support
- **pytest-cov** for coverage reporting
- **pytest-mock** for mocking
- **hypothesis** for property-based testing
- **mypy plugin** enabled for pydantic

### Test Directory Structure
```
stockvaluefinder/tests/
└── unit/
    ├── __init__.py
    ├── test_external/
    │   ├── __init__.py
    │   ├── test_akshare_client.py    # AKShare client tests
    │   ├── test_efinance_client.py   # efinance client tests
    │   └── test_data_service.py      # Data service facade tests
    └── test_services/
        ├── __init__.py
        ├── test_yield_service.py     # Yield gap calculation tests
        └── test_valuation_service.py # DCF valuation tests
```

## Test Coverage

### What's Tested
- **External clients**: AKShare, efinance, data_service (with mocking)
- **Services**: yield_service (pure functions), valuation_service (pure functions)
- Pure calculation functions are well-suited for unit testing

### What's Not Tested
- **API routes** (risk_routes, valuation_routes, yield_routes) - no integration tests
- **Repository layer** (all 7 repos) - no database tests
- **Narrative service** - LLM integration not tested
- **Rate client** - interest rate fetching not tested
- **Risk service** - M-Score, F-Score calculations not tested
- **RAG module** - scaffolding, no tests
- **Agents** - scaffolding, no tests
- **Cache manager** - Redis integration not tested
- **Config** - no tests

### Coverage Configuration
- pytest-cov available but coverage thresholds not enforced in CI

## Test Patterns

### Mocking Strategies
- External API calls mocked with `pytest-mock`
- Async clients mocked for unit testing
- Data sources use development mode mock data as fallback

### Async Test Patterns
- `pytest-asyncio` for async test functions
- Async functions tested with `await` directly

## Testing Commands

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_services/test_yield_service.py

# Run with coverage
uv run pytest --cov=stockvaluefinder --cov-report=term-missing

# Run single test
uv run pytest tests/test_module.py::test_function
```

## Test Gaps

1. **No integration tests**: API routes untested end-to-end
2. **No repository tests**: Database operations untested
3. **Risk service untested**: M-Score, F-Score, 存贷双高, profit-cash divergence
4. **No narrative tests**: LLM response parsing, graceful fallback
5. **No rate client tests**: Interest rate fetching with AKShare
6. **No config tests**: Configuration validation
7. **No error handling tests**: Exception hierarchy behavior
8. **No cache tests**: Redis operations, decorator behavior
9. **Coverage threshold not enforced**: No minimum coverage requirement in CI
10. **Missing E2E tests**: No end-to-end user flow tests
