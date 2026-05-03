# Roadmap: StockValueFinder

## Milestones

- **v1.0 MVP** — Phases 1-4 (shipped 2026-05-01) — [Archive](milestones/v1.0-ROADMAP.md)
- **v1.1 Smart Financial Report Pipeline** — Phases 5-8 (shipped 2026-05-02) — [Archive](milestones/v1.1-ROADMAP.md)
- **v1.2 Alpha Engine V2.0** — Phases 9-12 (current milestone)

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

- [x] Phase 5: Pipeline Foundation (3/3 plans) — Config, DB schema, arq worker, state machine, health-check
- [x] Phase 6: Smart Watcher (3/3 plans) — Disclosure monitoring, season-aware polling, watchlist management
- [x] Phase 7: Report Processing (3/3 plans) — PDF download, dedup, RAG integration, parallel analysis
- [x] Phase 8: Task API, Notifications & Sandbox (3/3 plans) — Status endpoints, SSE events, subprocess sandbox

</details>

### v1.2 Alpha Engine V2.0 (Current)

**Milestone Goal:** Shift from "historical audit" to "forward-looking value prediction" by quantifying value creation (ROIC-WACC), capital efficiency, policy alignment, and composite Alpha scoring.

- [ ] **Phase 9: ROIC-WACC Spread Analysis** — Calculate ROIC, true WACC, spread classification, and 3-year moat trend
- [ ] **Phase 10: Capital Allocation Scorecard** — Buyback yield, dividend stability, blind expansion alerts, combined scorecard
- [ ] **Phase 11: Policy Resonance Engine** — Upload policy docs, vector-match to stocks, score resonance, auto-adjust DCF
- [ ] **Phase 12: Alpha Composite Score** — Weighted composite scoring, unified API endpoint, persistence with audit trail

## Phase Details

### Phase 9: ROIC-WACC Spread Analysis
**Goal**: Users can evaluate whether a stock creates or destroys value by comparing its return on invested capital against its weighted cost of capital, with 3-year trend detection for competitive moat identification.
**Depends on**: Phase 8 (v1.1 complete)
**Requirements**: ROIC-01, ROIC-02, ROIC-03, ROIC-04, ROIC-05, ROIC-06
**Success Criteria** (what must be TRUE):
  1. User can submit a CSI 300 ticker and receive ROIC, true WACC (weighted Ke + Kd), and spread value in a single response
  2. System correctly classifies spread as value-creating (ROIC > WACC) or value-destroying (ROIC < WACC) with clear label
  3. System handles financial sector stocks (banks, insurance, securities) with sector-specific NOPAT formula and produces correct results
  4. System handles edge cases gracefully: debt-free companies (NaN debt fields) return WACC = Ke, cash-rich companies (negative invested capital) are flagged with explanatory note
  5. User can view 3-year ROIC-WACC spread trend with moat detection (widening spread flagged as competitive advantage, narrowing flagged as deteriorating)
**Plans**: 3 plans

Plans:
- [ ] 09-01-PLAN.md — ROIC calculation engine: scipy install, ROICConfig, extend calculate_wacc(), roic domain models, roic_service pure functions, TDD unit tests
- [ ] 09-02-PLAN.md — Data access layer: multi-year AKShare fetch (D-04), Redis cache (D-05), ROICResultDB ORM model, Alembic migration 011, ROICResultRepository
- [ ] 09-03-PLAN.md — API wiring: POST /api/v1/analyze/roic endpoint, sector detection, full ROIC-WACC orchestration, persistence

### Phase 10: Capital Allocation Scorecard
**Goal**: Users can assess how well management deploys capital through buyback yield, dividend stability, and expansion discipline signals.
**Depends on**: Phase 9 (needs ROIC < WACC for blind expansion detection)
**Requirements**: CAPEX-01, CAPEX-02, CAPEX-03, CAPEX-04
**Success Criteria** (what must be TRUE):
  1. User can view buyback yield (repurchase amount / market cap) for any CSI 300 stock with data from AKShare stock_repurchase_em()
  2. User can view 5-year dividend per unit stability trend with classification (growth, decline, or stable) based on trend analysis
  3. System raises blind expansion alert when a stock has ROIC < WACC AND CapEx growth exceeds threshold, with alert details in the response
  4. User can view a combined capital allocation scorecard that integrates buyback yield, dividend stability, and expansion discipline into a single rated assessment
**Plans**: TBD

### Phase 11: Policy Resonance Engine
**Goal**: Users can measure how well a stock aligns with government policy direction through document-based semantic matching and receive automatic DCF parameter adjustments.
**Depends on**: Phase 8 (v1.1 complete, uses existing RAG pipeline)
**Requirements**: POL-01, POL-02, POL-03, POL-04
**Success Criteria** (what must be TRUE):
  1. User can upload a policy PDF document that is stored in a dedicated Qdrant collection (`policy_documents`) with policy-specific metadata
  2. System matches uploaded policy documents to stocks via vector similarity against stock business descriptions, with LLM classification to reduce false positives
  3. User can view a policy resonance score (0-100) per stock with matched policy excerpts and relevance explanation
  4. System auto-adjusts DCF terminal growth rate based on policy resonance (e.g., supportive policy adds +1% to terminal growth) and returns the adjustment details
**Plans**: TBD

### Phase 12: Alpha Composite Score
**Goal**: Users can see a single composite Alpha score that aggregates all forward-looking analysis dimensions with transparent weighting and full audit trail.
**Depends on**: Phase 9, Phase 10, Phase 11 (all component scores must be available)
**Requirements**: ALPHA-01, ALPHA-02, ALPHA-03
**Success Criteria** (what must be TRUE):
  1. User can view a composite Alpha score computed from fixed weights: 40% ROIC-WACC, 30% Capital Allocation, 20% Policy Resonance, 10% Moat trend
  2. User can retrieve all sub-scores and the composite via a single API endpoint that includes the full audit trail (input values, intermediate calculations, weight assignments)
  3. System persists Alpha analysis results with all component scores, DCF parameter adjustments, and timestamps for historical retrieval
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 9 -> 10 -> 11 -> 12

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
| 9. ROIC-WACC Spread Analysis | v1.2 | 0/3 | Planned | - |
| 10. Capital Allocation Scorecard | v1.2 | 0/? | Not started | - |
| 11. Policy Resonance Engine | v1.2 | 0/? | Not started | - |
| 12. Alpha Composite Score | v1.2 | 0/? | Not started | - |
