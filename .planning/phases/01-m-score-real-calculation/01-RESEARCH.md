# Phase 1: M-Score Real Calculation - Research

**Researched:** 2026-04-15
**Domain:** Beneish M-Score financial fraud detection, AKShare data field mapping, pure-function calculation services
**Confidence:** HIGH

## Summary

Phase 1 replaces the 8 hardcoded M-Score index values (1.0/0.0) in `data_service.py` with real calculations derived from two years of financial data. The core work involves three layers: (1) extending the AKShare/efinance/Tushare field mappings in `data_service.py` to extract the ~10 additional financial fields needed for M-Score index computation, (2) creating a new pure function `calculate_mscore_indices()` in `risk_service.py` that computes all 8 indices from standardized two-year data, and (3) updating the `analyze_financial_risk()` orchestrator to call the new function before the existing `calculate_beneish_m_score()` linear combination.

The existing `calculate_beneish_m_score()` function already correctly implements the Beneish 1999 linear formula -- it reads pre-calculated index values and combines them. The gap is that those indices are currently hardcoded as 1.0 or 0.0 in `data_service.py` (lines 895-902 for AKShare, 974-981 for efinance, 1044-1051 for Tushare). The F-Score already demonstrates the desired pattern: `calculate_piotroski_f_score()` receives raw financial data and computes ratios internally.

**Primary recommendation:** Extend `data_service.py` field mappings, create `calculate_mscore_indices()` as a pure function, and wire it into `analyze_financial_risk()` before the existing M-Score linear combination call.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Unified mapping layer in `data_service.py` -- extend `_get_financial_report_from_akshare/efinance/tushare` to normalize raw field names to internal standard names. `risk_service` only processes standardized data.
- **D-02:** Extend `get_financial_report` -- add M-Score fields (~10) to existing mapping, no new methods.
- **D-03:** Standalone calculation function -- new `calculate_mscore_indices(current_report, previous_report)` pure function. `calculate_beneish_m_score` stays unchanged.
- **D-04:** SG&A proxy -- use `OPERATE_EXPENSE` (operating total expense) as SG&A proxy to avoid missing field issues.
- **D-05:** DEPI simplified -- MVP sets DEPI to 1.0 (neutral) since AKShare lacks direct depreciation field.
- **D-06:** TATA standard formula -- `(Net Income - Operating Cash Flow) / Total Assets`.
- **D-07:** Complete field mapping table confirmed (see Code Context section of CONTEXT.md).
- **D-08:** Strict mode -- missing required fields throw `DataValidationError`, no M-Score result returned.
- **D-09:** Zero denominator -- mark index as non-calculable, add warning to `red_flags`. M-Score uses remaining calculable indices.
- **D-10:** Unified processing -- M-Score logic does not distinguish market type. Data source differences handled in `data_service`.
- **D-11:** Full audit trail -- each index includes intermediate values (numerator, denominator, ratio) and field source references.
- **D-12:** Extend MScoreData -- add intermediate value and source info to existing JSONB column `mscore_data`, no new database migration.

### Claude's Discretion

