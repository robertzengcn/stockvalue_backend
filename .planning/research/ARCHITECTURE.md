# Architecture Patterns -- Financial Metrics Validation System

**Domain:** Validation infrastructure for a financial analysis platform (v1.4 milestone)
**Researched:** 2026-05-20

## Recommended Architecture

The validation system is a **cross-cutting test-time concern** that does NOT modify the existing production application layer. It introduces new modules alongside the existing codebase, reading from the same service interfaces and data paths but operating in test and CLI contexts only. No existing production code needs modification.

```
Production Architecture (UNCHANGED):
  API Routes -> Services (pure) -> Repositories -> DB/External
       |              |
       v              v
  data_service.py -> AKShare/efinance/Tushare
       |
       v
  _extract_akshare_* -> _coalesce_akshare_field -> standardized report dict


New Validation Components (test-time only):

  metric_registry.yaml  <-- single source of truth for metric definitions
         |
         v
  validation/
    registry.py          <-- loads + validates metric_registry.yaml
    golden_loader.py     <-- loads golden dataset files from tests/golden/
    comparator.py        <-- compares computed vs expected with tolerances
    reconcile.py         <-- CLI runner that orchestrates comparison
    runner_l1.py         <-- L1 formula verification test runner
    runner_l2.py         <-- L2 field mapping verification test runner
    runner_l3.py         <-- L3 end-to-end golden test runner

  tests/golden/
    manifest.yaml                        <-- golden dataset manifest
    600519.SH/2023/
      raw_akshare_income.json            <-- frozen AKShare API response
      raw_akshare_balance.json
      raw_akshare_cashflow.json
      expected_metrics.yaml              <-- hand-verified expected values
      provenance.md                      <-- source attribution (annual report pages)

  tests/unit/test_validation/
    test_l1_formula.py                   <-- L1 tests (parametrized from registry)
    test_l2_mapping.py                   <-- L2 tests (frozen JSON -> field extraction)
    test_l3_golden.py                    <-- L3 tests (full pipeline vs golden)

  tools/
    reconcile_cli.py                     <-- `uv run python -m tools.reconcile_cli`
```

### Component Boundaries

| Component | Responsibility | Communicates With | New/Modified |
|-----------|---------------|-------------------|-------------|
| `metric_registry.yaml` | Metric definitions: formula, inputs, tolerances, references | Read by `validation/registry.py` | NEW |
| `validation/registry.py` | Parse + validate YAML; expose MetricDef dataclass | `comparator.py`, `runner_l1.py`, `runner_l2.py`, `runner_l3.py`, `reconcile.py` | NEW |
| `validation/golden_loader.py` | Load frozen JSON fixtures + expected YAML per ticker/year | `runner_l2.py`, `runner_l3.py`, `reconcile.py` | NEW |
| `validation/comparator.py` | Compare computed vs expected; produce DiffReport | `reconcile.py`, test runners | NEW |
| `validation/reconcile.py` | Orchestrate fetch-compute-compare for any ticker+year | `data_service.py`, service pure functions, `registry.py`, `comparator.py` | NEW |
| `validation/runner_l1.py` | Run L1 formula verification from registry definitions | `registry.py`, service pure functions directly | NEW |
| `validation/runner_l2.py` | Run L2 field mapping tests against frozen JSON | `golden_loader.py`, `_extract_akshare_*` functions directly | NEW |
| `validation/runner_l3.py` | Run L3 end-to-end golden tests | `golden_loader.py`, `data_service.py`, service pure functions | NEW |
| `tools/reconcile_cli.py` | CLI entry point for reconcile command | `validation/reconcile.py` | NEW |
| `data_service.py` | NO CHANGES -- consumed by L3 runner and reconcile CLI | UNCHANGED | MODIFIED (no code changes, just consumed) |
| `services/*_service.py` | NO CHANGES -- pure functions called by L1, L3, reconcile | UNCHANGED | MODIFIED (no code changes, just consumed) |
| `tests/conftest.py` | Existing fixtures (`make_financial_report`, `make_risk_report_pair`) | Reused by L1 tests | MODIFIED (extend, not replace) |
| `tests/unit/test_validation/` | New test directory for all validation tests | `validation/` modules | NEW |

### Data Flow Diagrams

#### Data Flow 1: Metric Registry Consumption

The metric registry is the single source of truth that drives all three verification layers. It lives as a YAML file and is parsed once per test session.

```
metric_registry.yaml
  |
  v
registry.py::load_registry()
  |-- parse YAML into list[MetricDefinition]
  |-- validate: every metric has module path, tolerance, formula_ref
  |-- index by metric_name for O(1) lookup
  |
  +---> runner_l1.py uses MetricDefinition.formula_ref to find paper examples
  +---> runner_l2.py uses MetricDefinition.input_fields to know which raw fields to check
  +---> runner_l3.py uses MetricDefinition.tolerance to determine pass/fail thresholds
  +---> reconcile.py uses MetricDefinition to build comparison report
```

**Key design decision**: The registry is a YAML file, not a Python module, because:
1. It must be human-readable and hand-editable (adding a new metric = adding a YAML block)
2. It serves as documentation that lives alongside tests, not in production code
3. Tolerances change per metric and should not require a code deploy to adjust

**Registry location**: `stockvaluefinder/tests/fixtures/metric_registry.yaml`

This is chosen over a `stockvaluefinder/validation/` package location because the registry is a test fixture, not production code. It should live with the tests that consume it.

**Registry schema per metric**:
```yaml
metrics:
  beneish_m_score:
    display_name: "Beneish M-Score"
    module: "stockvaluefinder.services.risk_service"
    function: "calculate_beneish_m_score"
    formula_ref: "Beneish (1999) Financial Analysts Journal 55(5), pp 24-36"
    category: risk
    tolerance:
      absolute: 0.05
      relative: 0.02
    audit_trail_required: true
    input_fields:
      - name: days_sales_receivables_index
        source: computed_from_accounts_receivable_and_revenue
      - name: gross_margin_index
        source: computed_from_gross_margin_current_and_previous

  roic:
    display_name: "ROIC"
    module: "stockvaluefinder.services.roic_service"
    function: "calculate_roic"
    formula_ref: "Damodaran, Investment Valuation, Chapter 25"
    category: roic
    sector_variants:
      financial:
        formula: "NOPAT = OPERATE_PROFIT * (1 - T)"
        extra_inputs: [OPERATE_PROFIT]
      non_financial:
        formula: "NOPAT = (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - T)"
        extra_inputs: [TOTAL_PROFIT, FINANCE_EXPENSE]
    tolerance:
      relative: 0.01
    audit_trail_required: true
```

#### Data Flow 2: L1 Formula Verification

L1 tests exercise pure calculation functions with known inputs and expected outputs. They do NOT touch external data.

```
Paper Reference Values (Beneish 1999, Piotroski 2000, Damodaran)
  |
  v
metric_registry.yaml (formula_ref + L1 test cases section)
  |
  v
runner_l1.py
  |-- For each metric in registry with l1_test_cases:
  |     1. Import the function from the module path
  |     2. Construct input dict from test case inputs
  |     3. Call the pure function with those inputs
  |     4. Assert output matches expected within tolerance
  |
  v
test_l1_formula.py (pytest parametrize from registry)
  |-- @pytest.mark.l1
  |-- @pytest.mark.parametrize("metric,case", registry_l1_cases())
  |-- def test_formula_accuracy(metric, case):
  |       result = call_function(metric, case.inputs)
  |       assert_within_tolerance(result, case.expected, metric.tolerance)
```

**Integration with existing tests**: The L1 layer extends existing unit tests. The `tests/conftest.py` `make_financial_report` fixture already provides the exact factory pattern L1 needs. New L1 cases should use this fixture where possible, adding paper-reference-value test cases to the existing service test files.

**What NOT to duplicate**: The existing `test_risk_service.py` already has 48KB of Hypothesis property tests and formula accuracy tests. L1 should add **reference value test cases from published papers** that the existing tests lack, not replace the property tests.

**L1 hook point**: Import the pure function directly:
```python
from stockvaluefinder.services.risk_service import calculate_beneish_m_score
```
No data_service involvement. No AKShare. No network. Pure function + known inputs.

#### Data Flow 3: L2 Field Mapping Verification

L2 tests verify that AKShare raw JSON is correctly mapped to the standardized report dict. This is the highest-risk layer because AKShare field names are unstable.

