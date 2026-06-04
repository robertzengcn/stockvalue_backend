# Phase 10: Capital Allocation Scorecard - Discussion Log

**Date:** 2026-05-05
**Phase:** 10 - Capital Allocation Scorecard

## Areas Discussed

### 1. Buyback Data Strategy
**Options presented:**
- Cache all ~5088 stocks, filter on read (Recommended)
- Per-stock fetch with cache
- You decide

**User selection:** Cache all, filter on read

**Follow-up:** Buyback yield calculation period
**Options presented:**
- Annual repurchase amount (Recommended)
- Trailing 12-month sum
- You decide

**User selection:** Annual repurchase amount

### 2. Dividend Stability Method
**Options presented:**
- Existing DB + AKShare fallback (Recommended)
- Fresh AKShare always
- You decide

**User selection:** Existing DB + AKShare fallback

**Follow-up:** Trend classification method
**Options presented:**
- Linear regression with scipy (Recommended, consistent with Phase 9)
- Simple YoY comparison
- You decide

**User selection:** Linear regression

### 3. Blind Expansion Threshold
**Options presented:**
- 20% YoY CapEx growth (Recommended)
- 50% YoY CapEx growth
- 3-year CAGR > 15%

**User selection:** 20% YoY CapEx growth

**Follow-up:** CapEx data source
**Options presented:**
- Existing CapEx from financials (Recommended)
- You decide

**User selection:** Existing CapEx from financials

### 4. Scorecard Weighting
**Options presented:**
- Letter grades A/B/C/D (Recommended)
- Numerical 0-100 score
- You decide

**User selection:** Letter grades A/B/C/D

**Follow-up:** Dimension weighting
**Options presented:**
- Equal weight 33/33/33 (Recommended)
- Shareholder-friendly 40/30/30
- You decide

**User selection:** Equal weight 33/33/33

## Summary

All 4 gray areas discussed. No deferred ideas. No scope creep detected.

---
*Phase 10 Discussion - 2026-05-05*