- Specific field mapping implementation details (efinance/Tushare fallback field name priority)
- Internal structure of `calculate_mscore_indices` and error message wording
- `red_flags` text content for non-calculable indices

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RISK-01 | DSRI calculated from actual balance sheet data | Verified AKShare `ACCOUNTS_RECE` field exists [VERIFIED: akshare 1.18.46 live query]. Formula: `(AR_curr / Revenue_curr) / (AR_prev / Revenue_prev)` |
| RISK-02 | GMI calculated from income statement data | Verified `TOTAL_OPERATE_INCOME` and `OPERATE_COST` fields [VERIFIED: akshare live query]. Formula: `GrossMargin_prev / GrossMargin_curr` |
| RISK-03 | AQI calculated from balance sheet data | Verified `TOTAL_CURRENT_ASSETS`, `TOTAL_ASSETS`, `FIXED_ASSET` [VERIFIED: akshare live query]. Formula: `(1 - (CA_curr - PPE_curr) / TA_curr) / (1 - (CA_prev - PPE_prev) / TA_prev)` |
| RISK-04 | SGI calculated from income statement data | Uses existing `revenue` field. Formula: `Revenue_curr / Revenue_prev` |
| RISK-05 | DEPI simplified to 1.0 | Locked decision D-05. AKShare lacks direct depreciation field. |
| RISK-06 | SGAI calculated from income statement data | Verified `SALE_EXPENSE` + `MANAGE_EXPENSE` as components. Decision D-04: use `TOTAL_OPERATE_COST` total. Formula: `(SGA_curr / Revenue_curr) / (SGA_prev / Revenue_prev)` |
| RISK-07 | LVGI calculated from balance sheet data | Verified `TOTAL_LIABILITIES` and `TOTAL_ASSETS` [VERIFIED: akshare live query]. Long-term debt field is `LONG_LOAN` (not `LONGTERM_LOAN`). Formula: `(TL_curr / TA_curr) / (TL_prev / TA_prev)` |
| RISK-08 | TATA calculated from cash flow + balance sheet | Verified `NETCASH_OPERATE` [VERIFIED: akshare live query]. Formula: `(NetIncome - OCF) / TotalAssets` |
| RISK-09 | Complete M-Score composite with audit trail | Existing `calculate_beneish_m_score()` formula verified correct. Audit trail structure in D-11. |
| RISK-10 | API returns individual index breakdown with source references | D-12: extend MScoreData Pydantic model with audit fields stored in existing JSONB column |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| AKShare | 1.18.46 | Primary free A-share financial data source | Already installed, primary data source per project stack |
| Pydantic | 2.x | Data validation and serialization | Already in use for MScoreData model |
| pytest | 9.0.2 | Testing framework | Already configured in pytest.ini |
| hypothesis | 6.x | Property-based testing | Already in use in test_risk_service.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ruff | 0.15+ | Linting and formatting | Required before commit per CLAUDE.md |
| mypy | 1.19+ | Type checking | Required before commit per CLAUDE.md |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| OPERATE_COST as SG&A proxy | SALE_EXPENSE + MANAGE_EXPENSE | D-04 locks OPERATE_COST. More specific fields available but decision is locked. |
| DEPI = 1.0 | Estimate from fixed asset changes | D-05 locks 1.0 for MVP. Realistic for A-shares where depreciation detail is limited. |

**Installation:**
No new packages needed. All dependencies already in `pyproject.toml`.

**Version verification:**
```
AKShare: 1.18.46 (verified via `uv run python -c "import akshare; print(akshare.__version__)"`)
pytest: 9.0.2 (verified via `uv run pytest --version`)
Python: 3.12.4 (verified via `uv run python --version`)
```

## Architecture Patterns

### Recommended Project Structure
```
stockvaluefinder/
  stockvaluefinder/
    services/
      risk_service.py          # ADD: calculate_mscore_indices() function
    external/
      data_service.py          # MODIFY: extend field mappings in 3 source methods
    models/
      risk.py                  # MODIFY: extend MScoreData with audit fields
  tests/
    unit/
      test_services/
        test_risk_service.py   # MODIFY: add tests for calculate_mscore_indices
```

### Pattern 1: Pure Function Calculation (established in codebase)
**What:** Stateless functions receive dicts, return dicts/dataclasses. No side effects, no I/O.
**When to use:** All financial calculations per project architecture principle.
**Example:**
```python
# Existing pattern from calculate_piotroski_f_score():
def calculate_mscore_indices(
    current_report: dict[str, Any],
    previous_report: dict[str, Any],
) -> dict[str, Any]:
    """Calculate all 8 Beneish M-Score component indices from two-year data.

    Returns:
        Dictionary with each index value, plus audit trail:
        {
            "dsri": {"value": 1.15, "numerator": ..., "denominator": ..., "source_fields": {...}},
            "gmi": {...},
            ...
            "non_calculable": ["depi"],  # indices that could not be calculated
        }
    """
    ...
```

