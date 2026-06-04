# Phase 9: ROIC-WACC Spread Analysis - Research

**Researched:** 2026-05-03
**Domain:** Financial analysis -- ROIC, NOPAT, WACC with debt weighting, moat trend detection
**Confidence:** HIGH

## Summary

Phase 9 adds ROIC-WACC spread analysis to StockValueFinder, enabling users to evaluate whether a stock creates or destroys value by comparing ROIC against true WACC. The core calculation chain is: extract financial data from AKShare -> compute NOPAT (sector-aware) -> compute Invested Capital -> compute ROIC -> compute true WACC (with debt weighting) -> compute spread -> detect 3-year trend for moat identification. All inputs are available from existing AKShare functions (profit sheet, balance sheet, cash flow sheet). No new API endpoints need to be added to AKShare; only a new multi-year fetch method is needed on the existing AKShareClient.

The existing `calculate_wacc()` in `valuation_service.py` computes only the cost of equity (Ke = Rf + beta * ERP). Per D-01, this function must be extended with optional debt parameters (`debt_weight`, `cost_of_debt`, `tax_rate`) that default to 0 for backward compatibility. The existing DCF pipeline continues using Ke-only WACC unchanged. The new ROIC-WACC pipeline passes debt params to compute true WACC = We * Ke + Wd * Kd * (1 - T).

The most critical finding from research: the `StockDB` model uses `industry` (not `sector` as stated in D-09). AKShare returns Shenwan Level 2 industry names like "银行II", "证券II", "保险II" for financial companies. The financial sector detection must use `stock.industry` field and check for substring matches against "银行", "保险", "证券". Additionally, scipy is NOT installed in the project venv -- it must be added via `uv add "scipy>=1.15.0"` as the first step.

**Primary recommendation:** Extend `calculate_wacc()` with backward-compatible optional debt params, create a new `roic_service.py` with pure functions, add `fetch_multi_year_financials()` to AKShareClient, and use `scipy.stats.linregress` for 3-year moat trend detection.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Extend existing `calculate_wacc()` in `valuation_service.py` with optional debt parameters (`debt_weight`, `cost_of_debt`, `tax_rate`) defaulting to 0. Existing DCF calls continue to work unchanged (Ke-only). New ROIC-WACC calls pass debt params for true WACC.
- **D-02:** Cost of debt (Kd) is implied from financials: `finance_expense / total_interest_bearing_debt` from AKShare balance sheet data.
- **D-03:** ROIC-WACC API response includes full WACC breakdown: Ke, Kd, D/E ratio, tax rate, equity weight, debt weight.
- **D-04:** Add `fetch_multi_year_financials(ticker, years=3)` method to existing `AKShareClient`. Calls AKShare API once (returns all years), filters in-memory for the requested years.
- **D-05:** Multi-year financial data cached in Redis with 24h TTL, consistent with existing financials caching pattern.
- **D-06:** Three-state trend classification using `scipy.stats.linregress` on 3-year ROIC-WACC spread: "Competitive Advantage" (slope > 0.005/yr), "Deteriorating" (slope < -0.005/yr), "Stable" (between +/-0.005/yr).
- **D-07:** Generic labels only -- "Competitive Advantage", "Deteriorating", "Stable". No PRD-specific moat type heuristics (intangible/scale) at this stage.
- **D-08:** Negative invested capital (cash > equity + debt): return ROIC = None with flag `negative_invested_capital`. Do NOT compute negative ROIC value.
- **D-09:** Auto-detect financial sector from `stock.sector` field in database. If sector contains "银行", "保险", or "证券", use financial NOPAT formula.
- **D-10:** Financial sector NOPAT: `OPERATE_PROFIT * (1 - tax_rate)`. Non-financial sector NOPAT: `(TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)`.
- **D-11:** NaN debt fields (debt-free companies): normalize to 0.0. WACC for debt-free companies equals Ke (cost of equity only), same as existing behavior.

