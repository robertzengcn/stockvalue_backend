---
status: complete
phase: 10-capital-allocation-scorecard
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md]
started: 2026-05-06T07:30:00Z
updated: 2026-05-06T07:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Capital Allocation API Returns Complete Scorecard
expected: POST /api/v1/analyze/capex with a CSI 300 ticker returns success=True with data containing buyback_yield, dividend_stability, expansion_discipline, overall_grade, and weighting fields.
result: pass

### 2. Buyback Yield with Data Quality Classification
expected: Buyback yield dimension returns buyback_yield (float), grade (A/B/C/D), and data_quality field (COMPLETE/INCOMPLETE/NO_DATA). Stocks with recent repurchase programs show non-zero yield and appropriate grade.
result: pass

### 3. Dividend Stability Trend Classification
expected: Dividend stability dimension returns trend (Growth/Decline/Stable/Insufficient Data), grade, slope, and data_points. At least 3 years of DPU data produces a trend classification (not "Insufficient Data").
result: pass

### 4. Blind Expansion Alert Detection
expected: When a stock has ROIC < WACC (value-destroying) AND CapEx YoY growth exceeds 20%, the expansion_discipline dimension returns has_alert=True with alert_details containing capex_growth and expansion_risk fields. Otherwise has_alert=False.
result: pass

### 5. Combined Scorecard with Missing-Dimension Reweighting
expected: Overall grade is computed from three dimensions with equal weights (33/33/33). When buyback data is NO_DATA, the system reweights to 50/50 for the remaining two dimensions instead of penalizing. The weighting field reflects the actual weights used.
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