### Pattern 2: Multi-Level Field Mapping (established in data_service.py)
**What:** `income.get("ENGLISH_FIELD", income.get("中文", income.get("fallback", 0)))`
**When to use:** All data source mappings in `_get_financial_report_from_*` methods.
**Example:**
```python
# Existing pattern - extend with new M-Score fields:
"cost_of_goods": str(
    income.get("OPERATE_COST", income.get("营业成本", 0))
),
"sga_expense": str(
    income.get("TOTAL_OPERATE_COST", income.get("营业总成本", 0))
),
```

### Pattern 3: Orchestrator Integration (established in analyze_financial_risk)
**What:** `analyze_financial_risk()` calls pure functions in sequence, collects results.
**When to use:** When adding a new calculation step to the risk pipeline.
**Example:**
```python
# Insert BEFORE calculate_beneish_m_score():
mscore_indices = calculate_mscore_indices(current_report, previous_report or {})
# Then pass index values into current_report dict for calculate_beneish_m_score
```

### Anti-Patterns to Avoid
- **Don't calculate indices inside data_service.py:** The calculation belongs in `risk_service.py` as a pure function. `data_service.py` only does field mapping and data retrieval. [CITED: CONTEXT.md D-01, D-03]
- **Don't silently default missing fields to 0:** Per D-08, throw `DataValidationError` when required fields are missing. The current code uses `.get(field, 0)` defaults which is the exact pattern we're fixing.
- **Don't modify `calculate_beneish_m_score()`:** Per D-03, it stays unchanged. It only does the linear combination of pre-calculated indices.
- **Don't create new API endpoints:** The existing `POST /api/v1/analyze/risk` endpoint already calls the full pipeline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Financial ratio calculations with zero-division guard | Custom try/except per ratio | Helper function pattern from `calculate_piotroski_f_score` (`_ratio` helper) | F-Score already has `_ratio(numerator, denominator)` that returns 0.0 when denominator <= 0. Follow same pattern. |
| Field mapping from AKShare raw data | Custom per-field mapping logic | Established `dict.get("PRIMARY", dict.get("中文", dict.get("FALLBACK", 0)))` pattern | Existing pattern works, just needs more fields |
| Decimal precision for financial data | float arithmetic | Python `Decimal` type (already used in F-Score, `detect_存贷双高`) | Avoids floating point accumulation errors |

**Key insight:** The F-Score implementation (`calculate_piotroski_f_score` at risk_service.py:83-212) is the direct reference implementation for how M-Score indices should be calculated. It already receives raw financial data, computes ratios with Decimal precision, and handles zero denominators.

## Common Pitfalls

### Pitfall 1: Incorrect AKShare Field Names
**What goes wrong:** Using `LONGTERM_LOAN` (does not exist) instead of `LONG_LOAN`.
**Why it happens:** CONTEXT.md mapping table listed `LONGTERM_LOAN` as the AKShare field for long_term_debt, but live API verification shows the actual column is `LONG_LOAN`.
**How to avoid:** Use verified field names from live AKShare 1.18.46 queries. See Corrected Field Mapping table below.
**Warning signs:** `LONG_LOAN` returns `nan` for many companies (e.g., Maotai has no long-term loans). This is valid data, not a missing field.

### Pitfall 2: nan Values from AKShare
**What goes wrong:** AKShare returns `nan` (not `None` or `0`) for fields that don't apply to a company (e.g., Maotai's `LONG_LOAN = nan`, `GOODWILL = nan`).
**Why it happens:** AKShare uses pandas, which represents missing data as `nan`.
**How to avoid:** Convert values with `float(value or 0)` or check for `pd.isna()` before using. The existing `str()` wrapping in data_service.py handles this by converting `nan` to string "nan", which then becomes `0.0` when read back as float.
**Warning signs:** If M-Score calculation receives string "nan" instead of a number.

### Pitfall 3: Revenue Field Ambiguity
**What goes wrong:** Using `OPERATE_INCOME` (operating income, subset) instead of `TOTAL_OPERATE_INCOME` (total operating revenue).
**Why it happens:** Both exist in AKShare profit sheet. M-Score DSRI uses total revenue.
**How to avoid:** Use `TOTAL_OPERATE_INCOME` as primary field for `revenue`. This is already the pattern in existing code.