### Claude's Discretion
- Exact API endpoint path and request/response model structure
- New ORM model field names and Alembic migration details
- Internal helper function organization within roic_service.py
- Test file structure and test case selection

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ROIC-01 | User can calculate ROIC (NOPAT / Invested Capital) from AKShare financial data for any CSI 300 stock | AKShare field mapping verified live (TOTAL_PROFIT, FINANCE_EXPENSE, INCOME_TAX, TOTAL_PARENT_EQUITY, SHORT_LOAN, LONG_LOAN, BOND_PAYABLE). NOPAT formula defined per D-10. Invested Capital = Equity + ST Debt + LT Debt + Bonds - Treasury Shares. |
| ROIC-02 | User can calculate true WACC (weighted cost of equity + after-tax cost of debt) with debt/equity ratio from balance sheet | D-01 extends `calculate_wacc()` with optional debt params. D-02: Kd = finance_expense / interest_bearing_debt. D-03: Full breakdown in response. |
| ROIC-03 | User can view ROIC-WACC spread with classification (value creating vs destroying) | Spread = ROIC - WACC. Classification: positive = "Value Creating", negative = "Value Destroying". Straightforward comparison. |
| ROIC-04 | System detects financial sector stocks and applies correct NOPAT formula | D-09: Detect from `stock.industry` field (NOT `sector` -- actual DB column is `industry`). AKShare returns "银行II", "证券II", "保险II" for financials. D-10 defines dual formula. |
| ROIC-05 | System handles edge cases: negative invested capital (cash-rich companies), NaN debt fields (debt-free companies) | D-08: Negative IC -> ROIC = None + flag. D-11: NaN debt -> normalize to 0.0. Pattern exists in `risk_service.py:_safe_ratio()`. |
| ROIC-06 | User can view 3-year ROIC-WACC spread trend with moat detection (widening spread flagged as competitive advantage) | D-06: `scipy.stats.linregress` for 3-point regression. D-07: Three-state labels. scipy NOT in project venv -- must add via `uv add`. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ROIC calculation (NOPAT, Invested Capital) | API / Backend | -- | Pure function in services layer, no client-side computation |
| True WACC with debt weighting | API / Backend | -- | Extends existing `calculate_wacc()` in valuation_service.py |
| Multi-year financial data fetch | API / Backend | Database / Storage | AKShareClient fetches, Redis caches, PostgreSQL persists results |
| Sector detection (financial vs non-financial) | API / Backend | Database / Storage | Reads `stock.industry` from PostgreSQL `stocks` table |
| Moat trend detection (3-year linregress) | API / Backend | -- | Pure function using scipy.stats.linregress |
| ROIC analysis persistence | Database / Storage | -- | New ORM model, Alembic migration, Repository pattern |
| ROIC analysis API endpoint | Frontend Server (SSR) | -- | New route file `roic_routes.py` following existing POST pattern |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scipy | >=1.15.0 | 3-year trend line regression (moat detection) | `scipy.stats.linregress` provides slope + p-value for trend significance. Must be added to project venv -- NOT currently installed. [VERIFIED: `importlib.util.find_spec('scipy')` returned `None` in project venv] |
| numpy | 2.4.2 (installed) | Array operations for multi-year financial data | Already installed as transitive dependency. No action needed. [VERIFIED: `numpy.__version__` = '2.4.2'] |
| AKShare | 1.18.46 (installed) | Financial data source for ROIC inputs | Already installed. `stock_profit_sheet_by_report_em` and `stock_balance_sheet_by_report_em` provide all needed columns. [VERIFIED: `akshare.__version__` = '1.18.46'] |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic | >=2.12.5 | ROIC domain models (frozen), request/response models | New `models/roic.py` with frozen dataclass-like models |
| SQLAlchemy | >=2.0.47 | ORM model for ROIC analysis persistence | New `db/models/roic.py` following RiskScoreDB pattern |
| Alembic | >=1.18.4 | Database migration for new `roic_results` table | Migration 011_alpha_engine_tables.py (revision "011", revises "010") |
| redis | >=7.2.1 | Cache multi-year financial data with 24h TTL | Reuse `CacheManager._cache_get_or_set()` pattern from `data_service.py` |
| FastAPI | >=0.133.1 | API route for ROIC-WACC analysis | New `roic_routes.py` with `POST /api/v1/analyze/roic` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy.stats.linregress | numpy polyfit | linregress provides p-value; polyfit only gives coefficients. For 3-point regression with significance testing, linregress is standard. |
| scipy.stats.linregress | Manual slope calculation | Error-prone; duplicates battle-tested code. Not worth the risk for financial calculations. |

**Installation:**
```bash
cd stockvaluefinder
uv add "scipy>=1.15.0"
```

