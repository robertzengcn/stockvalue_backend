# Roadmap: StockValueFinder

## Milestones

- **v1.0 MVP** — Phases 1-4 (shipped 2026-05-01) — [Archive](milestones/v1.0-ROADMAP.md)
- **v1.1 Smart Financial Report Pipeline** — Phases 5-8 (shipped 2026-05-02) — [Archive](milestones/v1.1-ROADMAP.md)
- **v1.2 Alpha Engine V2.0** — Phases 9-12 (shipped 2026-05-07) — [Archive](milestones/v1.2-ROADMAP.md)
- **v1.3 User Auth & Admin API** — Phases 13-16 (shipped 2026-05-11) — [Archive](milestones/v1.3-ROADMAP.md)
- **v1.4 Financial Metrics Validation** — Phases 17-24 (shipped 2026-05-23) — [Archive](milestones/v1.4-ROADMAP.md)
- **v1.5 Market Index Value Scanner** — Phases 25-28 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) — SHIPPED 2026-05-01</summary>

- [x] Phase 1: M-Score Real Calculation (2/2 plans)
- [x] Phase 2: Redis Cache Integration (2/2 plans)
- [x] Phase 3: Test Coverage (6/6 plans)
- [x] Phase 4: RAG Pipeline (5/5 plans)

</details>

<details>
<summary>v1.1 Smart Financial Report Pipeline (Phases 5-8) — SHIPPED 2026-05-02</summary>

- [x] Phase 5: Pipeline Foundation (3/3 plans)
- [x] Phase 6: Smart Watcher (3/3 plans)
- [x] Phase 7: Report Processing (3/3 plans)
- [x] Phase 8: Task API, Notifications & Sandbox (3/3 plans)

</details>

<details>
<summary>v1.2 Alpha Engine V2.0 (Phases 9-12) — SHIPPED 2026-05-07</summary>

- [x] Phase 9: ROIC-WACC Spread Analysis (3/3 plans)
- [x] Phase 10: Capital Allocation Scorecard (3/3 plans)
- [x] Phase 11: Policy Resonance Engine (3/3 plans)
- [x] Phase 12: Alpha Composite Score (3/3 plans)

</details>

<details>
<summary>v1.3 User Auth & Admin API (Phases 13-16) — SHIPPED 2026-05-11</summary>

- [x] Phase 13: Auth Core & JWT (4/4 plans)
- [x] Phase 14: Admin Management API (3/3 plans)
- [x] Phase 15: Access Control & Rate Limiting (3/3 plans)
- [x] Phase 16: Usage Analytics (3/3 plans)

</details>

<details>
<summary>v1.4 Financial Metrics Validation (Phases 17-24) — SHIPPED 2026-05-23</summary>

- [x] Phase 17: Metric Registry Foundation (2/2 plans)
- [x] Phase 18: Golden Dataset Construction (2/2 plans)
- [x] Phase 19: L1 Formula Verification (2/2 plans)
- [x] Phase 20: L2 Field Mapping Verification (2/2 plans)
- [x] Phase 21: L3 End-to-End Golden Testing (3/3 plans)
- [x] Phase 22: Reconcile CLI Tool (2/2 plans)
- [x] Phase 23: CI Integration & Polish (2/2 plans)
- [x] Phase 24: Golden Dataset Expansion (2/2 plans)

</details>

### v1.5 Market Index Value Scanner (Phases 25-28)

- [x] **Phase 25: Data Foundation** -- Database models, migrations, Pydantic models, repositories, scanner config
- [ ] **Phase 26: Screening & Scoring Engine** — Coarse screening rules, composite scoring, structured reason generation
- [ ] **Phase 27: Market Scanner Service** — Scan orchestration, deep analysis integration, batch data operations
- [ ] **Phase 28: Worker & API Integration** — arq cron jobs, REST endpoints, watchlist integration

## Phase Details

### Phase 25: Data Foundation
**Goal**: Scanner data can be persisted and queried -- index constituents are tracked, scan runs have full lifecycle state, and all thresholds are configurable via frozen dataclass
**Depends on**: Phase 24 (v1.4 complete)
**Requirements**: IDX-01, IDX-02, EXE-04, SCR-04
**Success Criteria** (what must be TRUE):
  1. User can sync CSI 300 and CSI 500 constituent lists, and each sync records the effective date with historical changes retained
  2. When constituents change between syncs, previously active members are marked as removed with a removal date, and the last-known-good list is preserved if sync fails
  3. Each scan run has a unique run ID and tracks status through pending, running, completed, and partial_failed with total/screened/candidate counts and error summary
  4. All screening thresholds (safety margin minimum, Top N count, risk exclusion criteria, liquidity minimum) are defined in a frozen dataclass config, not hardcoded
**Plans**: 2 plans

Plans:
- [x] 25-01-PLAN.md — ORM models, Pydantic models, frozen config, enums, migration
- [x] 25-02-PLAN.md -- Repositories with state machine, constituent sync, history tracking

### Phase 26: Screening & Scoring Engine
**Goal**: Stocks can be filtered through the coarse screen and ranked by composite score with deterministic, structured explanations
**Depends on**: Phase 25
**Requirements**: SCR-01, SCR-05, SCR-06, SCR-07
**Success Criteria** (what must be TRUE):
  1. User can run a coarse screen that filters out ST stocks, suspended stocks, stocks with missing price data, stocks below minimum liquidity, and stocks with persistently negative operating cash flow, while prioritizing low PE/PB, high dividend yield, and price drawdown stocks
  2. User can view a composite score for each candidate calculated from 5 weighted dimensions (safety margin 35%, Alpha 25%, risk penalty 20%, yield gap 10%, valuation percentile 10%), with all components normalized to 0-100 before weighting
  3. Each candidate stock has machine-generated structured reasons explaining selection (e.g., "safety margin 38%, above 30% threshold") and risk flags highlighting concerns, all derived from deterministic metrics
  4. Scoring weights and minimum composite score threshold are configurable, with defaults: safety margin 0.35, Alpha 0.25, risk penalty 0.20, yield gap 0.10, valuation percentile 0.10, minimum composite 60
**Plans**: 3 plans

Plans:
- [x] 26-01-PLAN.md -- ScoringWeightsConfig, extended MarketScannerConfig, screening/scoring Pydantic models
- [ ] 26-02-PLAN.md -- Coarse screener (SCR-01) and composite scorer (SCR-05, SCR-07)
- [ ] 26-03-PLAN.md -- Deterministic reason generator (SCR-06)

### Phase 27: Market Scanner Service
**Goal**: A complete scan orchestrates constituent sync, batch data fetching, deep analysis (DCF, risk, yield, Alpha), and candidate persistence -- with single-stock failure isolation
**Depends on**: Phase 26
**Requirements**: IDX-03, IDX-04, SCR-02, SCR-03
**Success Criteria** (what must be TRUE):
  1. User can fetch batch market snapshots (PE TTM, PB, dividend yield, market cap, turnover, ST status, suspension status) for all constituents of a given index in a single operation with rate-limited API calls and caching
  2. User can calculate historical PE/PB percentile ranking for each stock within its index, showing where current valuation sits relative to its 5-year history
  3. User can run DCF valuation on top N stocks from the coarse screen, calculating intrinsic value, WACC, safety margin, and valuation level, with stocks at safety margin >= 30% flagged as potentially undervalued (threshold configurable)
  4. User can run a risk and quality review on value-confirmed stocks checking ROIC-WACC spread, M-Score, cash flow divergence, leverage, and dividend sustainability, where only stocks passing the review enter the candidate list
**Plans**: TBD

### Phase 28: Worker & API Integration
**Goal**: Scans run automatically on schedule via arq cron jobs, and users can query results, trigger manual scans, and add candidates to their watchlist via REST API
**Depends on**: Phase 27
**Requirements**: EXE-01, EXE-02, EXE-03, EXE-05, EXE-06, EXE-07, EXE-08
**Success Criteria** (what must be TRUE):
  1. A daily post-market-close light scan runs as an arq cron job, syncing constituents, fetching prices, running coarse screening, performing DCF on top N, and generating the candidate list
  2. A weekly deep scan runs as an arq cron job, supplementing the daily scan by refreshing financial reports, running full risk analysis, computing Alpha scores, and recalculating composite rankings
  3. Admin users can manually trigger a scan via API with configurable parameters (index codes, scan type, top N), where the API enqueues an arq job rather than running synchronously
  4. User can query scan run history with pagination and filtering by status and scan type, and can query the latest run for a given index code
  5. User can query candidate lists by run ID with pagination, filtering by index code, and sorting by rank, composite score, safety margin, or yield gap
  6. User can query full candidate detail including structured reasons, risk flags, screening snapshot, analysis references, and audit trail
  7. User can add a candidate stock to their existing watchlist via API, with duplicate additions returning success with an already_exists flag
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 25 -> 26 -> 27 -> 28

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. M-Score Real Calculation | v1.0 | 2/2 | Complete | 2026-04-15 |
| 2. Redis Cache Integration | v1.0 | 2/2 | Complete | 2026-04-16 |
| 3. Test Coverage | v1.0 | 6/6 | Complete | 2026-04-17 |
| 4. RAG Pipeline | v1.0 | 5/5 | Complete | 2026-04-19 |
| 5. Pipeline Foundation | v1.1 | 3/3 | Complete | 2026-05-01 |
| 6. Smart Watcher | v1.1 | 3/3 | Complete | 2026-05-01 |
| 7. Report Processing | v1.1 | 3/3 | Complete | 2026-05-02 |
| 8. Task API, Notifications & Sandbox | v1.1 | 3/3 | Complete | 2026-05-02 |
| 9. ROIC-WACC Spread Analysis | v1.2 | 3/3 | Complete | 2026-05-03 |
| 10. Capital Allocation Scorecard | v1.2 | 3/3 | Complete | 2026-05-06 |
| 11. Policy Resonance Engine | v1.2 | 3/3 | Complete | 2026-05-06 |
| 12. Alpha Composite Score | v1.2 | 3/3 | Complete | 2026-05-07 |
| 13. Auth Core & JWT | v1.3 | 4/4 | Complete | 2026-05-10 |
| 14. Admin Management API | v1.3 | 3/3 | Complete | 2026-05-11 |
| 15. Access Control & Rate Limiting | v1.3 | 3/3 | Complete | 2026-05-11 |
| 16. Usage Analytics | v1.3 | 3/3 | Complete | 2026-05-11 |
| 17. Metric Registry Foundation | v1.4 | 2/2 | Complete | 2026-05-21 |
| 18. Golden Dataset Construction | v1.4 | 2/2 | Complete | 2026-05-21 |
| 19. L1 Formula Verification | v1.4 | 2/2 | Complete | 2026-05-21 |
| 20. L2 Field Mapping Verification | v1.4 | 2/2 | Complete | 2026-05-21 |
| 21. L3 End-to-End Golden Testing | v1.4 | 3/3 | Complete | 2026-05-21 |
| 22. Reconcile CLI Tool | v1.4 | 2/2 | Complete | 2026-05-21 |
| 23. CI Integration & Polish | v1.4 | 2/2 | Complete | 2026-05-21 |
| 24. Golden Dataset Expansion | v1.4 | 2/2 | Complete | 2026-05-23 |
| 25. Data Foundation | v1.5 | 2/2 | Complete | 2026-06-04 |
| 26. Screening & Scoring Engine | v1.5 | 1/3 | In progress | - |
| 27. Market Scanner Service | v1.5 | 0/? | Not started | - |
| 28. Worker & API Integration | v1.5 | 0/? | Not started | - |
