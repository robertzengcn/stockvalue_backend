# Provenance: 000063.SZ (ZTE Corporation) FY2023

## Status
- **Verification**: COMPUTED (pending human verification from annual report)

## Data Source
- **Source**: AKShare frozen from exchange filing -- to be cross-referenced with CNINFO annual report (search "中兴通讯 000063")
- **Annual Report**: ZTE 2023 annual report available from CNINFO (http://www.cninfo.com.cn) or ZTE IR page (https://ir.zte.com.cn -> Financial Reports)
- **Key pages to verify**: 合并资产负债表 (consolidated balance sheet), 合并利润表 (consolidated income statement), 合并现金流量表 (consolidated cash flow statement)
- **AKShare Endpoints**:
  - stock_profit_sheet_by_report_em (income statement)
  - stock_balance_sheet_by_report_em (balance sheet)
  - stock_cash_flow_sheet_by_report_em (cash flow statement)
- **Frozen Date**: 2026-05-21T01:26:46.845311+00:00
- **Period**: FY2023 (20231231) + FY2022 (20221231) for year-over-year indices
- **is_financial**: False

## Technology-Sector Specific Notes
- **NOPAT branch**: is_financial=False, uses (TOTAL_PROFIT + FINANCE_EXPENSE) * (1 - tax_rate)
- **FINANCE_EXPENSE = -1,101,192,000** (negative): ZTE has net finance income (利息收入 > 利息支出), not expense. The NOPAT formula adds back finance expense, so a negative FINANCE_EXPENSE actually reduces NOPAT slightly. Verifier should confirm this sign convention matches the annual report.
- **R&D capitalization**: ZTE capitalizes a portion of R&D as 开发支出 on the balance sheet. AKShare reports OPERATE_COST which includes expensed R&D. Verifier should check whether TOTAL_OPERATE_INCOME (124.25B) matches annual report revenue including any R&D capitalization effects.
- **Revenue recognition**: ZTE has long-cycle contracts (5G base stations, telecom infrastructure). Revenue may use percentage-of-completion method. Verifier should confirm TOTAL_OPERATE_INCOME matches the annual report's recognized revenue line.
- **Goodwill = nan**: AKShare reports NaN for GOODWILL. ZTE has made acquisitions (e.g., Nubia stake) but the consolidated goodwill may be reported under a different field or is immaterial. Verifier should check the balance sheet for 商誉.
- **Invested Capital = 118.14B**: Parent equity (68.0B) + short loans (7.56B) + long loans (42.58B) = 118.14B. Bond payable is NaN, treated as 0.

## Discrepancies (to be filled during human verification)
- No discrepancies identified yet -- all values computed deterministically from frozen AKShare data
- Human verifier should check: Does TOTAL_OPERATE_INCOME (124,250,878,000) match "营业总收入" in the annual report?
- Human verifier should check: Does NETPROFIT (9,240,849,000) match "净利润" in the annual report?
- Human verifier should check: Is GOODWILL truly 0 or NaN in the annual report balance sheet?
- Human verifier should check: Is FINANCE_EXPENSE truly negative (-1,101,192,000) indicating net finance income?

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
| Revenue | TOTAL_OPERATE_INCOME | 124250878000.0 |
| Net Income | NETPROFIT | 9240849000.0 |
| Cost of Goods | OPERATE_COST | 72702602000.0 |
| SGA Expense | TOTAL_OPERATE_COST | 113977604000.0 |
| Finance Expense | FINANCE_EXPENSE | -1101192000.0 |
| Income Tax | INCOME_TAX | 962291000.0 |
| Operating Profit | OPERATE_PROFIT | 10258379000.0 |
| Total Profit | TOTAL_PROFIT | 10203140000.0 |

### Balance Sheet (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Total Assets | TOTAL_ASSETS | 200958318000.0 |
| Total Equity | TOTAL_EQUITY | 68331445000.0 |
| Total Liabilities | TOTAL_LIABILITIES | 132626873000.0 |
| Current Assets | TOTAL_CURRENT_ASSETS | 158504553000.0 |
| Accounts Receivable | ACCOUNTS_RECE | 20821526000.0 |
| PPE | FIXED_ASSET | 13372364000.0 |
| Goodwill | GOODWILL | nan |
| Cash | MONETARYFUNDS | 78543219000.0 |
| Parent Equity | TOTAL_PARENT_EQUITY | 68008307000.0 |
| Short Loan | SHORT_LOAN | 7560358000.0 |
| Long Loan | LONG_LOAN | 42576057000.0 |
| Bond Payable | BOND_PAYABLE | nan |
| Treasury Shares | TREASURY_SHARES | nan |

### Cash Flow Statement (FY2023)
| Field | AKShare Column | Value |
|-------|---------------|-------|
| Operating Cash Flow | NETCASH_OPERATE | 17405699000.0 |

### Previous Year (FY2022) -- for M-Score indices
| Field | Value |
|-------|-------|
| Revenue | 122954418000.0 |
| Net Income | 7791610000.0 |
| Total Assets | 180953574000.0 |
| Total Current Assets | 137873843000.0 |
| PPE | 12913313000.0 |
| SGA Expense | 114449900000.0 |
| Total Liabilities | 121410351000.0 |
| Accounts Receivable | 17751390000.0 |
| Operating Cash Flow | 7577700000.0 |

## Computed Golden Values
| Metric | Value | Computed By |
|--------|-------|-------------|

| DSRI | 1.1607 | calculate_mscore_indices |
| GMI | 0.8964 | calculate_mscore_indices |
| AQI | 0.8978 | calculate_mscore_indices |
| SGI | 1.0105 | calculate_mscore_indices |
| DEPI | 1.0 | calculate_mscore_indices |
| SGAI | 0.9855 | calculate_mscore_indices |
| LVGI | 0.9836 | calculate_mscore_indices |
| TATA | -0.0406 | calculate_mscore_indices |
| M-Score | -2.6009 | calculate_beneish_m_score |
| F-Score | 6 | calculate_piotroski_f_score |
| 存贷双高 | False | detect_存贷双高 |
| Goodwill Ratio | 0.0 | calculate_goodwill_ratio |
| Profit-Cash Divergence | False | detect_profit_cash_divergence |
| NOPAT | 8243513964.70616 | calculate_nopat (is_financial=False (TOTAL_PROFIT + FINANCE_EXPENSE branch)) |
| Invested Capital | 118144722000.0 | calculate_invested_capital |
| ROIC | 0.069775 | calculate_roic |

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