**Version verification:** Before writing the Standard Stack table, verify each recommended package version is current:
```bash
# scipy: NOT currently installed in project venv
/home/robertzeng/project/stockvalue/stockvalue_backend/stockvaluefinder/.venv/bin/python -c "import scipy"
# -> ModuleNotFoundError -- MUST add

# numpy: already at 2.4.2
/home/robertzeng/project/stockvalue/stockvalue_backend/stockvaluefinder/.venv/bin/python -c "import numpy; print(numpy.__version__)"
# -> 2.4.2
```

## Architecture Patterns

### System Architecture Diagram

```
API Request (POST /api/v1/analyze/roic)
    |
    v
roic_routes.py (route handler)
    |
    |-- [1] data_service.get_financial_report(ticker, year) -> current year data
    |-- [2] data_service.get_financial_report(ticker, year-1) -> previous year data
    |-- [3] data_service.get_multi_year_financials(ticker, years=3) -> 3-year trend data
    |       |
    |       v
    |    AKShareClient.fetch_multi_year_financials()
    |       |-> stock_profit_sheet_by_report_em(symbol)
    |       |-> stock_balance_sheet_by_report_em(symbol)
    |       |-> Filter by fiscal_year in-memory
    |       |-> Cache result in Redis (24h TTL)
    |
    |-- [4] stock_repo.get_by_ticker(ticker) -> read stock.industry for sector detection
    |
    v
roic_service.py (pure functions)
    |
    |-- calculate_nopat(financials, is_financial_sector) -> NOPAT
    |       |-- Financial: OPERATE_PROFIT * (1 - tax_rate)
    |       |-- Non-financial: (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)
    |
    |-- calculate_invested_capital(balance_sheet) -> IC
    |       |-- IC = Equity + ST_Debt + LT_Debt + Bonds - Treasury_Shares
    |       |-- If IC <= 0: return None with flag
    |
    |-- calculate_roic(nopat, invested_capital) -> ROIC | None
    |
    |-- calculate_wacc(rf, beta, erp, debt_weight?, cost_of_debt?, tax_rate?) -> WACC
    |       |-- Extended from valuation_service.py (backward compatible)
    |
    |-- calculate_roic_wacc_spread(roic, wacc) -> spread, classification
    |
    |-- analyze_roic_trend(spreads_3yr) -> trend label + slope + p-value
    |       |-- scipy.stats.linregress([0,1,2], spreads)
    |       |-- slope > 0.005 -> "Competitive Advantage"
    |       |-- slope < -0.005 -> "Deteriorating"
    |       |-- else -> "Stable"
    |
    v
API Response (ApiResponse[ROICAnalysisResult])
    |
    v
Persistence (roic_repo.upsert -> PostgreSQL)
```

### Recommended Project Structure
```
stockvaluefinder/
├── services/
│   ├── roic_service.py           # NEW: ROIC, NOPAT, IC, spread, trend pure functions
│   └── valuation_service.py      # MODIFY: extend calculate_wacc() with optional debt params
├── models/
│   └── roic.py                   # NEW: ROICAnalysisResult, ROICAnalysisRequest, etc.
├── db/models/
│   └── roic.py                   # NEW: ROICResultDB ORM model
├── repositories/
│   └── roic_repo.py              # NEW: ROICResultRepository with upsert pattern
├── api/
│   └── roic_routes.py            # NEW: POST /api/v1/analyze/roic endpoint
├── external/
│   ├── akshare_client.py         # MODIFY: add fetch_multi_year_financials()
│   └── data_service.py           # MODIFY: add get_roic_inputs() orchestration
├── config.py                     # MODIFY: add ROICConfig frozen dataclass
└── tests/
    ├── unit/
    │   ├── test_roic_service.py  # NEW: unit tests for pure functions
    │   └── test_api/
    │       └── test_roic_routes.py # NEW: API route tests
    └── conftest.py               # MODIFY: add make_roic_report fixture
```

