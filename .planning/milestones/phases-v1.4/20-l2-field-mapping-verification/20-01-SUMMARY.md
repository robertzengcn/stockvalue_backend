---
phase: 20-l2-field-mapping-verification
plan: 01
subsystem: validation
tags: [testing, l2-mapping, snapshot, traceability, akshare, frozen-data]
dependency_graph:
  requires: [phase-18, phase-19]
  provides: [l2-mapping-tests, build_standardized_report_from_frozen]
  affects: [pytest.ini, tests/unit/test_l2/]
tech_stack:
  added: []
  patterns: [frozen-data-testing, NaN-sanitization, synthetic-previous-report]
key_files:
  created:
    - stockvaluefinder/tests/unit/test_l2/__init__.py
    - stockvaluefinder/tests/unit/test_l2/conftest.py
    - stockvaluefinder/tests/unit/test_l2/test_l2_snapshot_traceability.py
    - stockvaluefinder/tests/__init__.py
  modified:
    - stockvaluefinder/pytest.ini
decisions:
  - Financial stocks (banking/insurance) exempted from certain assertions where fields are structurally absent
  - Synthetic previous report created by multiplying current values by 0.95 for traceability tests
  - NaN sanitization applied at load time to prevent silent float('nan') propagation
metrics:
  duration: 583s
  completed: "2026-05-21"
  test_count: 217
  file_count: 4
---

# Phase 20 Plan 01: Snapshot Tests + Field Traceability Tests Summary

L2 field mapping verification with 217 snapshot and traceability tests validating AKShare field extraction across all 14 golden stocks and IndexAuditDetail consistency for the anchor stock.

## What Was Done

### Task 1: Register l2_mapping marker and create test scaffold
- Added `l2_mapping` marker to `pytest.ini` alongside existing `l1_formula` marker
- Created `tests/unit/test_l2/` directory with `__init__.py` and `conftest.py`
- `conftest.py` provides:
  - `_sanitize_nan()`: Walks dicts/lists and replaces NaN/Inf floats with None
  - `_load_frozen_json()`: Loads frozen AKShare JSON with NaN sanitization
  - `frozen_akshare_data` fixture: Session-scoped, cached data loader
  - `build_standardized_report_from_frozen()`: Replicates data_service.py report building using `_extract_akshare_*` functions
  - `roic_inputs_from_frozen()`: Extracts ROIC-relevant fields from frozen data
- Added missing `tests/__init__.py` to fix mypy duplicate module path resolution

### Task 2: L2 snapshot tests + field traceability tests
- 15 snapshot test functions parametrized across all 14 golden stocks (210 tests total)
- 7 traceability tests for anchor stock 600519.SH
- All 217 tests marked `@pytest.mark.l2_mapping`, pass with no network access

## Test Coverage

### Snapshot Tests (210 tests)
Each of the 15 assertions runs for all 14 golden stocks:
1. `test_revenue_extraction` - _extract_akshare_revenue returns non-null, non-zero
2. `test_cost_of_goods_extraction` - _extract_akshare_cost_of_goods returns non-null
3. `test_sga_expense_extraction` - _extract_akshare_sga_expense non-zero for non-financial
4. `test_accounts_receivable_extraction` - _extract_akshare_accounts_receivable non-null
5. `test_netprofit_present` - NETPROFIT coalesced and non-zero
6. `test_netcash_operate_present` - NETCASH_OPERATE coalesced and present
7. `test_total_assets_present` - TOTAL_ASSETS coalesced and present
8. `test_total_liabilities_present` - TOTAL_LIABILITIES coalesced and present
9. `test_monetaryfunds_present` - MONETARYFUNDS present for non-financial stocks
10. `test_total_equity_present` - TOTAL_EQUITY coalesced and present
11. `test_total_current_assets_present` - TOTAL_CURRENT_ASSETS present for non-financial
12. `test_fixed_asset_present` - FIXED_ASSET coalesced and present
13. `test_total_parent_equity_present` - TOTAL_PARENT_EQUITY coalesced and present
14. `test_standardized_report_mscore_fields` - Report has all M-Score required fields
15. `test_roic_profit_fields` - TOTAL_PROFIT and INCOME_TAX present and non-zero

