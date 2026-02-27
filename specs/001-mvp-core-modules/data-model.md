# Data Model: AI 增强型价值投资决策平台 MVP

**Feature**: 001-mvp-core-modules  
**Date**: 2026-02-26  
**Status**: Draft

This document defines all data entities, their relationships, and validation rules.

## Entity Relationship Diagram

```text
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│    Stock    │───────│ FinancialReport  │───────│ RiskScore   │
│             │ 1   N │                  │ 1   1 │             │
│ - ticker    │       │ - report_id      │       │ - score_id  │
│ - name      │       │ - period         │       │ - m_score   │
│ - market    │       │ - revenue        │       │ - ...       │
│ - industry  │       │ - net_income     │       └─────────────┘
└─────────────┘       │ - ...            │
         │             └──────────────────┘
         │                      │
         │              ┌───────┴────────┐
         │              │                 │
         │         ┌────▼────┐     ┌─────▼──────┐
         └────────→│Dividend │     │Valuation  │
                  │Data     │     │Result     │
                  │         │     │           │
                  │- div_id │     │- val_id   │
                  │- amount │     │- intrinsic│
                  └─────────┘     └───────────┘
                         
┌─────────────┐
│  RateData   │
│             │
│ - rate_id   │
│ - bond_rate │
│ - deposit   │
│ - update_at │
└─────────────┘
```

## Core Entities

### Stock (股票基本信息)

Represents a tradeable stock on A-share or Hong Kong markets.

**Attributes**:
- `ticker` (str, PK): Stock code (e.g., "600519.SH", "0700.HK")
- `name` (str): Company name (e.g., "贵州茅台", "腾讯控股")
- `market` (Enum): Market enum (A_SHARE, HK_SHARE)
- `industry` (str): Industry sector (e.g., "食品饮料", "科技")
- `list_date` (date): Listing date
- `created_at` (datetime): Record creation timestamp
- `updated_at` (datetime): Last update timestamp

**Validation Rules**:
- `ticker` must match pattern: `\d{6}\.(SH|SZ|HK)`
- `name` must not be empty
- `market` must be one of: A_SHARE, HK_SHARE
- `industry` must be from predefined industry list

**Indexes**:
- Primary key: `ticker`
- Index on: `market`, `industry`

---

### FinancialReport (财务报告)

Stores audited financial statement data for a stock.

**Attributes**:
- `report_id` (UUID, PK): Unique identifier
- `ticker` (str, FK): Reference to Stock.ticker
- `period` (str): Reporting period (e.g., "2024-03-31" for Q1 2024)
- `report_type` (Enum): Report type (ANNUAL, QUARTERLY)
- `revenue` (Decimal): Total revenue (元)
- `net_income` (Decimal): Net profit (元)
- `operating_cash_flow` (Decimal): Operating cash flow (元)
- `gross_margin` (float): Gross margin percentage (0-100)
- `assets_total` (Decimal): Total assets (元)
- `liabilities_total` (Decimal): Total liabilities (元)
- `equity_total` (Decimal): Total equity (元)
- `accounts_receivable` (Decimal): Accounts receivable (元)
- `inventory` (Decimal): Inventory (元)
- `fixed_assets` (Decimal): Fixed assets (元)
- `goodwill` (Decimal): Goodwill (元)
- `cash_and_equivalents` (Decimal): Cash and cash equivalents (元)
- `interest_bearing_debt` (Decimal): Interest-bearing debt (元)
- `report_source` (str): Source of data (Tushare/AKShare/PDF)
- `fiscal_year` (int): Fiscal year
- `fiscal_quarter` (int): Fiscal quarter (1-4, or None for annual)
- `created_at` (datetime): Record creation timestamp
- `updated_at` (datetime): Last update timestamp

**Validation Rules**:
- All monetary fields must be >= 0
- `gross_margin` must be between 0 and 100
- `period` must match pattern: `\d{4}-\d{2}-\d{2}`
- `report_type` must be ANNUAL or QUARTERLY
- `fiscal_quarter` must be 1-4 if report_type is QUARTERLY, None if ANNUAL

**Indexes**:
- Primary key: `report_id`
- Unique constraint: `(ticker, period)`
- Index on: `ticker`, `fiscal_year`

---

### RiskScore (风险评分)

Stores risk assessment results for a stock based on financial analysis.

**Attributes**:
- `score_id` (UUID, PK): Unique identifier
- `ticker` (str, FK): Reference to Stock.ticker
- `report_id` (UUID, FK): Reference to FinancialReport.report_id
- `calculated_at` (datetime): Calculation timestamp
- `risk_level` (Enum): Overall risk level (LOW, MEDIUM, HIGH, CRITICAL)

**Beneish M-Score Components**:
- `m_score` (float): Beneish M-Score value
- `dsri` (float): Days' Sales in Receivables Index
- `gmi` (float): Gross Margin Index
- `aqi` (float): Asset Quality Index
- `sgi` (float): Sales Growth Index
- `depi` (float): Depreciation Index
- `sgai` (float): SG&A Expense Index
- `lvgi` (float): Leverage Index
- `tata` (float): Total Accruals to Total Assets

**Risk Flags**:
- `存贷双高` (bool): High cash + high debt flag
- `cash_amount` (Decimal): Cash and equivalents for 存贷双高 calculation
- `debt_amount` (Decimal): Interest-bearing debt for 存贷双高 calculation
- `cash_growth_rate` (float): YoY cash growth rate
- `debt_growth_rate` (float): YoY debt growth rate

**Goodwill Risk**:
- `goodwill_ratio` (float): Goodwill / Equity ratio (0-100)
- `goodwill_excessive` (bool): True if goodwill_ratio > 30%

**Cash Flow Divergence**:
- `profit_cash_divergence` (bool): True if net_income grew but OCF declined
- `profit_growth` (float): YoY profit growth rate
- `ocf_growth` (float): YoY operating cash flow growth rate

**Red Flags** (JSON array):
- `red_flags` (list[str]): List of warning messages
- Examples: ["应收账款异常增长", "毛利率下降", "经营现金流与净利润背离"]

**Validation Rules**:
- `m_score` must be between -10 and 10
- All ratios must be between 0 and 1 or 0 and 100 as appropriate
- `risk_level` must be LOW, MEDIUM, HIGH, or CRITICAL
- Thresholds: M-Score > -1.78 → HIGH or CRITICAL

**Indexes**:
- Primary key: `score_id`
- Unique constraint: `(ticker, report_id)`
- Index on: `risk_level`, `calculated_at`

---

### DividendData (分红数据)

Stores dividend information for yield calculation.

**Attributes**:
- `div_id` (UUID, PK): Unique identifier
- `ticker` (str, FK): Reference to Stock.ticker
- `ex_dividend_date` (date): Ex-dividend date
- `dividend_per_share` (Decimal): Dividend amount per share (元/share or HKD/share)
- `dividend_frequency` (Enum): Frequency (ANNUAL, SEMI_ANNUAL, QUARTERLY, SPECIAL)
- `tax_rate` (float): Applicable tax rate (0 for A-shares, 0.20 for HK Stock Connect)
- `currency` (Enum): Currency (CNY, HKD)
- `created_at` (datetime): Record creation timestamp

**Validation Rules**:
- `dividend_per_share` must be > 0
- `tax_rate` must be 0 or 0.20
- `currency` must match market (CNY for A-shares, HKD for HK)
- `ex_dividend_date` must not be in the future

**Indexes**:
- Primary key: `div_id`
- Index on: `ticker`, `ex_dividend_date`

---

### YieldGap (股息率利差)

Stores yield gap comparison results.