```
Frozen AKShare JSON (tests/golden/600519.SH/2023/raw_akshare_income.json)
  |
  v
golden_loader.py::load_raw_fixtures(ticker, year)
  |-- returns {"income": {...}, "balance": {...}, "cashflow": {...}}
  |
  v
runner_l2.py (two sub-flows)

  Sub-flow A: Unit-level field extraction
  |-- Import _extract_akshare_revenue, _extract_akshare_cost_of_goods, etc.
  |-- Call each _extract_* function with the frozen JSON
  |-- Assert output matches expected_metrics.yaml intermediate values
  |
  Sub-flow B: Integration-level mapping via data_service
  |-- Mock AKShare client to return frozen JSON
  |-- Call data_service._get_financial_report_from_akshare()
  |-- Assert the resulting report dict matches expected_metrics.yaml field-by-field
```

**Critical hook points in data_service.py** (lines referenced from actual file):

1. `_extract_akshare_revenue(income)` -- line 71: Maps `TOTAL_OPERATE_INCOME`, `OPERATE_INCOME`, `INSURANCE_INCOME`, Chinese field names to `revenue`
2. `_extract_akshare_cost_of_goods(income)` -- line 83: Maps `OPERATE_COST`, Chinese field names to `cost_of_goods`; has insurance/financial fallback logic
3. `_extract_akshare_sga_expense(income)` -- line 96: Maps `TOTAL_OPERATE_COST`, Chinese field names to `sga_expense`
4. `_extract_akshare_accounts_receivable(balance)` -- line 105: Maps `ACCOUNTS_RECE`, `PREMIUM_RECE`, `FINANCE_RECE`, `NOTE_RECE` to `accounts_receivable`
5. `_coalesce_akshare_field(record, *keys)` -- line 43: The core field resolver with NaN/null handling
6. `_get_financial_report_from_akshare()` -- line 1113: The full report builder that combines all three statements
7. `_get_financial_report_from_efinance()` -- line 1221: Parallel mapping logic for efinance source
8. `_get_financial_report_from_tushare()` -- line 1297: Parallel mapping logic for Tushare source

**L2 test approach**: Test the `_extract_*` functions as pure functions by passing frozen JSON directly:
```python
# tests/unit/test_validation/test_l2_mapping.py
from stockvaluefinder.external.data_service import (
    _extract_akshare_revenue,
    _extract_akshare_cost_of_goods,
    _extract_akshare_accounts_receivable,
)

@pytest.mark.l2
def test_revenue_extraction_moutai_2023():
    income = golden_loader.load_raw_fixture("600519.SH", 2023, "income")
    result = _extract_akshare_revenue(income)
    expected = golden_loader.load_expected("600519.SH", 2023, "revenue")
    assert float(result) == pytest.approx(float(expected), rel=0.01)
```

**Cross-source consistency check** (advanced): For the same ticker+year, compare the report dict produced by the AKShare path vs the efinance path. Key fields (revenue, net_income, total_assets) should agree within 2%.

#### Data Flow 4: L3 End-to-End Golden Testing

L3 tests run the full pipeline: frozen raw data -> field mapping -> service calculation -> compare with hand-verified golden values.

```
Golden Dataset (tests/golden/)
  |
  v
runner_l3.py
  |-- Load frozen raw JSON via golden_loader
  |-- Mock data_service to return frozen data
  |-- Call the full analysis chain (same as API route does)
  |     e.g., for risk: data_service.get_financial_report() -> RiskAnalyzer().analyze()
  |-- Extract computed metrics from result
  |-- Load expected_metrics.yaml via golden_loader
  |-- Compare via comparator with registry-defined tolerances
  |
  v
test_l3_golden.py (pytest parametrize from golden manifest)
  |-- @pytest.mark.golden
  |-- @pytest.mark.parametrize("ticker,year,metric", golden_manifest_cases())
  |-- def test_golden_accuracy(ticker, year, metric):
  |       computed = run_full_pipeline(ticker, year, metric)
  |       expected = golden_loader.load_expected(ticker, year, metric)
  |       assert comparator.within_tolerance(computed, expected, metric.tolerance)
```

**Integration with API route pattern**: The L3 runner mirrors the exact call sequence from `risk_routes.py::analyze_risk`:
```python
# From risk_routes.py lines 140-152 (the actual production flow):
current_report = await data_service.get_financial_report(ticker, year)
previous_report = await data_service.get_financial_report(ticker, year - 1)
analyzer = RiskAnalyzer()
risk_score = analyzer.analyze(current_report, previous_report)
```

L3 reproduces this exact sequence but with mocked data_service that returns frozen golden data instead of live API data.

