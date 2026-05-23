# Provenance: 600519.SH FY2023

## Data Source
- **Source**: AKShare frozen from exchange filing -- to be cross-referenced with CNINFO annual report
- **AKShare Endpoints**:
  - stock_profit_sheet_by_report_em (income statement)
  - stock_balance_sheet_by_report_em (balance sheet)
  - stock_cash_flow_sheet_by_report_em (cash flow statement)
- **Frozen Date**: 2026-05-21T01:06:36.807096+00:00
- **Period**: FY2023 (20231231) + FY2022 (20221231) for year-over-year indices
- **is_financial**: False

## Computation Method
All golden values computed from frozen AKShare data using production calculate_* functions:
- M-Score 8 sub-indices: `calculate_mscore_indices(current_2023, previous_2022, "AKShare")`
- M-Score composite: `calculate_beneish_m_score(current_financials, previous_financials)`
- F-Score: `calculate_piotroski_f_score(report_2023, previous_report_2022)`
- 存贷双高: `detect_存贷双高(report_2023, report_2022)`
- Goodwill ratio: `calculate_goodwill_ratio(goodwill, equity)`
- Profit-cash divergence: `detect_profit_cash_divergence(profit_2023, profit_2022, ocf_2023, ocf_2022)`
- NOPAT: `calculate_nopat(profit_data, is_financial=False (TOTAL_PROFIT + FINANCE_EXPENSE branch))`
- Invested Capital: `calculate_invested_capital(balance_sheet_data)`
- ROIC: `calculate_roic(nopat, invested_capital, negative_ic)`

## Raw Financial Data (from frozen AKShare)

### Income Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Revenue | TOTAL_OPERATE_INCOME | 150560330316.45 |
| Net Income | NETPROFIT | 77521476277.8 |
| Cost of Goods | OPERATE_COST | 11867273851.78 |
| SGA Expense | TOTAL_OPERATE_COST | 46960889468.54 |
| Finance Expense | FINANCE_EXPENSE | -1789503701.48 |
| Income Tax | INCOME_TAX | 26141077412.01 |
| Operating Profit | OPERATE_PROFIT | 103708655208.38 |
| Total Profit | TOTAL_PROFIT | 103662553689.81 |

### Balance Sheet (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Total Assets | TOTAL_ASSETS | 272699660092.25 |
| Total Equity | TOTAL_EQUITY | 223656469294.82 |
| Total Liabilities | TOTAL_LIABILITIES | 49043190797.43 |
| Current Assets | TOTAL_CURRENT_ASSETS | 225172517821.28 |
| Accounts Receivable | ACCOUNTS_RECE | 60373410.41 |
| PPE | FIXED_ASSET | 19909280655.97 |
| Goodwill | GOODWILL | nan |
| Cash | MONETARYFUNDS | 69070136376.12 |
| Parent Equity | TOTAL_PARENT_EQUITY | 215668571607.43 |
| Short Loan | SHORT_LOAN | nan |
| Long Loan | LONG_LOAN | nan |
| Bond Payable | BOND_PAYABLE | nan |
| Treasury Shares | TREASURY_SHARES | nan |

### Cash Flow Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Operating Cash Flow | NETCASH_OPERATE | 66593247721.09 |

### Previous Year (FY2022) -- for M-Score indices
| Field | Value |
|-------|-------|
| Revenue | 127553959355.97 |
| Net Income | 65376039957.88 |
| Total Assets | 254500826096.02 |
| Total Current Assets | 216611435672.92 |
| PPE | 19742622547.86 |
| SGA Expense | 39748309616.85 |
| Total Liabilities | 49562744832.16 |
| Accounts Receivable | 20937144.0 |
| Operating Cash Flow | 36698595830.03 |

## Computed Golden Values
| Metric | Value | Computed By |
|--------|-------|-------------|

| DSRI | 2.4429 | calculate_mscore_indices |
| GMI | 0.9997 | calculate_mscore_indices |
| AQI | 1.092 | calculate_mscore_indices |
| SGI | 1.1804 | calculate_mscore_indices |
| DEPI | 1.0 | calculate_mscore_indices |
| SGAI | 1.0009 | calculate_mscore_indices |
| LVGI | 0.9235 | calculate_mscore_indices |
| TATA | 0.0401 | calculate_mscore_indices |
| M-Score | -0.7421 | calculate_beneish_m_score |
| F-Score | 6 | calculate_piotroski_f_score |
| 存贷双高 | False | detect_存贷双高 |
| Goodwill Ratio | 0.0 | calculate_goodwill_ratio |
| Profit-Cash Divergence | False | detect_profit_cash_divergence |
| NOPAT | 76183240205.02849 | calculate_nopat (is_financial=False (TOTAL_PROFIT + FINANCE_EXPENSE branch)) |
| Invested Capital | 215668571607.43 | calculate_invested_capital |
| ROIC | 0.353242 | calculate_roic |

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
- **is_financial**: False
- **Note**: Values should be cross-referenced with CNINFO annual report PDF for L3 verification