**Attributes**:
- `yield_id` (UUID, PK): Unique identifier
- `ticker` (str, FK): Reference to Stock.ticker
- `current_price` (Decimal): Current stock price
- `cost_basis` (Decimal | None): User's cost basis (optional)
- `dividend_per_share` (Decimal): Annual dividend per share
- `gross_dividend_yield` (float): Gross dividend yield (pre-tax)
- `tax_rate` (float): Applied tax rate
- `net_dividend_yield` (float): After-tax dividend yield
- `risk_free_rate_bond` (float): 10-year treasury yield
- `deposit_rate` (float): 3-year large deposit rate
- `risk_free_rate` (float): Max of bond and deposit rates
- `yield_gap` (float): net_dividend_yield - risk_free_rate
- `recommendation` (Enum): Investment recommendation (ATTRACTIVE, NEUTRAL, UNATTRACTIVE)
- `calculated_at` (datetime): Calculation timestamp

**Validation Rules**:
- `current_price` must be > 0
- All yields must be between 0 and 1 (0-100%)
- `yield_gap` can be negative
- `recommendation` logic:
  - ATTRACTIVE: yield_gap > 0.02 (2%)
  - NEUTRAL: -0.01 <= yield_gap <= 0.02
  - UNATTRACTIVE: yield_gap < -0.01

**Indexes**:
- Primary key: `yield_id`
- Index on: `ticker`, `calculated_at`

---

### ValuationResult (估值结果)

Stores DCF valuation calculation results.

**Attributes**:
- `val_id` (UUID, PK): Unique identifier
- `ticker` (str, FK): Reference to Stock.ticker
- `report_id` (UUID, FK): Reference to FinancialReport.report_id
- `calculated_at` (datetime): Calculation timestamp

**DCF Parameters**:
- `current_price` (Decimal): Current market price
- `risk_free_rate` (float): Risk-free rate (10-year treasury)
- `beta` (float): Beta coefficient
- `equity_risk_premium` (float): Market equity risk premium
- `wacc` (float): Weighted average cost of capital
- `growth_rate_stage1` (float): Stage 1 growth rate (years 1-5)
- `growth_rate_stage2` (float): Stage 2 growth rate (years 6-10)
- `terminal_growth_rate` (float): Terminal growth rate
- `stage1_years` (int): Stage 1 duration (default: 5)
- `stage2_years` (int): Stage 2 duration (default: 5)

**Cash Flow Projections**:
- `fcf_base` (Decimal): Base year free cash flow
- `present_value_fcf` (Decimal): Present value of projected FCFs
- `terminal_value` (Decimal): Terminal value
- `present_value_terminal` (Decimal): Present value of terminal value

**Valuation Output**:
- `intrinsic_value` (Decimal): Calculated intrinsic value per share
- `margin_of_safety` (float): (intrinsic_value - current_price) / current_price
- `valuation_level` (Enum): (SIGNIFICANTLY_UNDervalued, UNDERVALUED, FAIR_VALUE, OVERVALUED, SIGNIFICANTLY_OVERvalued)

**Audit Trail** (JSON):
- `assumptions` (dict): All input parameters
- `calculation_steps` (list[str]): Step-by-step calculation
- `fcf_projections` (list[Decimal]): Projected FCFs

**Validation Rules**:
- `current_price` must be > 0
- All growth rates must be between -0.1 and 0.5 (-10% to 50%)
- `wacc` must be between 0.05 and 0.25 (5% to 25%)
- `terminal_growth_rate` must be between 0 and 0.05 (0% to 5%)
- Valuation thresholds:
  - SIGNIFICANTLY_UNDERVALUED: MoS > 40%
  - UNDERVALUED: 15% < MoS <= 40%
  - FAIR_VALUE: -15% <= MoS <= 15%
  - OVERVALUED: -40% <= MoS < -15%
  - SIGNIFICANTLY_OVERVALUED: MoS < -40%

**Indexes**:
- Primary key: `val_id`
- Index on: `ticker`, `calculated_at`

---

### RateData (利率数据)

Stores market interest rate data for yield comparison.

