# Provenance: 601398.SH FY2023

## Data Source
- **Source**: AKShare frozen from exchange filing -- to be cross-referenced with CNINFO annual report
- **AKShare Endpoints**:
  - stock_profit_sheet_by_report_em (income statement)
  - stock_balance_sheet_by_report_em (balance sheet)
  - stock_cash_flow_sheet_by_report_em (cash flow statement)
- **Frozen Date**: 2026-05-21T01:19:28.493024+00:00
- **Period**: FY2023 (20231231) + FY2022 (20221231) for year-over-year indices
- **is_financial**: True

## Computation Method
All golden values computed from frozen AKShare data using production calculate_* functions:
- M-Score 8 sub-indices: `calculate_mscore_indices(current_2023, previous_2022, "AKShare")`
- M-Score composite: `calculate_beneish_m_score(current_financials, previous_financials)`
- F-Score: `calculate_piotroski_f_score(report_2023, previous_report_2022)`
- 存贷双高: `detect_存贷双高(report_2023, report_2022)`
- Goodwill ratio: `calculate_goodwill_ratio(goodwill, equity)`
- Profit-cash divergence: `detect_profit_cash_divergence(profit_2023, profit_2022, ocf_2023, ocf_2022)`
- NOPAT: `calculate_nopat(profit_data, is_financial=True (OPERATE_PROFIT branch))`
- Invested Capital: `calculate_invested_capital(balance_sheet_data)`
- ROIC: `calculate_roic(nopat, invested_capital, negative_ic)`

## Raw Financial Data (from frozen AKShare)

### Income Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Revenue | TOTAL_OPERATE_INCOME | None |
| Net Income | NETPROFIT | 365116000000 |
| Cost of Goods | OPERATE_COST | None |
| SGA Expense | TOTAL_OPERATE_COST | None |
| Finance Expense | FINANCE_EXPENSE | None |
| Income Tax | INCOME_TAX | 56850000000 |
| Operating Profit | OPERATE_PROFIT | 420760000000 |
| Total Profit | TOTAL_PROFIT | 421966000000 |

### Balance Sheet (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Total Assets | TOTAL_ASSETS | 44697079000000 |
| Total Equity | TOTAL_EQUITY | 3776588000000 |
| Total Liabilities | TOTAL_LIABILITIES | 40920491000000 |
| Current Assets | TOTAL_CURRENT_ASSETS | None |
| Accounts Receivable | ACCOUNTS_RECE | nan |
| PPE | FIXED_ASSET | 272832000000 |
| Goodwill | GOODWILL | nan |
| Cash | MONETARYFUNDS | None |
| Parent Equity | TOTAL_PARENT_EQUITY | 3756887000000 |
| Short Loan | SHORT_LOAN | None |
| Long Loan | LONG_LOAN | None |
| Bond Payable | BOND_PAYABLE | 1369777000000.0 |
| Treasury Shares | TREASURY_SHARES | nan |

### Cash Flow Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Operating Cash Flow | NETCASH_OPERATE | 1417002000000 |

### Previous Year (FY2022) -- for M-Score indices
| Field | Value |
|-------|-------|
| Revenue | None |
| Net Income | 362110000000 |
| Total Assets | 39610146000000 |
| Total Current Assets | None |
| PPE | 274839000000 |
| SGA Expense | None |
| Total Liabilities | 36094727000000 |
| Accounts Receivable | nan |
| Operating Cash Flow | 1404657000000 |

## Computed Golden Values
| Metric | Value | Computed By |
|--------|-------|-------------|

| DSRI | 1.0 | calculate_mscore_indices |
| GMI | 0.9668 | calculate_mscore_indices |
| AQI | 0.9992 | calculate_mscore_indices |
| SGI | 0.9627 | calculate_mscore_indices |
| DEPI | 1.0 | calculate_mscore_indices |
| SGAI | 1.0 | calculate_mscore_indices |
| LVGI | 1.0047 | calculate_mscore_indices |
| TATA | -0.0235 | calculate_mscore_indices |
| M-Score | -2.6426 | calculate_beneish_m_score |
| F-Score | 4 | calculate_piotroski_f_score |
| 存贷双高 | False | detect_存贷双高 |
| Goodwill Ratio | 0.0 | calculate_goodwill_ratio |
| Profit-Cash Divergence | False | detect_profit_cash_divergence |
| NOPAT | 364072480152.4293 | calculate_nopat (is_financial=True (OPERATE_PROFIT branch)) |
| Invested Capital | 5126664000000.0 | calculate_invested_capital |
| ROIC | 0.071015 | calculate_roic |

## Skipped Metrics
| Metric | Reason |
|--------|--------|
| WACC | Requires market data (beta, risk-free rate, ERP) |
| Present Value | Requires multi-year FCF projections |
| Terminal Value | Requires multi-year growth assumptions |
| Margin of Safety | Requires current market price |
| Net Dividend Yield | Requires dividend per share and stock price |
| Yield Gap | Requires net_dividend_yield and risk-free rates |
| Buyback Yield | Requires share buyback data |
| Capital Allocation Score | Composite of above skipped metrics |
| Resonance Score | Requires LLM semantic matching |
| DCF Adjustment | Requires policy resonance engine |
| Alpha Score | Composite of LLM-dependent metrics |
| ROIC-WACC Spread | Depends on WACC (skipped) |

## Verifier
- **Date**: 2026-05-23
- **Method**: Computed from frozen AKShare data using calculate_* functions
- **Confidence**: Deterministic -- values are exact outputs of production code
- **is_financial**: True
- **Note**: Values should be cross-referenced with CNINFO annual report PDF for L3 verification