### Pitfall 4: Maotai as Test Stock Has Atypical Profile
**What goes wrong:** Testing only with Maotai (600519.SH) which has near-zero accounts receivable and no long-term debt, producing degenerate index values.
**Why it happens:** Maotai is a cash-rich consumer staples company with a unique business model.
**How to avoid:** Test with at least 2-3 stocks: Maotai (low receivables), a manufacturing company (normal receivables), and a company with known M-Score > -1.78. Use test fixtures with realistic data rather than relying solely on live API.

### Pitfall 5: Sign Convention for TATA
**What goes wrong:** Getting the sign wrong on TATA formula. `TATA = (Net Income - Operating Cash Flow) / Total Assets`.
**Why it happens:** When OCF > Net Income, TATA is negative (good -- earnings are cash-backed). When Net Income > OCF, TATA is positive (bad -- accruals are high).
**How to avoid:** Follow the Beneish 1999 formula exactly. Positive TATA contributes to higher (worse) M-Score via the `+4.679 * TATA` coefficient.

### Pitfall 6: Frozen Pydantic Model Extension
**What goes wrong:** Trying to mutate `MScoreData` in place after construction.
**Why it happens:** `MScoreData` has `model_config = {"frozen": True}`.
**How to avoid:** Create a new `MScoreData` instance with extended fields. Or create a new model class that includes audit fields.

### Pitfall 7: M-Score Index Hardcoded Values in Three Places
**What goes wrong:** Only fixing the AKShare mapping but leaving efinance and Tushare with hardcoded 1.0/0.0 values.
**Why it happens:** Three separate `_get_financial_report_from_*` methods each have their own hardcoded values.
**How to avoid:** All three source methods must be updated to include the new M-Score fields. Per D-01, the mapping layer is per-source but the calculation in `risk_service.py` is unified.

## Code Examples

### Corrected AKShare Field Mapping for M-Score

Verified via live AKShare 1.18.46 query against stock 600519.SH (Maotai):

| Internal Standard Name | AKShare Field | Source Statement | Verified | Notes |
|---|---|---|---|---|
| revenue | TOTAL_OPERATE_INCOME | profit_sheet | YES | 150.56B (2023) |
| net_income | NETPROFIT | profit_sheet | YES | 77.52B (2023) |
| operating_cash_flow | NETCASH_OPERATE | cash_flow_sheet | YES | 38.20B (2023) |
| accounts_receivable | ACCOUNTS_RECE | balance_sheet | YES | 60.37M (2023) |
| cost_of_goods | OPERATE_COST | profit_sheet | YES | 11.87B (2023) |
| total_current_assets | TOTAL_CURRENT_ASSETS | balance_sheet | YES | 225.17B (2023) |
| total_assets | TOTAL_ASSETS | balance_sheet | YES | 272.70B (2023) |
| ppe (fixed assets) | FIXED_ASSET | balance_sheet | YES | 19.91B (2023) |
| sga_expense | TOTAL_OPERATE_COST | profit_sheet | YES | 41.43B (2023) -- D-04 proxy |
| depreciation | (N/A) | - | DEPI = 1.0 per D-05 | |
| long_term_debt | LONG_LOAN | balance_sheet | YES | nan for Maotai (valid) |
| total_liabilities | TOTAL_LIABILITIES | balance_sheet | YES | 49.04B (2023) |
| total_current_liabilities | TOTAL_CURRENT_LIAB | balance_sheet | YES | 48.70B (2023) |

**Critical correction:** CONTEXT.md listed `LONGTERM_LOAN` as the AKShare field for long_term_debt. Live verification shows the actual field is `LONG_LOAN`. Planner must use `LONG_LOAN`.

### M-Score Index Formulas (Beneish 1999)