#### Data Flow 5: Reconcile CLI

The reconcile CLI is a developer tool for ad-hoc comparison, NOT a CI tool. It hits live APIs and compares against golden values.

```
$ uv run python -m tools.reconcile_cli --ticker 600519.SH --year 2023 --metrics m_score,roic
  |
  v
reconcile_cli.py
  |-- Parse args (--ticker, --year, --metrics, --live)
  |-- If --live: call data_service.get_financial_report() (hits real AKShare)
  |-- If not --live: load frozen golden data
  |-- For each requested metric:
  |     1. Call the service function with the report data
  |     2. Load expected values from golden dataset
  |     3. Compare via comparator
  |     4. Build DiffReport (metric, computed, expected, delta, pass/fail)
  |-- Print tabular report to stdout
  |-- Exit 0 if all pass, exit 1 if any fail
```

**Reconcile CLI interaction with services**: Direct function calls, no HTTP. Same pattern as production routes but without FastAPI middleware, auth, or DB persistence:
```python
# reconcile_cli.py core logic
from stockvaluefinder.services.risk_service import analyze_financial_risk
from stockvaluefinder.external.data_service import ExternalDataService

async def reconcile(ticker, year, metrics):
    service = ExternalDataService()
    await service.initialize()
    current_report = await service.get_financial_report(ticker, year)
    previous_report = await service.get_financial_report(ticker, year - 1)
    risk_result = analyze_financial_risk(current_report, previous_report)
    # compare risk_result.m_score against golden...
```

**File location**: `stockvaluefinder/tools/reconcile_cli.py`

This mirrors the existing convention where `stockvaluefinder/main.py` is the production entry point. A `tools/` directory for CLI utilities is standard.

## Patterns to Follow

### Pattern 1: Registry-Driven Test Parametrization

**What**: All test cases are derived from the metric registry YAML, not hardcoded in test files.
**When**: L1, L2, and L3 test parametrization.
**Why**: Adding a new metric to the registry automatically generates test cases in all three layers. No test file editing needed.
**Example**:
```python
# tests/unit/test_validation/conftest.py
import pytest
from validation.registry import load_registry

def pytest_collect_modifyitems(config, items):
    """Add golden marker from config."""
    pass

@pytest.fixture(scope="session")
def metric_registry():
    """Load metric registry once per test session."""
    return load_registry()

@pytest.fixture(scope="session")
def golden_manifest():
    """Load golden dataset manifest once per test session."""
    return golden_loader.load_manifest()

def pytest_generate_tests(metafunc):
    """Parametrize tests from registry and golden manifest."""
    if "metric_name" in metafunc.fixturenames:
        registry = load_registry()
        metafunc.parametrize("metric_name", list(registry.keys()))
```

### Pattern 2: Frozen Fixture Strategy

**What**: Golden test data is stored as frozen JSON files checked into the repository. These are snapshots of real AKShare API responses.
**When**: L2 and L3 tests that need deterministic raw data.
**Why**: AKShare is a third-party library with no version guarantees on field names. Frozen fixtures decouple test stability from upstream API changes.
**Directory structure**:
```
tests/golden/
  manifest.yaml                    # lists all golden test entries
  600519.SH/
    2023/
      raw_akshare_income.json      # exact API response from akshare.stock_profit_sheet_by_report_em
      raw_akshare_balance.json     # exact API response from akshare.stock_balance_sheet_by_report_em
      raw_akshare_cashflow.json    # exact API response from akshare.stock_cash_flow_sheet_by_report_em
      expected_metrics.yaml        # hand-verified values: m_score, f_score, roic, etc.
      provenance.md                # "Values from Kweichow Moutai 2023 Annual Report, pp 45-67"
    2022/
      ...
  601398.SH/
    2023/
      ...
```

**Golden value sources** (trust hierarchy):
1. Annual report hand-verified (highest trust)
2. cninfo.com.cn / eastmoney.com published financials
3. Wind/Choice terminal (if available)
4. NEVER use AKShare self-computed values as golden reference

### Pattern 3: Comparator with Layered Tolerances