### Traceability Tests (7 tests)
For anchor stock 600519.SH (Kweichow Moutai):
1. `test_audit_trail_has_all_8_indices` - All 8 M-Score indices present in audit trail
2. `test_numerator_denominator_consistency` - Each index value equals numerator/denominator within 0.001
3. `test_tata_traceability` - TATA numerator = (net_income - operating_cash_flow), denominator = assets_total
4. `test_sgi_traceability` - SGI numerator = current revenue, denominator = previous revenue
5. `test_source_fields_populated` - Each index has source_fields with >= 1 entry
6. `test_depi_mvp_hardcoded` - DEPI = 1.0 with MVP reason, non_calculable=False
7. `test_all_indices_finite_and_reasonable` - All values finite and in range (-10, 100)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed GOLDEN_DIR path resolution**
- **Found during:** Task 1 verification
- **Issue:** `Path(__file__).resolve().parents[3]` resolved to `stockvaluefinder/golden/` instead of `stockvaluefinder/tests/golden/`
- **Fix:** Changed to `parents[2]` in both conftest.py and test file
- **Files modified:** conftest.py, test_l2_snapshot_traceability.py

**2. [Rule 1 - Bug] Fixed mypy duplicate module name error**
- **Found during:** Task 2 pre-commit hook
- **Issue:** `conftest.py` found twice under `unit.test_l2.conftest` and `tests.unit.test_l2.conftest`
- **Fix:** Added missing `tests/__init__.py`
- **Files modified:** `stockvaluefinder/tests/__init__.py` (created)
- **Commit:** 0b60c8f

**3. [Rule 1 - Bug] Removed unused imports**
- **Found during:** Task 2 pre-commit hook
- **Issue:** Unused imports: `yaml` in conftest.py, `json` and `_akshare_field_str` in test file
- **Fix:** Removed unused imports
- **Files modified:** conftest.py, test_l2_snapshot_traceability.py

**4. [Rule 2 - Missing] Financial stock field exemptions**
- **Found during:** Task 2 implementation
- **Issue:** Banking (601398.SH, 600036.SH) and insurance (601318.SH) stocks lack MONETARYFUNDS, TOTAL_CURRENT_ASSETS, ACCOUNTS_RECE, and TOTAL_OPERATE_COST fields
- **Fix:** Added `_is_financial()` helper and conditional assertions for financial stocks
- **Files modified:** test_l2_snapshot_traceability.py

## Key Findings

### AKShare Field Mapping by Sector
- **Non-financial stocks (11/14):** All extraction fields populated, all assertions pass with non-zero values
- **Banking stocks (601398.SH, 600036.SH):** Missing MONETARYFUNDS, ACCOUNTS_RECE, TOTAL_CURRENT_ASSETS; use OPERATE_EXPENSE fallback for COGS; SGA returns "0"
- **Insurance stock (601318.SH):** Missing TOTAL_CURRENT_ASSETS; uses PREMIUM_RECE for AR; OPERATE_EXPENSE fallback for COGS

### M-Score Index Consistency
- All 8 indices produce valid finite values for 600519.SH
- Numerator/denominator ratios match computed values within 0.001 tolerance
- DEPI correctly hardcoded to 1.0 (MVP simplification per D-05)
- TATA and SGI traceability verified against known input fields

## Self-Check

- [x] All 14 golden stocks have non-null values after extraction
- [x] Standardized report contains M-Score required fields for all stocks
- [x] IndexAuditDetail numerator/denominator consistent within 0.001
- [x] TATA and SGI traceability verified
- [x] DEPI hardcoded to 1.0 with MVP reason
- [x] All 217 tests marked @pytest.mark.l2_mapping pass
- [x] l2_mapping marker registered in pytest.ini

## Self-Check: PASSED