```python
# Source: Beneish, M. D. (1999). The detection of earnings manipulation.
# Financial Analysts Journal, 55(5), 24-36.
# Verified against formula in doc/M-Score 与 F-Score：投资分析.md

def calculate_mscore_indices(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> dict[str, Any]:
    """Calculate 8 M-Score indices from two-year standardized data.

    Each index is a year-over-year ratio (current / previous).
    """

    def _safe_ratio(num: float, denom: float) -> float | None:
        """Return ratio or None if denominator is zero."""
        if denom == 0:
            return None
        return num / denom

    # DSRI: Days' Sales Receivables Index
    # (AR_curr / Revenue_curr) / (AR_prev / Revenue_prev)
    dsri = _safe_ratio(
        current["accounts_receivable"] / current["revenue"],
        previous["accounts_receivable"] / previous["revenue"],
    )

    # GMI: Gross Margin Index
    # GrossMargin_prev / GrossMargin_curr
    gm_curr = (current["revenue"] - current["cost_of_goods"]) / current["revenue"]
    gm_prev = (previous["revenue"] - previous["cost_of_goods"]) / previous["revenue"]
    gmi = _safe_ratio(gm_prev, gm_curr)

    # AQI: Asset Quality Index
    # (1 - (CA_curr - PPE_curr) / TA_curr) / (1 - (CA_prev - PPE_prev) / TA_prev)
    aq_curr = 1 - (current["total_current_assets"] - current["ppe"]) / current["total_assets"]
    aq_prev = 1 - (previous["total_current_assets"] - previous["ppe"]) / previous["total_assets"]
    aqi = _safe_ratio(aq_curr, aq_prev)

    # SGI: Sales Growth Index
    # Revenue_curr / Revenue_prev
    sgi = _safe_ratio(current["revenue"], previous["revenue"])

    # DEPI: Depreciation Index = 1.0 (D-05 MVP simplification)
    depi = 1.0

    # SGAI: SGA Expense Index
    # (SGA_curr / Revenue_curr) / (SGA_prev / Revenue_prev)
    sgai = _safe_ratio(
        current["sga_expense"] / current["revenue"],
        previous["sga_expense"] / previous["revenue"],
    )

    # LVGI: Leverage Index
    # (TL_curr / TA_curr) / (TL_prev / TA_prev)
    lvgi = _safe_ratio(
        current["total_liabilities"] / current["total_assets"],
        previous["total_liabilities"] / previous["total_assets"],
    )

    # TATA: Total Accruals to Total Assets
    # (NetIncome - OperatingCashFlow) / TotalAssets
    tata = (current["net_income"] - current["operating_cash_flow"]) / current["total_assets"]

    # Return with defaults for non-calculable indices
    return {
        "dsri": dsri if dsri is not None else 1.0,
        "gmi": gmi if gmi is not None else 1.0,
        "aqi": aqi if aqi is not None else 1.0,
        "sgi": sgi if sgi is not None else 1.0,
        "depi": depi,
        "sgai": sgai if sgai is not None else 1.0,
        "lvgi": lvgi if lvgi is not None else 1.0,
        "tata": tata,
        "non_calculable": [...],  # list of indices that were None
        "audit_trail": {...},     # per-index numerator/denominator/source
    }
```

### Existing Integration Point in risk_service.py

```python
# risk_service.py line 396-510: analyze_financial_risk()
# Current flow:
m_score_result = calculate_beneish_m_score(current_report, previous_report or {})

# New flow (insert BEFORE calculate_beneish_m_score):
mscore_indices = calculate_mscore_indices(current_report, previous_report or {})

# Inject calculated indices into current_report for calculate_beneish_m_score:
enriched_current = {
    **current_report,
    "days_sales_receivables_index": mscore_indices["dsri"],
    "gross_margin_index": mscore_indices["gmi"],
    "asset_quality_index": mscore_indices["aqi"],
    "sales_growth_index": mscore_indices["sgi"],
    "depreciation_index": mscore_indices["depi"],
    "sga_expense_index": mscore_indices["sgai"],
    "leverage_index": mscore_indices["lvgi"],
    "total_accruals_to_assets": mscore_indices["tata"],
}

m_score_result = calculate_beneish_m_score(enriched_current, previous_report or {})
```

### New Fields to Add in data_service.py

For `_get_financial_report_from_akshare()` (line ~845):