### Pattern 1: Extend calculate_wacc() (D-01 Backward Compatibility)
**What:** Add optional debt params to existing WACC function, preserving Ke-only behavior
**When to use:** When computing WACC for ROIC-WACC spread analysis
**Example:**
```python
# Source: valuation_service.py (extended per D-01)
def calculate_wacc(
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float,
    # New optional debt params (D-01: default to 0 for backward compat)
    debt_weight: float = 0.0,
    cost_of_debt: float = 0.0,
    tax_rate: float = 0.0,
) -> float:
    """Calculate WACC with optional debt weighting.

    When debt params are 0 (default), returns Ke = Rf + beta * ERP
    (backward compatible with existing DCF pipeline).

    When debt params provided, returns true WACC = We*Ke + Wd*Kd*(1-T).
    """
    cost_of_equity = risk_free_rate + (beta * market_risk_premium)
    equity_weight = 1.0 - debt_weight
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)
```

### Pattern 2: Sector-Aware NOPAT Calculation (D-09, D-10)
**What:** Branch NOPAT formula based on industry classification
**When to use:** When computing NOPAT for any stock
**Example:**
```python
# Source: roic_service.py (new)
FINANCIAL_SECTOR_KEYWORDS = ("银行", "保险", "证券")

def is_financial_sector(industry: str) -> bool:
    """Check if stock belongs to financial sector via industry name.

    AKShare returns Shenwan L2 names: '银行Ⅱ', '证券Ⅱ', '保险Ⅱ'.
    """
    return any(kw in industry for kw in FINANCIAL_SECTOR_KEYWORDS)

def calculate_nopat(
    profit_data: dict[str, Any],
    is_financial: bool,
) -> tuple[float, dict[str, Any]]:
    """Calculate NOPAT with sector-aware formula (D-10).

    Financial: OPERATE_PROFIT * (1 - tax_rate)
    Non-financial: (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)

    Returns (nopat, audit_trail) tuple.
    """
    ...
```

### Pattern 3: Multi-Year Data Fetch (D-04)
**What:** Fetch 3 years of financial data in one AKShare call, filter in-memory
**When to use:** When computing moat trend
**Example:**
```python
# Source: akshare_client.py (extended per D-04)
async def fetch_multi_year_financials(
    self,
    ts_code: str,
    years: int = 3,
) -> list[dict[str, Any]]:
    """Fetch multi-year financial data (profit + balance sheet).

    Calls AKShare once (returns all years), filters in-memory.
    Cache entire result with 24h TTL (D-05).
    """
    ...
```

### Anti-Patterns to Avoid
- **Duplicating WACC calculation:** Do NOT copy `calculate_wacc()` into `roic_service.py`. Import from `valuation_service.py` -- single source of truth. [CITED: PITFALLS.md Pitfall 2]
- **Using `stock.sector` field:** The database uses `industry`, not `sector`. D-09 says "stock.sector" but the actual `StockDB` ORM model has `industry: Mapped[str]`. Use `stock.industry`. [VERIFIED: `db/models/stock.py` line 38-43]
- **Computing ROIC with negative invested capital:** D-08 explicitly says return None with flag. Never compute a negative ROIC value. [CITED: PITFALLS.md Pitfall 1]
- **Passing NaN to scipy.linregress:** NaN propagates through linregress, producing `slope=nan`. Must filter out years where ROIC is None before regression. [VERIFIED: tested `linregress([0,1,2], [0.03, float('nan'), 0.08])` -> `slope=nan`]
- **Using `TREASURY_SHARES` as buyback amount:** It is a cumulative stock, not annual flow. Not relevant for this phase but noted for Phase 10.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 3-year trend regression | Manual slope/p-value calculation | `scipy.stats.linregress` | Battle-tested, provides p-value for significance. 3-point regression has edge cases (perfect fit, NaN). |
| Division-by-zero in ratios | Custom if/else chains | `_safe_ratio()` pattern from `risk_service.py:207-215` | Already proven in M-Score calculation. Returns `(None, num, denom)` tuple for audit trail. |
| NaN normalization for debt fields | Per-field nan checks | `_to_float()` pattern from `risk_service.py:104-114` | Handles None, NaN, empty string, invalid types. Already used throughout codebase. |
| Cache multi-year financials | New caching decorator | `_cache_get_or_set()` in `data_service.py` | Existing pattern with cache versioning, TTL, graceful degradation. |
| JSON serialization for cache | Custom serializer | `_make_serializable()` in `data_service.py:191-200` | Handles UUID, Decimal, nested dicts/lists. |

