---
status: testing
phase: 24-golden-dataset-expansion
source: 24-01-SUMMARY.md, 24-02-SUMMARY.md
started: 2026-05-23T09:00:00Z
updated: 2026-05-23T09:00:00Z
---

## Current Test

number: 1
name: compute_golden_values.py --ticker/--year CLI
expected: |
  Script accepts --ticker and --year flags, prints help without error, and can compute golden values for any frozen stock.
awaiting: user response

## Tests

### 1. compute_golden_values.py --ticker/--year CLI
expected: Script accepts --ticker and --year flags via argparse, --help shows usage, and running with a valid ticker/year produces golden metric output
result: [pending]

### 2. 600519.SH Regression
expected: Running compute_golden_values.py --ticker 600519.SH --year 2023 produces byte-identical output (except verified_date/verified_by fields) matching the existing 600519 golden data
result: [pending]

### 3. ICBC (601398.SH) Golden Metrics Populated
expected: expected_metrics.yaml for ICBC contains 16 populated metrics (NOPAT=364B, IC=5.13T, ROIC=7.1%, M-Score=-2.6426, F-Score=4) with financial-sector NOPAT branch (OPERATE_PROFIT)
result: [pending]

### 4. Ping An (601318.SH) Golden Metrics Populated
expected: expected_metrics.yaml for Ping An contains 16 populated metrics (NOPAT=110B, IC=2.09T, ROIC=5.3%, M-Score=-2.4741, F-Score=4) with financial-sector NOPAT branch
result: [pending]

### 5. ZTE (000063.SZ) Golden Metrics Populated
expected: expected_metrics.yaml for ZTE contains 16 populated metrics (NOPAT=8.24B, IC=118.1B, ROIC=6.98%, M-Score=-2.6009, F-Score=6) with non-financial NOPAT branch (TOTAL_PROFIT + FINANCE_EXPENSE)
result: [pending]

### 6. Vanke (000002.SZ) Golden Metrics Populated
expected: expected_metrics.yaml for Vanke contains 16 populated metrics (NOPAT=23.0B, IC=508.2B, ROIC=4.53%, M-Score=-2.2018, F-Score=3) with non-financial NOPAT branch and large positive FINANCE_EXPENSE stress test
result: [pending]

### 7. Manifest l3_verified Status
expected: manifest.yaml shows l3_verified=false for ICBC, Ping An, ZTE, and Vanke (pending human verification), with updated notes and provenance fields
result: [pending]

### 8. Provenance Files Present and Annotated
expected: All 4 stocks have provenance.md files with COMPUTED status, sector-specific notes (banking/insurance/technology/real-estate), and pending_human_review annotations
result: [pending]

### 9. Golden Tests Pass (No Regressions)
expected: pytest -m golden passes with 22 tests (parametrized only for 600519.SH since l3_verified=false for the 4 new stocks), no failures
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps
