# Financial Metrics Validation Guide

This document describes the 3-layer validation system for StockValueFinder's
financial metrics. It covers how to run tests, use the reconcile CLI, contribute
new golden stocks, and configure tolerances.


## 1. System Overview

StockValueFinder uses a **3-layer validation pyramid** to ensure that every
financial metric -- from Beneish M-Score sub-indices to composite Alpha Score --
is computed correctly. Each layer builds confidence from unit-level formula
verification up to full end-to-end pipeline validation.

### The Validation Pyramid

```
         +-------------------+
         |   L3 Golden (8)   |  End-to-end pipeline vs hand-verified values
         +-------------------+
         |  L2 Mapping (403)  |  AKShare field extraction + cross-source checks
         +-------------------+
         |  L1 Formula (161)  |  Pure calculate_* functions vs paper references
         +-------------------+
```

**L1 Formula Verification.** Tests pure `calculate_*` functions in isolation,
using inputs and expected outputs taken from published academic papers.
No database, no network, no external data. A test for `calculate_beneish_m_score`
uses the illustrative sample from Beneish (1999), Table 3.

**L2 Field Mapping Verification.** Tests the AKShare-to-standardized-dict
extraction layer and cross-source (AKShare vs efinance) field consistency.
Uses frozen JSON snapshots -- no network required. Covers 14 CSI 300 stocks
across banking, insurance, technology, real estate, energy, pharmaceuticals,
materials, industrials, and consumer staples sectors.

**L3 End-to-End Golden Testing.** Runs the full pipeline: frozen AKShare JSON
through extraction, standardization, and all `calculate_*` functions. Compares
the computed results against hand-verified expected values in
`expected_metrics.yaml`. No network required.

### Metric Registry

The **metric registry** (`stockvaluefinder/validation/metric_registry.yaml`) is
the single source of truth for all 28 validated metrics across 7 categories:

| Category   | Metrics                                                              | Count |
|------------|----------------------------------------------------------------------|-------|
| risk       | DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA, M-Score, F-Score, detect_存贷双高, goodwill_ratio, profit_cash_divergence | 13    |
| roic       | NOPAT, invested_capital, ROIC, ROIC-WACC spread                      | 4     |
| valuation  | WACC, present_value, terminal_value, margin_of_safety                | 4     |
| yield      | net_dividend_yield, yield_gap                                        | 2     |
| capex      | buyback_yield, capital_allocation_score                              | 2     |
| policy     | resonance_score, dcf_adjustment                                      | 2     |
| alpha      | alpha_score                                                          | 1     |

### Priority Levels

Metrics are assigned a priority that determines how failures are handled:

- **P0** (critical): M-Score sub-indices, composite M-Score, F-Score, NOPAT,
  invested capital, ROIC. Failures are hard assertion errors.
- **P1** (important): detect_存贷双高, goodwill_ratio, profit_cash_divergence,
  WACC, present value, terminal value, margin of safety, yield metrics,
  CapEx metrics. Failures are reported as `xfail` (non-blocking).
- **P2** (supplementary): Policy resonance, DCF adjustment, Alpha score.
  Informational only.

### Data Flow

```
AKShare API
    |
    v
frozen JSON (tests/golden/<TICKER>/<YEAR>/raw_akshare_*.json)
    |
    v
extraction layer (data_service / compute_golden_values.py)
    |
    v
standardized financial dict
    |
    v
calculate_* functions (risk_service, roic_service, valuation_service, ...)
    |
    v
computed metrics
    |
    v
comparison against expected_metrics.yaml (via metric_registry tolerances)
```


## 2. Running Tests

All validation tests use pytest markers registered in `pytest.ini`. Run them
from the `stockvaluefinder/` directory (where `pytest.ini` lives).

### Individual Layers

```bash
# L1 formula tests -- 161 tests, ~4 seconds, no network
cd stockvaluefinder
uv run pytest -m l1_formula

# L2 mapping tests -- 403 tests, ~5 seconds, no network
uv run pytest -m l2_mapping

# L3 golden tests -- 8 tests, ~3 seconds, no network
uv run pytest -m golden

# L3 golden live tests -- requires network + DEVELOPMENT_MODE=true
uv run pytest -m golden_live
```

### Combined Runs

```bash
# All offline validation tests (L1 + L2 + L3 golden) -- ~572 tests, ~12 seconds
uv run pytest -m "l1_formula or l2_mapping or golden"

# Full test suite (includes non-validation tests)
uv run pytest
```

### Targeting Specific Stocks

```bash
# Run golden tests for a specific stock
uv run pytest tests/golden/test_l3_golden.py -k "600519"

# Run L2 snapshot tests for a specific stock
uv run pytest -m l2_mapping -k "600519"
```

### CI Integration