**Key insight:** The codebase has well-established patterns for division safety (`_safe_ratio`), NaN handling (`_to_float`), and caching (`_cache_get_or_set`). The ROIC service should reuse these exact patterns, not invent new ones.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | No ROIC results exist yet in PostgreSQL | Code only -- new table via Alembic migration 011 |
| Live service config | Redis cache keys will use new prefix `roic_analysis` | Code only -- no runtime config changes needed |
| OS-registered state | None | None -- verified no OS-level registrations |
| Secrets/env vars | No new env vars needed; reuses existing `DATABASE_URL`, `REDIS_URL`, `LLM_*` | None |
| Build artifacts | `pyproject.toml` needs `scipy>=1.15.0` added | `uv add "scipy>=1.15.0"` -- required before implementation |

## Common Pitfalls

### Pitfall 1: WACC Function Name vs Behavior Mismatch
**What goes wrong:** The existing `calculate_wacc()` only computes Ke (cost of equity), not true WACC. Developers may assume it handles debt weighting because of the name.
**Why it happens:** The docstring says "Using CAPM: WACC = Rf + beta * ERP" which is actually the CAPM formula for Ke, not WACC. [VERIFIED: `valuation_service.py:11-34`]
**How to avoid:** D-01 addresses this by extending the same function with optional debt params. The default behavior (debt params = 0) returns Ke-only, identical to current behavior. When ROIC-WACC passes debt params, it computes true WACC.
**Warning signs:** ROIC-WACC spread shows identical WACC for leveraged and unleveraged companies.

### Pitfall 2: D-09 Says "stock.sector" But Actual Field Is "stock.industry"
**What goes wrong:** Code written to read `stock.sector` fails at runtime because the `StockDB` model uses `industry` as the column name.
**Why it happens:** CONTEXT.md D-09 was written during discussion and used the word "sector" generically. The actual database schema uses `industry` for the industry classification column.
**How to avoid:** Use `stock.industry` field. Verified: `StockDB` model at `db/models/stock.py:38-43` defines `industry: Mapped[str]`. AKShare populates this from `stock_individual_info_em` response field "行业". [VERIFIED: live data shows "银行II", "证券II", "保险II"]
**Warning signs:** AttributeError on `stock.sector`, or KeyError on dict access.

### Pitfall 3: NaN Propagation Through scipy.linregress
**What goes wrong:** If any year in the 3-year spread data has ROIC=None (due to negative invested capital), and the code passes `float('nan')` to linregress, the result is `slope=nan`, breaking trend classification.
**Why it happens:** D-08 says negative IC -> ROIC = None. When building the 3-year array for linregress, None years must be excluded, not converted to NaN.
**How to avoid:** Filter out years where ROIC is None before passing to linregress. If fewer than 2 valid years remain, return "Insufficient Data" instead of a trend label.
**Warning signs:** Moat trend shows "nan" instead of a classification label.

### Pitfall 4: Financial Sector NOPAT Double-Counting
**What goes wrong:** For banks/insurance/securities, adding `FINANCE_EXPENSE` back to `TOTAL_PROFIT` double-counts interest income (which is a core operating item for financials, not a financing cost).
**Why it happens:** The standard NOPAT formula (EBIT = Total Profit + Finance Expense) assumes interest is a financing item. For financials, it is an operating item.
**How to avoid:** D-10 defines dual formula. Financial: `OPERATE_PROFIT * (1 - tax_rate)`. Non-financial: `(TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)`. Must detect sector first. [VERIFIED: AKShare returns "银行II" for ICBC, "证券II" for CITIC, "保险II" for Ping An]
**Warning signs:** ICBC (601398.SH) shows NOPAT exceeding total profit.

### Pitfall 5: AKShare Debt Fields Return NaN for Debt-Free Companies
**What goes wrong:** Companies like Maotai (600519.SH) carry no bank borrowings. AKShare returns NaN for `SHORT_LOAN` and `LONG_LOAN`. If NaN propagates to WACC or invested capital calculations, all downstream computations produce NaN.
**Why it happens:** NaN is AKShare's way of indicating "not applicable" or "zero" for balance sheet fields that don't apply to a company.
**How to avoid:** D-11: Normalize NaN debt fields to 0.0 using the existing `_to_float()` pattern. Invested capital becomes just equity (debt-free). WACC becomes Ke-only (same as current behavior). [VERIFIED: AKShare returns NaN for SHORT_LOAN/LONG_LOAN on Maotai]
**Warning signs:** Any financial ratio output shows "nan" instead of a number.