```python
# ADD these fields to the report dict:
"cost_of_goods": str(
    income.get("OPERATE_COST", income.get("营业成本", 0))
),
"sga_expense": str(
    income.get("TOTAL_OPERATE_COST", income.get("营业总成本", 0))
),
"total_current_assets": str(
    balance.get("TOTAL_CURRENT_ASSETS", balance.get("流动资产合计", 0))
),
"ppe": str(
    balance.get("FIXED_ASSET", balance.get("固定资产", 0))
),
"long_term_debt": str(
    balance.get("LONG_LOAN", balance.get("长期借款", 0))
),
# Note: remove the 8 hardcoded index lines (days_sales_receivables_index, etc.)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded M-Score indices (1.0/0.0) | Real calculation from two-year data | This phase | M-Score becomes meaningful for fraud detection |
| LONGTERM_LOAN field name | LONG_LOAN field name | Discovered during research | CONTEXT.md had incorrect field name |

**Deprecated/outdated:**
- The 8 hardcoded index fields in `data_service.py` (`days_sales_receivables_index`, `gross_margin_index`, etc.) will be removed and replaced with raw financial fields.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `OPERATE_COST` in AKShare profit sheet maps to "cost of goods sold" for GMI calculation | Standard Stack | If OPERATE_COST is actually total operating cost (not COGS), GMI formula would need adjustment. Verified: AKShare has both `OPERATE_COST` (营业成本, COGS) and `TOTAL_OPERATE_COST` (营业总成本). Use `OPERATE_COST` for GMI, `TOTAL_OPERATE_COST` for SGAI per D-04. |
| A2 | D-04 "OPERATE_EXPENSE" in CONTEXT.md maps to `TOTAL_OPERATE_COST` in AKShare | Architecture | The CONTEXT.md says use `OPERATE_EXPENSE` as proxy, but AKShare has `TOTAL_OPERATE_COST` not `OPERATE_EXPENSE`. `OPERATE_EXPENSE` does NOT appear in AKShare profit sheet columns. Planner should use `TOTAL_OPERATE_COST` for the SG&A proxy. |
| A3 | DEPI = 1.0 is acceptable for CSI 300 MVP stocks | Standard Stack | For companies with significant depreciation changes, DEPI = 1.0 masks real signal. Locked decision D-05. |

## Open Questions

1. **SG&A Proxy Field Resolution**
   - What we know: D-04 says use `OPERATE_EXPENSE` as proxy. But AKShare profit sheet does NOT have an `OPERATE_EXPENSE` column.
   - What's unclear: Does D-04 mean `TOTAL_OPERATE_COST` (total operating cost = 营业总成本)? Or should we sum `SALE_EXPENSE + MANAGE_EXPENSE` (which are individually available)?
   - Recommendation: Use `TOTAL_OPERATE_COST` as the SG&A proxy since it's the closest match to "operating expenses" and is already used in the existing `_calculate_gross_margin_from_akshare` method. This needs user confirmation since it differs from the literal `OPERATE_EXPENSE` name in D-04.

2. **LVGI Formula Choice**
   - What we know: LVGI in Beneish 1999 uses long-term debt to total assets ratio. CONTEXT.md field mapping includes `long_term_debt` -> `LONG_LOAN`.
   - What's unclear: Should LVGI use `(total_liabilities / total_assets)` or `(long_term_debt / total_assets)`? The CONTEXT.md mapping table includes both.
   - Recommendation: Use `total_liabilities / total_assets` as the leverage ratio, since `LONG_LOAN` is `nan` for many companies (including Maotai). This gives a more universally applicable ratio.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.12.4 | -- |
| AKShare | Data source | Yes | 1.18.46 | efinance / Tushare |
| efinance | Secondary data source | Yes (installed) | 0.5+ | -- |
| pytest | Testing | Yes | 9.0.2 | -- |
| hypothesis | Property testing | Yes | 6.x | -- |
| PostgreSQL | DB persistence | Not verified | -- | Phase 1 code changes don't require live DB |
| uv | Package management | Yes | -- | -- |

**Missing dependencies with no fallback:**
- None. All required tools are available.

**Missing dependencies with fallback:**
- PostgreSQL not needed for this phase (code-only changes, tests use mocks).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 with hypothesis |
| Config file | `stockvaluefinder/pytest.ini` |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py -x -q` |
| Full suite command | `cd stockvaluefinder && uv run pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RISK-01 | DSRI from actual AR/revenue data | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_dsri_calculation -x` | No -- Wave 0 |
| RISK-02 | GMI from gross margin data | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_gmi_calculation -x` | No -- Wave 0 |
| RISK-03 | AQI from balance sheet data | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_aqi_calculation -x` | No -- Wave 0 |
| RISK-04 | SGI from revenue data | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_sgi_calculation -x` | No -- Wave 0 |
| RISK-05 | DEPI = 1.0 | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_depi_default -x` | No -- Wave 0 |
| RISK-06 | SGAI from SGA/revenue ratio | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_sgai_calculation -x` | No -- Wave 0 |
| RISK-07 | LVGI from liabilities/assets ratio | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_lvgi_calculation -x` | No -- Wave 0 |
| RISK-08 | TATA from NI/OCF/assets | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_tata_calculation -x` | No -- Wave 0 |
| RISK-09 | M-Score composite with audit trail | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_composite_with_audit -x` | No -- Wave 0 |
| RISK-10 | API response includes index breakdown | unit | `uv run pytest tests/unit/test_services/test_risk_service.py::TestMScoreIndices::test_index_breakdown_in_result -x` | No -- Wave 0 |