GitHub Actions runs `l1_formula`, `l2_mapping`, and `golden` tests on every
pull request. The `golden_live` marker runs on a weekly schedule against the
live AKShare API to detect upstream data format changes.


## 3. Using the Reconcile CLI

The `reconcile` tool compares computed financial metrics against golden expected
values. It provides colored terminal output via Rich tables, JSON output for
CI/CD pipelines, and an optional verbose audit trail.

### Basic Usage

```bash
# Compare all metrics for a stock/year against frozen golden data
uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023
```

This outputs a Rich table with columns: METRIC, EXPECTED, COMPUTED, DELTA,
TOLERANCE, STATUS. Below the table, a summary line shows P0 and total pass rates.

### Single Metric

```bash
# Compare only one metric
uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --metric m_score
```

Useful for debugging a specific failing metric.

### Verbose Mode

```bash
# Show full audit trail with priority, category, and formula reference
uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --verbose
# or: -v
```

Verbose mode adds columns for PRIORITY, CATEGORY, and AUDIT_TRAIL to the table,
then prints a detailed breakdown for every metric including formula references
and tolerance specifications.

### JSON Output

```bash
# Machine-parseable JSON for CI/CD integration
uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --json
```

Outputs a JSON object with `ticker`, `year`, `summary`, `p0_all_pass`,
`skipped_metrics`, and `comparisons` array.

### Live Mode

```bash
# Fetch live data from AKShare instead of using frozen golden data
uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --live
```

Requires network access and AKShare availability. Useful for detecting drift
between frozen snapshots and current AKShare responses.

### Exit Codes

| Code | Meaning                          |
|------|----------------------------------|
| 0    | All P0 metrics pass              |
| 1    | One or more P0 metrics fail      |
| 2    | Error (invalid ticker, missing data, etc.) |

Example CI usage:

```bash
uv run python -m stockvaluefinder.tools.reconcile --ticker 600519.SH --year 2023 --json
if [ $? -ne 0 ]; then
  echo "P0 validation failed"
  exit 1
fi
```


## 4. Contributing New Golden Stocks

To add a new CSI 300 stock to the golden dataset, follow these steps.

### Step 1: Add Entry to manifest.yaml

Edit `tests/golden/manifest.yaml` and add a new entry:

```yaml
- ticker: 601988.SH
  name: Bank of China
  sector: banking
  is_financial: true
  years:
  - 2023
  l3_verified: false
  provenance: frozen_akshare
  notes: 'P0: Additional banking stock for NOPAT formula branch validation'
```

Set `l3_verified: false` initially. The `is_financial` flag controls which NOPAT
formula branch is used (financial sector uses `OPERATE_PROFIT`, non-financial
uses `TOTAL_PROFIT + FINANCE_EXPENSE`).

### Step 2: Freeze AKShare Data

Run the freeze script to fetch and store raw AKShare responses:

```bash
cd stockvaluefinder

# Freeze all stocks with missing data
uv run python tests/golden/freeze_akshare_data.py

# Or freeze a specific stock
uv run python tests/golden/freeze_akshare_data.py --ticker 601988.SH

# Force re-freeze existing data
uv run python tests/golden/freeze_akshare_data.py --ticker 601988.SH --force
```

This creates three JSON files under `tests/golden/601988.SH/2023/`:
- `raw_akshare_income.json`
- `raw_akshare_balance.json`
- `raw_akshare_cashflow.json`

### Step 3: Generate Expected Metrics Template

Run the compute script to generate an `expected_metrics.yaml` template with
values computed by the production `calculate_*` functions:

```bash
uv run python tests/golden/compute_golden_values.py 601988.SH 2023
```

This writes `tests/golden/601988.SH/2023/expected_metrics.yaml` with computed
values for all metrics that can be derived from financial statement data alone.
Metrics requiring external market data (WACC, yield, alpha) will be set to
`null` with a `skip_reason`.

### Step 4: Manually Verify Values

Cross-check the computed values against the company's annual report (available
on CNINFO at https://www.cninfo.com.cn or the company investor relations page):

1. Open `expected_metrics.yaml` and review each metric value.
2. For P0 metrics (M-Score, F-Score, ROIC components), verify against the
   annual report financial statements line by line.
3. Update `source_page` fields with the page number or section where the
   reference value was found.
4. Adjust any values that differ from the annual report. The compute script
   produces best-effort values; manual verification catches edge cases.

### Step 5: Write Provenance Documentation

Create `tests/golden/601988.SH/2023/provenance.md` documenting your sources:

```markdown
# Provenance: 601988.SH / 2023

## Data Source
- AKShare frozen: 2024-XX-XX
- Annual report: Bank of China 2023 Annual Report

## Verification
- Revenue: p.12, Total Operating Income
- Net Income: p.14, Net Profit Attributable to Parent
- Total Assets: p.28, Balance Sheet
- ...
```

