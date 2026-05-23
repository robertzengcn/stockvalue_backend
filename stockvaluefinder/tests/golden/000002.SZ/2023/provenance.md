# Provenance: 000002.SZ (China Vanke) FY2023

## Status
- **Verification**: COMPUTED (pending human verification from annual report)

## Data Source
- **Source**: AKShare frozen from exchange filing -- to be cross-referenced with CNINFO annual report (search "万科A 000002")
- **Annual Report**: Vanke 2023 annual report available from CNINFO (http://www.cninfo.com.cn, search "万科A")
- **Key pages to verify**: 合并资产负债表 (consolidated balance sheet), 合并利润表 (consolidated income statement), 合并现金流量表 (consolidated cash flow statement)
- **AKShare Endpoints**:
  - stock_profit_sheet_by_report_em (income statement)
  - stock_balance_sheet_by_report_em (balance sheet)
  - stock_cash_flow_sheet_by_report_em (cash flow statement)
- **Frozen Date**: 2026-05-21T01:22:14.153072+00:00
- **Period**: FY2023 (20231231) + FY2022 (20221231) for year-over-year indices
- **is_financial**: False

## Real-Estate Sector Specific Notes
- **NOPAT branch**: is_financial=False, uses (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)
- **FINANCE_EXPENSE = 3,714,825,488.38** (positive and large): Vanke carries substantial interest-bearing debt (long loans 197.8B + bonds 59.9B = 257.7B). The positive FINANCE_EXPENSE is added back in the NOPAT formula, increasing NOPAT. This is the known stress test for the non-financial NOPAT branch described in the plan.
- **Tax rate = 31.37%**: High effective tax rate, consistent with real estate sector (land value tax + corporate income tax).
- **LVGI = 0.9519**: Leverage slightly decreased YoY (debt/assets ratio fell). Despite this, total liabilities are 1.1 trillion (73.2% debt ratio). Verifier should cross-check against the balance sheet's interest-bearing debt composition.
- **GMI = 1.2835**: Gross margins deteriorated significantly YoY (gross margin index > 1 means margins are shrinking). This reflects the 2023 Chinese real estate downturn where developers cut prices to move inventory.
- **SGI = 0.9244**: Revenue declined 7.6% YoY -- expected given the property market slowdown and Vanke's deliberate sales pacing.
- **F-Score = 3**: Low, reflecting deteriorating profitability (negative profit growth, declining margins), partially offset by slight deleveraging.
- **Presale revenue (合同负债)**: Vanke receives cash from presales booked as 合同负债 (contract liabilities) until project completion. Verifier should confirm TOTAL_OPERATE_INCOME (465.7B) matches recognized revenue in the annual report, not presale cash receipts.
- **Goodwill = 5,408,770,448.41**: Non-trivial goodwill from property management acquisitions (e.g., Onewo万科云). Goodwill ratio = 1.34% of equity.
- **存贷双高 = False**: Despite having 99.8B cash and 1.1T total liabilities, the detection algorithm did not flag 存贷双高. Verifier should check whether the algorithm's thresholds are appropriate for real estate developers who structurally carry both high cash (from presales) and high debt.
- **Invested Capital = 508.2B**: Parent equity (250.8B) + short loans (1.06B) + long loans (197.8B) + bonds (59.9B) - treasury shares (1.3B) = 508.2B. This is dominated by long-term debt, reflecting the capital-intensive nature of property development.

## Discrepancies (to be filled during human verification)
- No discrepancies identified yet -- all values computed deterministically from frozen AKShare data
- Human verifier should check: Does TOTAL_OPERATE_INCOME (465,739,076,702.23) match "营业总收入" in the annual report?
- Human verifier should check: Does NETPROFIT (20,455,558,414.74) match "净利润" in the annual report?
- Human verifier should check: Does FINANCE_EXPENSE (3,714,825,488.38) match "财务费用" in the annual report?
- Human verifier should check: Is TOTAL_LIABILITIES (1,101,916,641,170.57) consistent with the balance sheet?
- Human verifier should check: Is GOODWILL (5,408,770,448.41) consistent with the balance sheet's 商誉 line?

## Data Source (AKShare details)
- **AKShare Endpoints**:
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
| Revenue | TOTAL_OPERATE_INCOME | 465739076702.23 |
| Net Income | NETPROFIT | 20455558414.74 |
| Cost of Goods | OPERATE_COST | 394783859517.79 |
| SGA Expense | TOTAL_OPERATE_COST | 435658346640.35 |
| Finance Expense | FINANCE_EXPENSE | 3714825488.38 |
| Income Tax | INCOME_TAX | 9349869711.7 |
| Operating Profit | OPERATE_PROFIT | 29251702064.41 |
| Total Profit | TOTAL_PROFIT | 29805428126.44 |

### Balance Sheet (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Total Assets | TOTAL_ASSETS | 1504850172117.83 |
| Total Equity | TOTAL_EQUITY | 402933530947.26 |
| Total Liabilities | TOTAL_LIABILITIES | 1101916641170.57 |
| Current Assets | TOTAL_CURRENT_ASSETS | 1150260062360.68 |
| Accounts Receivable | ACCOUNTS_RECE | 7293628386.69 |
| PPE | FIXED_ASSET | 19233034944.88 |
| Goodwill | GOODWILL | 5408770448.41 |
| Cash | MONETARYFUNDS | 99813755447.81 |
| Parent Equity | TOTAL_PARENT_EQUITY | 250784613404.38 |
| Short Loan | SHORT_LOAN | 1063561883.1 |
| Long Loan | LONG_LOAN | 197764142683.89 |
| Bond Payable | BOND_PAYABLE | 59871015948.97 |
| Treasury Shares | TREASURY_SHARES | 1291800290.12 |

### Cash Flow Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Operating Cash Flow | NETCASH_OPERATE | 3912323920.11 |

### Previous Year (FY2022) -- for M-Score indices
| Field | Value |
|-------|-------|
| Revenue | 503838367358.76 |
| Net Income | 37612558798.7 |
| Total Assets | 1757804935896.04 |
| Total Current Assets | 1415356379958.52 |
| PPE | 16420265134.96 |
| SGA Expense | 455011051482.74 |
| Total Liabilities | 1352168105932.49 |
| Accounts Receivable | 7504692133.25 |
| Operating Cash Flow | 2750449478.44 |

## Computed Golden Values
| Metric | Value | Computed By |
|--------|-------|-------------|

| DSRI | 1.0514 | calculate_mscore_indices |
| GMI | 1.2835 | calculate_mscore_indices |
| AQI | 1.2168 | calculate_mscore_indices |
| SGI | 0.9244 | calculate_mscore_indices |
| DEPI | 1.0 | calculate_mscore_indices |
| SGAI | 1.0358 | calculate_mscore_indices |
| LVGI | 0.9519 | calculate_mscore_indices |
| TATA | 0.011 | calculate_mscore_indices |
| M-Score | -2.2018 | calculate_beneish_m_score |
| F-Score | 3 | calculate_piotroski_f_score |
| 存贷双高 | False | detect_存贷双高 |
| Goodwill Ratio | 0.0134 | calculate_goodwill_ratio |
| Profit-Cash Divergence | False | detect_profit_cash_divergence |
| NOPAT | 23005054749.96336 | calculate_nopat (is_financial=False (TOTAL_PROFIT + FINANCE_EXPENSE branch)) |
| Invested Capital | 508191533630.22 | calculate_invested_capital |
| ROIC | 0.045268 | calculate_roic |

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