### Additional Test Cases Needed
| Test | Purpose | Type |
|------|---------|------|
| test_zero_denominator_handling | D-09: zero denom produces warning, not crash | unit |
| test_missing_field_raises_error | D-08: DataValidationError on missing required field | unit |
| test_nan_value_handling | AKShare nan values don't propagate | unit |
| test_maotai_2023_manual_verification | Match manual M-Score calculation for 600519.SH | unit |
| test_analyze_financial_risk_integration | Full pipeline produces RiskScore with real indices | unit |

### Sampling Rate
- **Per task commit:** `cd stockvaluefinder && uv run pytest tests/unit/test_services/test_risk_service.py -x -q`
- **Per wave merge:** `cd stockvaluefinder && uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_services/test_risk_service.py` -- add `TestMScoreIndices` class with all index tests
- [ ] `tests/unit/test_services/test_risk_service.py` -- add tests for `calculate_mscore_indices` function
- [ ] `tests/unit/test_services/test_risk_service.py` -- add Maotai manual verification test with known values
- [ ] Existing test file has `TestBeneishMScore` that tests the linear combination -- these should still pass unchanged

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Pydantic model validation in MScoreData, DataValidationError for missing fields |
| V6 Cryptography | no | No cryptographic operations in this phase |

### Known Threat Patterns for Python Financial Calculation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| NaN injection from external data | Tampering | Validate all numeric fields from AKShare, convert nan to explicit errors or zero |
| Division by zero crash | Denial of Service | D-09: catch zero denominators, mark as non-calculable |
| Silent data corruption (wrong field mapping) | Tampering | D-11: audit trail with source field references enables verification |

## Sources

### Primary (HIGH confidence)
- AKShare 1.18.46 live API verification -- field names confirmed via `stock_profit_sheet_by_report_em`, `stock_balance_sheet_by_report_em`, `stock_cash_flow_sheet_by_report_em` for symbol SH600519
- `stockvaluefinder/stockvaluefinder/services/risk_service.py` -- existing M-Score formula verified correct
- `stockvaluefinder/stockvaluefinder/external/data_service.py` -- integration points verified (lines 895-902, 974-981, 1044-1051)
- `doc/M-Score 与 F-Score：投资分析.md` -- business logic reference

### Secondary (MEDIUM confidence)
- CONTEXT.md field mapping table -- used as starting point, but field `LONGTERM_LOAN` corrected to `LONG_LOAN` via live verification
- Beneish, M. D. (1999). The detection of earnings manipulation. Financial Analysts Journal, 55(5), 24-36. [CITED: risk_service.py docstring]

### Tertiary (LOW confidence)
- None -- all findings verified via code inspection or live API queries

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already installed and verified
- Architecture: HIGH -- existing codebase patterns are clear and consistent
- Field mapping: HIGH -- verified via live AKShare 1.18.46 API queries
- Pitfalls: HIGH -- identified through code analysis and live data testing

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable codebase, AKShare field names may change with major updates)
