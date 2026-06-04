---
status: complete
phase: 09-roic-wacc-spread
source: [09-01-SUMMARY.md, 09-02-SUMMARY.md, 09-03-SUMMARY.md]
started: 2026-05-03T11:15:00Z
updated: 2026-05-05T08:01:00Z
---

## Current Test

[testing complete]

## Tests

### 1. ROIC-WACC Spread API Returns Complete Analysis
expected: POST /api/v1/analyze/roic with a CSI 300 ticker returns success=True with data containing roic, wacc_breakdown (ke, kd, weights, wacc), spread, and spread_classification fields.
result: pass

### 2. Spread Classification (Value-Creating vs Value-Destroying)
expected: ROIC > WACC produces spread_classification="value_creating", ROIC < WACC produces "value_destroying". The label is clear and unambiguous in the response.
result: pass

### 3. Financial Sector NOPAT Formula Branching
expected: Stocks with industry containing "银行", "保险", or "证券" use interest-income-based NOPAT formula (net interest income + non-interest income - operating expenses). Non-financial stocks use operating profit - adjusted taxes. Both produce correct results.
result: pass

### 4. Edge Case: Debt-Free Companies and Negative Invested Capital
expected: Debt-free companies (NaN/zero debt fields) return WACC = Ke only (debt_weight=0). Companies with negative invested capital are flagged with negative_invested_capital=True and ROIC=None.
result: pass

### 5. 3-Year Moat Trend with Detection
expected: When 3+ years of data available, moat_trend field contains trend direction ("widening"=competitive advantage, "narrowing"=deteriorating, "stable"), slope, p_value, and data_points count. Widening spread flagged as moat.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