### Pitfall 6: Only 2 Years of Valid Data for 3-Year Trend
**What goes wrong:** If a stock has 3 years of financial data but one year has negative invested capital (ROIC = None), only 2 valid spread values remain. linregress with 2 points works but produces `pvalue=0.0` (perfect fit), which is misleading.
**Why it happens:** Survivorship and data quality issues. IPO within 3 years, or data gaps in AKShare.
**How to avoid:** Require minimum 3 valid data points for trend classification. With fewer, return "Insufficient Data" flag. With exactly 2, compute slope but mark as "Low Confidence" in audit trail. [VERIFIED: `linregress([0,1], [0.03, 0.05])` returns `pvalue=0.0`]
**Warning signs:** All stocks with 2-year data show identical trend confidence.

## Code Examples

Verified patterns from the existing codebase:

### Extend calculate_wacc() (D-01 Pattern)
```python
# Source: valuation_service.py (current, to be extended)
def calculate_wacc(
    risk_free_rate: float,
    beta: float,
    market_risk_premium: float,
    # NEW optional debt params (D-01)
    debt_weight: float = 0.0,     # D/(D+E)
    cost_of_debt: float = 0.0,    # Kd = finance_expense / interest_bearing_debt
    tax_rate: float = 0.0,        # T = income_tax / total_profit
) -> float:
    cost_of_equity = risk_free_rate + (beta * market_risk_premium)
    equity_weight = 1.0 - debt_weight
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)
```

### NaN-Safe Value Extraction (Existing Pattern to Reuse)
```python
# Source: risk_service.py:104-114
def _to_float(value: Any, field_name: str = "") -> float:
    """Convert a value to float, treating nan/None/empty as 0.0."""
    if value is None:
        return 0.0
    try:
        result = float(value)
        if result != result:  # NaN check
            return 0.0
        return result
    except (ValueError, TypeError):
        return 0.0
```

### Safe Division Pattern (Existing Pattern to Reuse)
```python
# Source: risk_service.py:207-215
def _safe_ratio(
    num: float, denom: float, index_name: str
) -> tuple[float | None, float, float]:
    """Return (ratio, numerator, denominator) or (None, num, denom) if denom is 0."""
    if denom == 0:
        non_calculable.append(index_name)
        red_flags.append(f"{index_name}: denominator is zero, index not calculable")
        return None, num, denom
    return num / denom, num, denom
```

### 3-Year Moat Trend with scipy (New Code)
```python
# Source: roic_service.py (new, per D-06)
from scipy.stats import linregress

MOAT_TREND_THRESHOLD = 0.005  # D-06: slope threshold per year

def analyze_roic_trend(
    spreads: list[float],
    years: list[int],
) -> dict[str, Any]:
    """Classify 3-year ROIC-WACC spread trend using linear regression (D-06).

    Filters out None/NaN spreads. Requires >= 3 valid points.
    Returns trend label, slope, p_value.
    """
    valid = [(y, s) for y, s in zip(years, spreads) if s is not None and s == s]
    if len(valid) < 3:
        return {
            "trend": "Insufficient Data",
            "slope": None,
            "p_value": None,
            "data_points": len(valid),
        }
    x = [i for i in range(len(valid))]
    y = [s for _, s in valid]
    result = linregress(x, y)
    if result.slope > MOAT_TREND_THRESHOLD:
        trend = "Competitive Advantage"
    elif result.slope < -MOAT_TREND_THRESHOLD:
        trend = "Deteriorating"
    else:
        trend = "Stable"
    return {
        "trend": trend,
        "slope": round(result.slope, 6),
        "p_value": round(result.pvalue, 6),
        "data_points": len(valid),
    }
```

### Sector Detection (New Code per D-09)
```python
# Source: roic_service.py (new)
# VERIFIED: AKShare returns "银行II", "证券II", "保险II" for financial stocks
FINANCIAL_SECTOR_KEYWORDS = ("银行", "保险", "证券")

def is_financial_sector(industry: str) -> bool:
    """Detect financial sector from stock.industry field.

    Uses substring matching against Shenwan L2 industry names.
    """
    if not industry:
        return False
    return any(kw in industry for kw in FINANCIAL_SECTOR_KEYWORDS)
```

