# Additional Financial Analysis Suggestions

Based on the current implementation (M-Score fraud detection, F-Score financial strength, DCF valuation, yield gap analysis), the following additional financial analyses would help users pick better stocks.

---

## 1. Graham Number & Margin of Safety

Benjamin Graham's classic metric: `√(22.5 × EPS × Book Value Per Share)`. Compare it to market price to get a margin of safety. This is simple to implement and directly complements your DCF valuation by providing a quick sanity check.

## 2. Altman Z-Score (Bankruptcy Risk)

A well-established 5-factor model predicting bankruptcy probability within 2 years. It uses ratios already available in the system (working capital, retained earnings, EBIT, market cap, sales). Thresholds:

- Z > 2.99: Safe zone
- 1.81 < Z < 2.99: Grey zone
- Z < 1.81: Distress zone

This pairs naturally with M-Score — M-Score detects earnings manipulation, Z-Score detects insolvency risk.

## 3. DuPont Analysis (ROE Decomposition)

Break ROE into: `Net Profit Margin × Asset Turnover × Equity Multiplier`. This tells users *why* a company has high or low ROE — is it operational efficiency, asset utilization, or just leverage? Far more actionable than raw ROE alone.

## 4. Free Cash Flow Quality Score

Compare operating cash flow to net income over multiple years. A persistently low cash-to-earnings ratio (e.g., CFO/Net Income < 0.7) signals aggressive accounting, even when M-Score looks clean. Both numbers are already fetched by the system.

## 5. PEG Ratio (Growth-Adjusted Valuation)

`PE Ratio / Earnings Growth Rate`. Peter Lynch popularized this — PEG < 1 suggests undervaluation relative to growth. Simple to calculate and gives a different angle than DCF for growth-oriented value plays.

## 6. Debt Serviceability Metrics

- **Interest Coverage Ratio**: EBIT / Interest Expense
- **Debt-to-EBITDA**: Total Debt / EBITDA
- **Net Debt / Free Cash Flow**: Years to pay off debt from FCF

These matter especially for A-share and H-share companies where "存贷双高" is already flagged. Quantifying debt burden complements the existing qualitative flag.

## 7. Earnings Stability & Growth Trend

Calculate earnings volatility (standard deviation of EPS over 5+ years) and compound growth rates. Stable, growing earnings are a hallmark of quality companies. Computationally trivial but highly informative when scored across the CSI 300.

## 8. Shareholder Return Analysis

- **Dividend Payout Ratio** trend (increasing = sustainable, erratic = risky)
- **Buyback Yield** (net shares repurchased / market cap)
- **Total Shareholder Return** over 3/5/10 years

This extends the existing yield gap analysis into a fuller picture of capital allocation quality.

---

## Recommended Priority

| Priority | Analysis | Rationale |
|----------|----------|-----------|
| **High** | Altman Z-Score | Pairs with M-Score, uses existing data, well-validated |
| **High** | DuPont Analysis | Turns raw ROE into actionable insight, simple math |
| **High** | Graham Number | Minimal effort, strong value investing brand recognition |
| **Medium** | FCF Quality Score | Uses existing cash flow data, catches what M-Score misses |
| **Medium** | Debt Serviceability | Critical for A/H market where leverage is common |
| **Medium** | PEG Ratio | Quick valuation sanity check alongside DCF |
| **Low** | Earnings Stability | Requires 5+ years of history, but highly informative |
| **Low** | Shareholder Return | Extends yield gap, but lower urgency |

## Implementation Notes

The high-priority items all use data already being fetched and can reuse the existing service architecture (service → repo → API route pattern). Each one can be added as a standalone module following the same pattern as the existing risk/valuation/yield services.

### Existing Pattern to Follow

```
models/<module>.py         → Pydantic request/response models
services/<module>_service.py → Business logic and calculations
repositories/<module>_repo.py → Database persistence
api/<module>_routes.py     → FastAPI endpoints
tests/unit/test_services/  → Unit tests
tests/contract/            → API contract tests
```