**What**: A single comparison function that understands absolute, relative, and exact tolerances from the metric registry.
**When**: All comparison operations in L1, L2, L3, and reconcile.
**Example**:
```python
# validation/comparator.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Tolerance:
    absolute: float | None = None
    relative: float | None = None
    exact: bool = False

@dataclass(frozen=True)
class DiffResult:
    metric_name: str
    computed: float
    expected: float
    delta: float
    passed: bool
    tolerance_used: Tolerance
    details: str

def compare(
    metric_name: str,
    computed: float,
    expected: float,
    tolerance: Tolerance,
) -> DiffResult:
    """Compare computed vs expected value within tolerance."""
    if tolerance.exact:
        passed = computed == expected
        delta = abs(computed - expected)
    elif tolerance.relative is not None:
        delta = abs(computed - expected)
        passed = delta <= abs(expected) * tolerance.relative
    elif tolerance.absolute is not None:
        delta = abs(computed - expected)
        passed = delta <= tolerance.absolute
    else:
        delta = abs(computed - expected)
        passed = True  # no tolerance defined = informational only

    return DiffResult(
        metric_name=metric_name,
        computed=computed,
        expected=expected,
        delta=delta,
        passed=passed,
        tolerance_used=tolerance,
        details="OK" if passed else f"FAIL: delta={delta} exceeds tolerance",
    )
```

### Pattern 4: Immutable Audit Trail Reuse