### Step 6: Update manifest.yaml

After verification is complete:

```yaml
- ticker: 601988.SH
  ...
  l3_verified: true
  provenance: frozen_akshare_computed
```

### Step 7: Run Tests

```bash
# Verify the new stock passes all golden tests
uv run pytest tests/golden/test_l3_golden.py -k "601988"

# Verify nothing else broke
uv run pytest -m golden
```

### Step 8: Commit

Commit all new files: frozen JSON, expected_metrics.yaml, provenance.md,
and the updated manifest.yaml.

### Stock Selection Guidelines

Choose stocks that provide sector diversity and formula branch coverage:

- At least 2 financial-sector stocks (banking, insurance) to validate the
  `OPERATE_PROFIT` NOPAT branch.
- At least 1 high-dividend stock for yield gap validation.
- At least 1 high-leverage stock (real estate) for LVGI stress testing.
- At least 1 technology stock with significant R&D and CapEx.


## 5. Tolerance Configuration

Each metric in `metric_registry.yaml` defines a tolerance specification that
determines whether a computed value is considered "close enough" to the expected
value.

### Tolerance Types

**Absolute tolerance** (`absolute`): Fixed delta. The comparison passes if
`|computed - expected| <= absolute`.

Example: M-Score sub-indices have `absolute: 0.05`, meaning a computed DSRI
of 2.44 passes if the expected value is between 2.39 and 2.49.

**Relative tolerance** (`relative`): Percentage delta. The comparison passes
if `|computed - expected| / |expected| <= relative`.

Example: NOPAT has `relative: 0.02`, meaning a 2% relative difference is
acceptable. For an expected NOPAT of 76,183,240,205, the computed value can
range from ~74,659,575,401 to ~77,706,905,009.

**OR logic**: When both `absolute` and `relative` are specified, the comparison
passes if **either** threshold is satisfied. This handles metrics that may have
small absolute differences at low values but acceptable relative differences at
high values.

**Exact match**: Setting `absolute: 0` requires exact equality. Used for
F-Score (integer 0-9) where any difference is a real error.

### Current Tolerances by Category

| Category   | Metric                          | Type     | Value | Notes                             |
|------------|---------------------------------|----------|-------|-----------------------------------|
| risk       | DSRI, GMI, AQI, SGI, DEPI,     | absolute | 0.05  | Sub-indices of M-Score            |
|            | SGAI, LVGI, TATA, M-Score       |          |       |                                   |
| risk       | F-Score                         | absolute | 0     | Exact integer match (0-9)         |
| risk       | detect_存贷双高                  | absolute | 0.01  | Boolean flag comparison           |
| risk       | goodwill_ratio                  | relative | 0.01  | 1% relative tolerance             |
| risk       | profit_cash_divergence          | absolute | 0.01  | Boolean flag comparison           |
| roic       | NOPAT, invested_capital         | relative | 0.02  | 2% relative for large absolute vals |
| roic       | ROIC                            | relative | 0.01  | 1% relative tolerance             |
| roic       | ROIC-WACC spread                | absolute | 0.001 | Tight absolute tolerance          |
| valuation  | WACC                            | relative | 0.01  | 1% relative tolerance             |
| valuation  | present_value                   | relative | 0.02  | 2% relative tolerance             |
| valuation  | terminal_value                  | relative | 0.02  | 2% relative tolerance             |
| valuation  | margin_of_safety                | relative | 0.01  | 1% relative tolerance             |
| yield      | net_dividend_yield              | relative | 0.01  | 1% relative tolerance             |
| yield      | yield_gap                       | relative | 0.01  | 1% relative tolerance             |
| capex      | buyback_yield                   | relative | 0.01  | 1% relative tolerance             |
| capex      | capital_allocation_score        | absolute | 0.5   | Score grade tolerance             |
| policy     | resonance_score                 | absolute | 1.0   | Wide tolerance for LLM variability |
| policy     | dcf_adjustment                  | absolute | 0.001 | Tight for growth rate adjustment  |
| alpha      | alpha_score                     | absolute | 0.1   | Composite score tolerance         |

### Modifying Tolerances

Edit `stockvaluefinder/validation/metric_registry.yaml` directly. Each metric
entry has a `tolerance` block:

```yaml
# Before
m_score:
  display_name: "Beneish M-Score"
  tolerance:
    absolute: 0.05

# After (widen to 0.08)
m_score:
  display_name: "Beneish M-Score"
  tolerance:
    absolute: 0.08
```

The registry is loaded once and cached via `lru_cache`. To pick up changes,
restart the Python process (or invalidate the cache in long-running sessions).

Validation is automatic: running `uv run pytest -m golden` will apply the
updated tolerances immediately since each test run loads a fresh registry.