### AKShare Field Mapping for ROIC Inputs (Verified Live Data)
```python
# Source: research/STACK.md (verified against 600519 live data)
# AKShare column -> ROIC input mapping:
ROIC_FIELD_MAP = {
    # Profit sheet fields
    "TOTAL_PROFIT": "total_profit",         # Pre-tax profit
    "FINANCE_EXPENSE": "finance_expense",   # Interest expense (negative = net income for banks)
    "INCOME_TAX": "income_tax",             # Tax paid
    "OPERATE_PROFIT": "operate_profit",     # Operating profit (used for financial NOPAT)

    # Balance sheet fields
    "TOTAL_PARENT_EQUITY": "equity",        # Shareholders' equity
    "SHORT_LOAN": "short_term_debt",        # Short-term borrowings (may be NaN!)
    "LONG_LOAN": "long_term_debt",          # Long-term borrowings (may be NaN!)
    "BOND_PAYABLE": "bonds_payable",        # Bond obligations (may be NaN!)
    "TREASURY_SHARES": "treasury_shares",   # Share repurchases (balance sheet)
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| scipy not needed | scipy required for trend detection | Phase 9 adds it | Must add via `uv add scipy` -- NOT in pyproject.toml yet |
| WACC = Ke only (DCF) | WACC = We*Ke + Wd*Kd*(1-T) (ROIC) | This phase | Extend function, don't replace. DCF stays Ke-only. |
| Single-year analysis | Multi-year trend analysis | This phase | New `fetch_multi_year_financials()` method on AKShareClient |

**Deprecated/outdated:**
- D-09's reference to "stock.sector": The actual database column is `stock.industry`. Use `industry` field.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | AKShare `stock_profit_sheet_by_report_em` returns multiple years when called without period filter (for multi-year fetch) | D-04 Multi-Year Data | Must call with `period=""` or omit period, then filter by REPORT_DATE. If AKShare only returns latest, need separate calls per year. LOW risk -- the function already returns all available reports, and existing code filters by period. |
| A2 | The `OPERATE_PROFIT` column exists in AKShare profit sheet data for all stocks | D-10 Financial NOPAT | If column name differs for some stocks, NOPAT calculation fails. MEDIUM risk -- verified for 600519 but not tested across all financials. |
| A3 | The `FINANCE_EXPENSE` column can be negative (representing net interest income for financial companies) | D-02, D-10 | For banks, finance expense is often negative (they earn interest, not pay it). The non-financial NOPAT formula adds abs(finance_expense). LOW risk -- verified in STACK.md for 600519. |

## Open Questions

1. **AKShare multi-year data structure**
   - What we know: `stock_profit_sheet_by_report_em` returns a DataFrame with all reporting periods when called without period filter.
   - What's unclear: Whether the response includes all years in a single call or only recent ones.
   - Recommendation: Test with `period=""` parameter. If AKShare returns all available reports, filter by fiscal year in-memory per D-04. If it only returns the latest, make N calls (one per year) and aggregate.

2. **`OPERATE_PROFIT` vs `OPERATING_PROFIT` column name**
   - What we know: STACK.md research references `OPERATE_PROFIT` from live 600519 data.
   - What's unclear: Whether the column name is consistent across all A-share stocks.
   - Recommendation: Use the exact column name from STACK.md (`OPERATE_PROFIT`). Add a fallback check in the extraction layer.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scipy | Moat trend detection (D-06) | -- (NOT installed) | -- | No fallback -- must install |
| numpy | Array operations | Available | 2.4.2 | -- |
| AKShare | Financial data source | Available | 1.18.46 | -- |
| Redis | Multi-year data caching (D-05) | Available | 7.2.1 | Graceful degradation (no cache) |
| PostgreSQL | ROIC results persistence | Available | via asyncpg 0.31.0 | -- |
| FastAPI | API endpoint | Available | 0.133+ | -- |

**Missing dependencies with no fallback:**
- scipy: Must install via `uv add "scipy>=1.15.0"` before implementation begins. This is a blocking dependency for moat trend detection (D-06).

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | None (uses pytest auto-discovery) |
| Quick run command | `uv run pytest tests/unit/test_roic_service.py -x -q` |
| Full suite command | `uv run pytest tests/ --cov=stockvaluefinder --cov-report=term-missing` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROIC-01 | Calculate ROIC from NOPAT / Invested Capital | unit | `uv run pytest tests/unit/test_roic_service.py::test_calculate_roic -x` | Wave 0 |
| ROIC-01 | NOPAT calculation (non-financial) | unit | `uv run pytest tests/unit/test_roic_service.py::test_calculate_nopat_non_financial -x` | Wave 0 |
| ROIC-02 | True WACC with debt weighting | unit | `uv run pytest tests/unit/test_roic_service.py::test_calculate_true_wacc -x` | Wave 0 |
| ROIC-03 | ROIC-WACC spread classification | unit | `uv run pytest tests/unit/test_roic_service.py::test_spread_classification -x` | Wave 0 |
| ROIC-04 | Financial sector detection and NOPAT | unit | `uv run pytest tests/unit/test_roic_service.py::test_financial_sector_nopat -x` | Wave 0 |
| ROIC-05 | Negative invested capital handling | unit | `uv run pytest tests/unit/test_roic_service.py::test_negative_invested_capital -x` | Wave 0 |
| ROIC-05 | NaN debt normalization | unit | `uv run pytest tests/unit/test_roic_service.py::test_nan_debt_normalization -x` | Wave 0 |
| ROIC-06 | 3-year moat trend classification | unit | `uv run pytest tests/unit/test_roic_service.py::test_analyze_roic_trend -x` | Wave 0 |
| ROIC-06 | Insufficient trend data handling | unit | `uv run pytest tests/unit/test_roic_service.py::test_trend_insufficient_data -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_roic_service.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** `uv run pytest tests/ --cov=stockvaluefinder --cov-report=term-missing`