**What**: Leverage the existing `IndexAuditDetail` frozen Pydantic model from `risk_service.py` for L2 verification.
**When**: L2 and L3 tests for M-Score indices.
**Why**: Each `IndexAuditDetail` contains `numerator`, `denominator`, and `value`. The L2 test can independently verify that `numerator / denominator == value` (within float precision), catching mapping errors that produce wrong numerators.
**Example**:
```python
@pytest.mark.l2
def test_mscore_audit_trail_consistency(moutai_2023_report_pair):
    current, previous = moutai_2023_report_pair
    indices = calculate_mscore_indices(current, previous, source_name="golden")
    for index_name, detail in indices["audit_trail"].items():
        if not detail.non_calculable and detail.denominator != 0:
            recomputed = detail.numerator / detail.denominator
            assert abs(recomputed - detail.value) < 0.001, (
                f"{index_name}: audit_trail inconsistency "
                f"{detail.numerator}/{detail.denominator} != {detail.value}"
            )
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Modifying Production Code for Testing

**What**: Adding hooks, dependency injection points, or conditional logic in production code specifically for validation.
**Why bad**: The validation system must test the same code path that runs in production. Any modification invalidates the test.
**Instead**: The existing architecture already supports testing:
- Pure functions in `services/*_service.py` can be called directly
- `data_service.py` methods can be mocked at the client level
- The frozen JSON fixtures replace AKShare client return values via mock

### Anti-Pattern 2: Golden Values Derived from the System Under Test

**What**: Running the system to produce "expected" values and checking them into the golden dataset.
**Why bad**: This creates a tautology -- the system always passes because it was tested against its own output.
**Instead**: Golden values must come from independent sources:
- Manual calculation from annual report numbers
- Published academic paper reference values
- Independent financial data platforms (Wind, Choice, eastmoney.com)
- The `provenance.md` file in each golden directory must cite the exact source

### Anti-Pattern 3: Single Tolerance for All Metrics

**What**: Using one global tolerance (e.g., "everything within 5%") across all metrics.
**Why bad**: F-Score is an integer 0-9 and must match exactly. M-Score is sensitive at the -1.78 threshold so +-0.05 matters. NOPAT can legitimately vary by 2% due to accounting treatment differences.
**Instead**: Per-metric tolerances in the registry:
- F-Score: `exact: true`
- M-Score: `absolute: 0.05`
- ROIC ratio: `relative: 0.01`
- NOPAT: `relative: 0.02`
- DCF total value: no tolerance (subjective, skip)

### Anti-Pattern 4: Testing DCF Total Valuation Against a Single Number

**What**: Asserting that DCF intrinsic value matches a golden number exactly.
**Why bad**: DCF depends on growth rate assumptions, terminal value methodology, and risk-free rate on the day of calculation. These are inherently subjective or time-varying.
**Instead**: Test DCF sub-components (WACC, FCF projection, terminal value formula) individually. The total DCF value is documented but not asserted. This is explicitly stated in the existing validation plan document (Section 6).

### Anti-Pattern 5: Duplicating Existing Test Infrastructure

**What**: Building a parallel test runner instead of using pytest.
**Why bad**: The project has 997+ tests using pytest + hypothesis + pytest-asyncio. A custom runner fragments the test landscape and cannot reuse fixtures.
**Instead**: All validation tests are standard pytest test files:
- `tests/unit/test_validation/test_l1_formula.py`
- `tests/unit/test_validation/test_l2_mapping.py`
- `tests/unit/test_validation/test_l3_golden.py`
- Use `@pytest.mark.l1`, `@pytest.mark.l2`, `@pytest.mark.golden` for CI filtering
- Reuse `tests/conftest.py` fixtures (`make_financial_report`, `make_risk_report_pair`)
- The `validation/` package provides helper functions, NOT a custom test runner

## File Organization

### New Files to Create

```
stockvaluefinder/
  tests/
    fixtures/
      metric_registry.yaml                      # Metric definitions (single source of truth)
    golden/
      manifest.yaml                             # Lists all golden test entries
      600519.SH/
        2023/
          raw_akshare_income.json
          raw_akshare_balance.json
          raw_akshare_cashflow.json
          expected_metrics.yaml
          provenance.md
        2022/
          ...
      601398.SH/                                # Bank (financial sector variant)
        2023/
          ...
      601318.SH/                                # Insurance (income mapping variant)
        2023/
          ...
      000063.SZ/                                # Tech (high capex)
        2023/
          ...
      000002.SZ/                                # Real estate (high leverage)
        2023/
          ...
      601088.SH/                                # High dividend
        2023/
          ...
      0700.HK/                                  # HK stock (tax variant)
        2023/
          ...
    unit/
      test_validation/
        __init__.py
        conftest.py                             # Validation-specific fixtures
        test_l1_formula.py                      # L1 formula verification
        test_l2_mapping.py                      # L2 field mapping verification
        test_l3_golden.py                       # L3 end-to-end golden tests
  stockvaluefinder/
    validation/
      __init__.py
      registry.py                               # Metric registry loader
      golden_loader.py                          # Golden dataset loader
      comparator.py                             # Tolerance-aware comparison
      reconcile.py                              # Reconcile orchestration
    tools/
      __init__.py
      reconcile_cli.py                          # CLI entry point
```

### Existing Files Modified (Extension Only, No Breaking Changes)

| File | Change | Reason |
|------|--------|--------|
| `tests/conftest.py` | Add `@pytest.mark` registration for l1/l2/golden | Enable `pytest -m l1` filtering |
| `pyproject.toml` | Add `pyyaml` to dev dependencies if not present | YAML parsing for registry |
| (no production code files) | (no changes) | Validation is test-time only |

## Scalability Considerations

| Concern | At 12 stocks | At 50 stocks | At CSI 300 |
|---------|-------------|--------------|------------|
| Golden test runtime | < 5s (frozen data, no network) | < 20s | < 2min (may need pytest-xdist) |
| Golden dataset size | ~500KB JSON | ~2MB JSON | ~12MB JSON (still manageable in git) |
| L1 test count | ~30 cases | ~30 cases (does not scale with stocks) | ~30 cases (metric count, not stock count) |
| L2 test count | ~60 cases (5 fields x 12 stocks) | ~250 cases | ~1500 cases (needs xdist) |
| L3 test count | ~84 cases (7 metrics x 12 stocks) | ~350 cases | ~2100 cases (needs xdist) |
| Reconcile CLI | Instant (single stock) | Instant | ~10min (sequential API calls) |

## Build Order (Phase Dependency)

The validation components have a clear dependency chain that dictates the build order:

```
Phase 1: Foundation (no dependencies on existing test changes)
  1. metric_registry.yaml -- define all metrics, tolerances, references
  2. validation/registry.py -- parser for the YAML
  3. validation/comparator.py -- tolerance-aware comparison
  --> Dependency: pyyaml in dev deps

Phase 2: L1 Formula Verification (depends on Phase 1)
  1. Add paper reference values to metric_registry.yaml l1_test_cases section
  2. validation/runner_l1.py (optional helper, most work is in test file)
  3. tests/unit/test_validation/test_l1_formula.py
  --> Dependency: metric_registry.yaml, existing pure functions, tests/conftest.py fixtures

Phase 3: Golden Dataset Infrastructure (parallel with Phase 2)
  1. tests/golden/manifest.yaml
  2. validation/golden_loader.py
  3. Create golden fixture directories (start with 5 stocks)
  4. Freeze AKShare JSON for each stock/year
  5. Hand-verify expected_metrics.yaml for each stock/year
  --> Dependency: access to annual reports for verification, AKShare running

Phase 4: L2 Field Mapping (depends on Phase 1 + Phase 3)
  1. validation/runner_l2.py (optional helper)
  2. tests/unit/test_validation/test_l2_mapping.py
  --> Dependency: frozen JSON from Phase 3, _extract_akshare_* functions exist

Phase 5: L3 End-to-End Golden (depends on Phase 1 + Phase 3)
  1. validation/runner_l3.py (optional helper)
  2. tests/unit/test_validation/test_l3_golden.py
  --> Dependency: frozen JSON + expected values from Phase 3, full service chain

Phase 6: Reconcile CLI (depends on Phase 1 + Phase 3)
  1. validation/reconcile.py
  2. tools/reconcile_cli.py
  --> Dependency: comparator.py, golden_loader.py, data_service.py, service functions

Phase 7: CI Integration (depends on all above)
  1. Add markers to pyproject.toml pytest config
  2. CI workflow: `pytest -m "l1 or l2" -v` on every PR
  3. CI workflow: `pytest -m golden -v` on nightly/scheduled
  4. Expand golden dataset to 12-15 stocks
```

**Critical path**: Phase 1 -> Phase 3 -> Phase 5 is the longest chain. Phase 2 (L1) can run in parallel with Phase 3 (golden dataset creation) since L1 does not need golden data.

## Integration Points Summary

### Where the metric registry lives and how it is consumed

- **Location**: `stockvaluefinder/tests/fixtures/metric_registry.yaml`
- **Parser**: `stockvaluefinder/validation/registry.py` -- loads YAML, validates schema, returns `dict[str, MetricDefinition]`
- **Consumers**: L1 test runner, L2 test runner, L3 test runner, reconcile CLI
- **Why tests/fixtures/ not in validation/**: The registry is test data, not production code. It belongs in the test tree.

### How golden datasets integrate with existing test infrastructure

- **Location**: `stockvaluefinder/tests/golden/` (new directory under existing test tree)
- **Loader**: `stockvaluefinder/validation/golden_loader.py` -- loads JSON fixtures and expected YAML
- **Integration**: Reuses `tests/conftest.py` fixture pattern. The golden data provides the inputs to the same `make_financial_report` factory pattern.
- **pytest markers**: `@pytest.mark.golden` for CI filtering. Registered in `tests/conftest.py`.
- **NOT duplicated**: Does not create a parallel test runner. Uses standard pytest parametrize.

### How the reconcile CLI interacts with existing services and data layer

- **Entry point**: `python -m stockvaluefinder.tools.reconcile_cli`
- **Service interaction**: Directly calls `analyze_financial_risk()`, `calculate_roic()`, `analyze_yield_gap()`, etc. -- same pure functions the API routes call.
- **Data layer interaction**: Creates an `ExternalDataService` instance and calls `get_financial_report()` -- same data path as production.
- **Comparison**: Uses `validation/comparator.py` with tolerances from `metric_registry.yaml`.
- **Output**: Tabular stdout report. Exit code 0/1 for CI integration.

### How L2 mapping tests hook into data_service.py field extraction

- **Hook point**: Import `_extract_akshare_revenue`, `_extract_akshare_cost_of_goods`, `_extract_akshare_sga_expense`, `_extract_akshare_accounts_receivable`, and `_coalesce_akshare_field` directly from `stockvaluefinder.external.data_service`.
- **Input**: Frozen AKShare JSON from `tests/golden/{ticker}/{year}/raw_akshare_*.json`.
- **Verification**: Pass frozen JSON to `_extract_*` functions, assert output matches `expected_metrics.yaml` intermediate values.
- **Integration-level test**: Mock `_akshare.get_profit_sheet()` etc. to return frozen data, then call `_get_financial_report_from_akshare()` and verify the full report dict.

## Sources

- Codebase analysis: `stockvaluefinder/stockvaluefinder/external/data_service.py` (field mapping functions)
- Codebase analysis: `stockvaluefinder/stockvaluefinder/services/risk_service.py` (pure functions, IndexAuditDetail)
- Codebase analysis: `stockvaluefinder/stockvaluefinder/api/risk_routes.py` (API-to-service data flow)
- Codebase analysis: `stockvaluefinder/tests/conftest.py` (existing test fixtures)
- Existing validation plan: `doc/financial_metrics_validation_plan.md`
- Project context: `.planning/PROJECT.md`
