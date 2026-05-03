# Feature Landscape

**Domain:** Financial analysis platform -- value investing Alpha scoring
**Researched:** 2026-05-03

## Table Stakes

Features users expect from an "Alpha Engine" that claims to identify value creation. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| ROIC-WACC spread calculation | Core value creation metric. Every serious value investor checks whether a company earns above its cost of capital. | Medium | NOPAT + Invested Capital from AKShare financial statements. WACC reused from existing valuation_service. |
| 3-year ROIC-WACC trend | A single year's spread is noise. Users need to see if the moat is widening or narrowing. | Low | scipy.stats.linregress on 3 annual data points. Slope + p-value. |
| Buyback yield calculation | Shareholders benefit from buybacks. Users expect this in capital allocation analysis. | Low | AKShare `stock_repurchase_em()` provides `已回购金额`. Divide by market cap. |
| Dividend stability score | 5-year DPU consistency is a basic income investor metric. | Low | Coefficient of variation from existing `get_dividend_history()`. |
| Composite Alpha score | Users want a single number to rank stocks. Multi-dimensional scoring is the core value prop. | Low | Fixed weighted sum: 40% ROIC-WACC + 30% Capital Allocation + 20% Policy + 10% Moat. |
| Policy document upload | "Upload a policy doc and see how it affects my stocks" is the headline feature. | Medium | Reuses existing PDF upload + RAG pipeline. New Qdrant collection for policy docs. |
| Blind expansion detection | Alerting when ROIC < WACC AND CapEx is surging is a critical risk signal. | Medium | Requires ROIC-WACC from Phase 1 + CapEx from cash flow. |
| Standardized API responses | All analysis endpoints must return `ApiResponse[T]` envelope. | Low | Existing pattern. Just follow it. |
| Audit trail on all calculations | Every financial result must trace back to source data and formula parameters. | Low | Follow existing pattern from M-Score and DCF audit trails. |

## Differentiators

Features that set the product apart from basic stock screeners.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Policy Resonance Engine | No other free tool matches uploaded policy documents to stock analysis and auto-adjusts DCF parameters. This is the killer feature. | High | RAG search + LLM extraction of DCF parameter adjustments. Unique in free tools. |
| Moat trend detection with p-value | Not just "ROIC > WACC" but "is the spread statistically widening over 3 years?" Academic rigor. | Low | scipy linregress p-value separates signal from noise. |
| Integrated Alpha composite | Single number combining value creation (ROIC), capital efficiency, policy alignment, and moat durability. | Low | Fixed weights make it transparent and auditable. |
| Auto-adjust DCF parameters from policy | Upload a government policy PDF, and the system suggests terminal growth rate and risk premium adjustments. | High | LLM extracts structured adjustments. Novel feature. |

## Anti-Features

Features to explicitly NOT build for this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Live policy news crawling | Out of scope per PROJECT.md. Requires web scraping infrastructure, rate limiting, dedup. | Upload-based RAG matching. Users upload policy docs they care about. |
| User-adjustable Alpha weights | Adds configuration complexity. Fixed weights are transparent and auditable. | Hardcode weights in AlphaConfig (40/30/20/10). |
| Machine-learned Alpha weights | Would require historical backtesting data, model training, and validation infrastructure. | Fixed weights based on academic literature. No ML. |
| Sector-specific ROIC benchmarks | Would require building a sector classification system and benchmark database. | Use absolute ROIC-WACC spread (positive = value creation). |
| Real-time ROIC alerts | Requires WebSocket/SSE for continuous monitoring, not just on-demand analysis. | On-demand analysis via API endpoint. User requests when they want it. |
| HK stock buyback data | `stock_repurchase_em()` is A-share only. HK stock data has different source structure. | A-share CSI 300 only for this milestone. |
| Multi-year batch screening | Running ROIC for all CSI 300 stocks at once would hammer AKShare rate limits. | Per-stock on-demand analysis. Batch screening is future milestone. |

## Feature Dependencies

```
ROIC-WACC Spread Analysis
  |
  +---> Capital Allocation Scorecard (blind expansion needs ROIC < WACC)
  |
  +---> Composite Alpha Score (40% weight from ROIC-WACC)
  
Capital Allocation Scorecard
  |
  +---> Composite Alpha Score (30% weight from Capital Allocation)
  
Policy Resonance Engine (independent)
  |
  +---> Composite Alpha Score (20% weight from Policy)
  
3-Year Moat Trend (builds on ROIC-WACC)
  |
  +---> Composite Alpha Score (10% weight from Moat trend)
```

## MVP Recommendation

Prioritize:
1. ROIC-WACC spread with 3-year trend (foundation -- everything depends on it)
2. Capital Allocation scorecard (uses ROIC for blind expansion detection)
3. Composite Alpha score (aggregates all components into single number)

Defer to future milestone:
- Live policy crawling: upload-based matching is sufficient for v1.2
- Batch CSI 300 screening: per-stock analysis first
- HK stock support: A-share only for this milestone

## Sources

- PROJECT.md requirements: ROIC-WACC, Capital Allocation, Policy Resonance, Composite Alpha
- AKShare v1.18.46 verified: financial statements, repurchase data, dividend history
- Existing codebase analysis: 8 ORM models, 3 analysis APIs, RAG pipeline