### Wave 0 Gaps
- [ ] `tests/unit/test_roic_service.py` -- covers all ROIC pure function unit tests
- [ ] `tests/unit/test_api/test_roic_routes.py` -- covers API endpoint integration tests
- [ ] Framework install: `uv add "scipy>=1.15.0"` -- scipy must be installed before tests can run

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | API is currently unauthenticated (internal tool) |
| V3 Session Management | no | No session management needed |
| V4 Access Control | no | No authorization needed |
| V5 Input Validation | yes | Pydantic Field with ticker pattern `r"^\d{6}\.(SH|SZ|HK)$"`, year range 2000-2099 |
| V6 Cryptography | no | No cryptographic operations in this phase |

### Known Threat Patterns for ROIC-WACC Analysis

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed ticker injection | Tampering | Pydantic regex validation on ticker field |
| NaN propagation to financial outputs | Denial of Service | `_to_float()` normalization at data extraction boundary |
| Division by zero in ROIC/WACC | Denial of Service | `_safe_ratio()` pattern with None return and audit flag |
| Infinite WACC from zero equity | Denial of Service | Guard on equity_weight > 0 before WACC computation |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `valuation_service.py` (WACC = Ke only, must extend), `risk_service.py` (_safe_ratio, _to_float patterns), `akshare_client.py` (data fetching, multi-year extension point), `config.py` (frozen dataclass pattern), `data_service.py` (_cache_get_or_set pattern)
- AKShare live verification: `stock_individual_info_em` returns "银行II", "证券II", "保险II" for financial stocks; "白酒II" for Maotai
- AKShare v1.18.46 installed and verified
- scipy `linregress` behavior verified: NaN propagation confirmed, 2-point regression produces pvalue=0.0
- numpy 2.4.2 available in project venv

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` -- AKShare field mapping (TOTAL_PROFIT, FINANCE_EXPENSE, INCOME_TAX, OPERATE_PROFIT, TOTAL_PARENT_EQUITY, SHORT_LOAN, LONG_LOAN, BOND_PAYABLE, TREASURY_SHARES)
- `.planning/research/PITFALLS.md` -- WACC Ke-only pitfall, financial sector NOPAT, negative invested capital handling
- `.planning/research/SUMMARY.md` -- Phase ordering rationale, dependency analysis

### Tertiary (LOW confidence)
- None -- all critical claims verified against codebase or live AKShare data

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- scipy verified as NOT installed, numpy verified at 2.4.2, AKShare verified at 1.18.46
- Architecture: HIGH -- follows established patterns (pure functions, frozen config, BaseRepository, ApiResponse[T])
- Pitfalls: HIGH -- verified against live AKShare data and tested scipy edge cases

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (stable -- no fast-moving dependencies)