**Attributes**:
- `rate_id` (UUID, PK): Unique identifier
- `rate_date` (date): Date of rate
- `ten_year_treasury` (float): 10-year government bond yield
- `three_year_deposit` (float): 3-year large deposit rate
- `one_year_deposit` (float): 1-year deposit rate
- `benchmark_rate` (float): Central bank benchmark rate
- `rate_source` (str): Source of data (PBOC, HKMA, etc.)
- `created_at` (datetime): Record creation timestamp

**Validation Rules**:
- All rates must be between 0 and 0.20 (0% to 20%)
- `rate_date` must be unique
- `rate_date` cannot be in the future

**Indexes**:
- Primary key: `rate_id`
- Unique constraint: `rate_date`
- Index on: `rate_date` DESC (for latest rate lookup)

---

## Enums

### Market
```python
class Market(str, Enum):
    A_SHARE = "A_SHARE"    # A-shares (Shanghai/Shenzhen)
    HK_SHARE = "HK_SHARE"  # Hong Kong stocks
```

### ReportType
```python
class ReportType(str, Enum):
    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
```

### RiskLevel
```python
class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
```

### DividendFrequency
```python
class DividendFrequency(str, Enum):
    ANNUAL = "ANNUAL"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    QUARTERLY = "QUARTERLY"
    SPECIAL = "SPECIAL"
```

### Currency
```python
class Currency(str, Enum):
    CNY = "CNY"
    HKD = "HKD"
```

### YieldRecommendation
```python
class YieldRecommendation(str, Enum):
    ATTRACTIVE = "ATTRACTIVE"
    NEUTRAL = "NEUTRAL"
    UNATTRACTIVE = "UNATTRACTIVE"
```

### ValuationLevel
```python
class ValuationLevel(str, Enum):
    SIGNIFICANTLY_UNDERVALUED = "SIGNIFICANTLY_UNDERVALUED"
    UNDERVALUED = "UNDERVALUED"
    FAIR_VALUE = "FAIR_VALUE"
    OVERVALUED = "OVERVALUED"
    SIGNIFICANTLY_OVERVALUED = "SIGNIFICANTLY_OVERVALUED"
```

---

## Relationships

### One-to-Many
- **Stock → FinancialReport**: One stock has many historical reports
- **Stock → RiskScore**: One stock has many risk scores over time
- **Stock → DividendData**: One stock has many dividend records
- **Stock → YieldGap**: One stock has many yield gap calculations
- **Stock → ValuationResult**: One stock has many valuation results

### One-to-One
- **FinancialReport → RiskScore**: Each report has one risk score
- **FinancialReport → ValuationResult**: Each report can have one DCF valuation

### Reference Data
- **RateData**: Independent entity, no foreign keys

---

## State Transitions

### RiskScore State
```text
┌─────────┐  Data Available  ┌──────────┐
│  None   │ ────────────────→│  Calculated│
└─────────┘                  └──────────┘
                                      │
                                      │ New Report
                                      ↓
                              ┌──────────┐
                              │ Expired  │
                              └──────────┘
```

### ValuationResult State
```text
┌─────────┐  Parameters Set  ┌───────────┐
│  None   │ ─────────────────→│ Calculated│
└─────────┘                  └───────────┘
                                      │
                                      │ Price Change > 5%
                                      ↓
                              ┌───────────┐
                              │ Stale     │
                              └───────────┘
```

---

## Database Schema (SQL)

See [contracts/](contracts/) for detailed SQL DDL statements.

---

## Pydantic Models

All entities will be implemented as Pydantic `BaseModel` subclasses with:

- `frozen=True` for immutability
- Strict type validation
- Custom validators for business rules
- JSON serialization support

Example:
```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class Stock(BaseModel):
    model_config = {"frozen": True}
    
    ticker: str = Field(..., pattern=r"\d{6}\.(SH|SZ|HK)")
    name: str = Field(..., min_length=1)
    market: Market
    industry: str
    list_date: date
    created_at: datetime
    updated_at: datetime
    
    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        return v.upper()
```
