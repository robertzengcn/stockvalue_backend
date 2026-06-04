# Requirements: v1.5 Market Index Value Scanner

**Milestone:** v1.5
**Created:** 2026-06-04
**Status:** Active

## Index Data & Market Snapshot

### IDX-01: Index Constituent Synchronization
User can sync CSI 300 and CSI 500 constituent lists from AKShare, with each sync recording the effective date. Historical constituent changes are retained. A stock can belong to multiple indices simultaneously.

### IDX-02: Constituent History Tracking
When constituents change between syncs, previously active members are marked as removed with a removal date. The system preserves the last-known-good constituent list if sync fails.

### IDX-03: Batch Market Data Snapshot
User can fetch batch market snapshots (PE TTM, PB, dividend yield, market cap, turnover, ST status, suspension status) for all constituents of a given index in a single operation, with rate-limited API calls and caching.

### IDX-04: Valuation Percentile Calculation
User can calculate historical PE/PB percentile ranking for each stock within its index, showing where the current valuation sits relative to its 5-year history (e.g., "PB at 15th percentile of CSI 300 peers").

## Screening Funnel

### SCR-01: Market Coarse Screening
User can run a coarse screen that filters out ST stocks, suspended stocks, stocks with missing price data, stocks below minimum liquidity threshold, and stocks with persistently negative operating cash flow. Low PE, low PB, high dividend yield, and significant price drawdown stocks are prioritized.

### SCR-02: DCF Value Confirmation
User can run DCF valuation on the top N stocks from the coarse screen, calculating intrinsic value, WACC, safety margin, and valuation level. Stocks with safety margin >= 30% are flagged as potentially undervalued. The threshold is configurable.

### SCR-03: Risk and Quality Review
User can run a risk and quality review on value-confirmed stocks that checks ROIC-WACC spread (positive?), M-Score (below manipulation threshold?), operating cash flow vs net profit divergence, leverage and debt coverage, and dividend sustainability. Only stocks passing risk review enter the candidate list.

### SCR-04: Configurable Screening Thresholds
All screening thresholds (safety margin minimum, Top N count, risk exclusion criteria, liquidity minimum) are configurable via a frozen dataclass config, not hardcoded in business logic.

## Scoring & Explanation

### SCR-05: Composite Candidate Scoring
User can view a composite score for each candidate stock, calculated from 5 weighted dimensions: safety margin (35%), Alpha score (25%), risk penalty (20%), dividend yield gap (10%), and valuation percentile (10%). All components are normalized to 0-100 before weighting.

### SCR-06: Structured Reason Generation
Each candidate stock has machine-generated structured reasons explaining why it was selected (e.g., "safety margin 38%, above 30% threshold") and risk flags highlighting concerns (e.g., "inventory turnover slowing"). Reasons are derived from deterministic metrics, not LLM-generated.

### SCR-07: Configurable Scoring Weights
Scoring weights and candidate threshold (minimum composite score) are configurable. Default weights: safety margin 0.35, Alpha 0.25, risk penalty 0.20, yield gap 0.10, valuation percentile 0.10. Default minimum composite: 60.

## Execution & API

### EXE-01: Scheduled Daily Light Scan
User can trigger a daily post-market-close light scan that syncs constituents, fetches prices, runs coarse screening, performs DCF on Top N, and generates the candidate list. The scan runs as an arq cron job.

### EXE-02: Scheduled Weekly Deep Scan
User can trigger a weekly deep scan that supplements the daily scan by also refreshing financial reports, running full risk analysis, computing Alpha scores, and recalculating composite rankings.

### EXE-03: Manual Scan Trigger
Authorized users (admin) can manually trigger a scan via API with configurable parameters (index codes, scan type, Top N). The API enqueues an arq job rather than running synchronously.

### EXE-04: Scan Run Lifecycle Tracking
Each scan run has a unique run ID and tracks status through pending → running → completed/partial_failed. The run records total count, screened count, candidate count, rules version, and error summary. Single-stock failures are isolated and logged in error_summary without failing the entire run.

### EXE-05: Scan Results API - Runs
User can query scan run history with pagination, filtering by status and scan type. User can also query the latest run for a given index code.

### EXE-06: Scan Results API - Candidates
User can query candidate lists by run ID with pagination, filtering by index code, and sorting by rank, composite score, safety margin, or yield gap. Each candidate includes basic fields (price, intrinsic value, safety margin, risk level, Alpha score).

### EXE-07: Scan Results API - Candidate Detail
User can query full candidate detail including structured reasons, risk flags, screening snapshot, analysis references, and audit trail.

### EXE-08: Candidate-to-Watchlist Integration
User can add a candidate stock to their existing watchlist via API. Duplicate additions are handled gracefully (return success with already_exists flag). Added stocks enter the existing tracking pipeline.

---

## Future Requirements (Deferred)

- Event-triggered rescan (price drop > 10%, earnings release, index rebalance)
- Candidate change summary between scans (new entrants, dropouts, score changes)
- Industry theme index support (CSI 1000, CSI Dividend)
- User-custom stock pool scanning
- LLM narrative for candidate explanation (optional enhancement)
- Intraday real-time scanning

## Out of Scope

- Frontend candidate pool page — backend API only in v1.5
- Full A-share/HK stock universe — CSI 300 + CSI 500 only
- User-adjustable scanner weights in UI — config file only
- Investment advice language — all text must use "candidate", "research lead", "risk note" framing
- Batch report generation for all candidates — individual stock analysis via existing endpoints
- Live market data streaming — post-close batch processing only

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| IDX-01 | — | — |
| IDX-02 | — | — |
| IDX-03 | — | — |
| IDX-04 | — | — |
| SCR-01 | — | — |
| SCR-02 | — | — |
| SCR-03 | — | — |
| SCR-04 | — | — |
| SCR-05 | — | — |
| SCR-06 | — | — |
| SCR-07 | — | — |
| EXE-01 | — | — |
| EXE-02 | — | — |
| EXE-03 | — | — |
| EXE-04 | — | — |
| EXE-05 | — | — |
| EXE-06 | — | — |
| EXE-07 | — | — |
| EXE-08 | — | — |
