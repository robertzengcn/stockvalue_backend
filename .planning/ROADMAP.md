# Roadmap: StockValueFinder

## Milestones

- **v1.0 MVP** — Phases 1-4 (shipped 2026-05-01) — [Archive](milestones/v1.0-ROADMAP.md)
- **v1.1 Smart Financial Report Pipeline** — Phases 5-8 (shipped 2026-05-02) — [Archive](milestones/v1.1-ROADMAP.md)
- **v1.2 Alpha Engine V2.0** — Phases 9-12 (shipped 2026-05-07) — [Archive](milestones/v1.2-ROADMAP.md)
- **v1.3 User Auth & Admin API** — Phases 13-16 (shipped 2026-05-11) — [Archive](milestones/v1.3-ROADMAP.md)
- **v1.4 Financial Metrics Validation** — Phases 17-24 (shipped 2026-05-23) — [Archive](milestones/v1.4-ROADMAP.md)
- **v1.5 Market Index Value Scanner** — Phases 25-28 (shipped 2026-06-05) — [Archive](milestones/v1.5-ROADMAP.md)
- **v1.6 Equity Pledge Risk Analysis** — Phases 29-31 (in progress)

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

<details>
<summary>v1.5 Market Index Value Scanner (Phases 25-28) — SHIPPED 2026-06-05</summary>

- [x] **Phase 25: Data Foundation** -- Database models, migrations, Pydantic models, repositories, scanner config
- [x] **Phase 26: Screening & Scoring Engine** -- Coarse screening rules, composite scoring, structured reason generation (3/3 plans)
- [x] **Phase 27: Market Scanner Service** — Scan orchestration, deep analysis integration, batch data operations (3/3 plans)
- [x] **Phase 28: Worker & API Integration** -- arq cron jobs, REST endpoints, watchlist integration (3/3 plans)

</details>

### v1.6 Equity Pledge Risk Analysis (In Progress)

**Milestone Goal:** Add equity pledge risk as an independent risk dimension to the existing risk analysis pipeline, enabling users to assess controlling shareholder pledge pressure and closeout risk.

- [x] **Phase 29: Pledge Data Foundation** - Pydantic models, AKShare client methods, field mapping, ticker normalization, ExternalDataService pledge interfaces, Redis caching, date backfill, gap closure (completed 2026-06-06)
- [ ] **Phase 30: Pledge Risk Calculation** - Pure functions for pledge risk grading, closeout safety margin, combination upgrade rules, risk merge, red flags, data freshness, holder identification, HK unsupported
- [ ] **Phase 31: Persistence & API Integration** - ORM models, Alembic migration, repository, risk_scores extension, API integration with graceful degradation, narrative prompt extension

## Phase Details

### Phase 29: Pledge Data Foundation

**Goal**: System can reliably fetch and cache A-share equity pledge data from AKShare with proper field normalization and automatic date discovery
**Depends on**: Phase 28 (v1.5 complete)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07
**Success Criteria** (what must be TRUE):

  1. User can fetch company pledge ratio snapshot for a given A-share ticker on a specific trade date, receiving company pledge ratio, pledged shares, market value, pledge count, unrestricted/restricted breakdown, and 1-year price change
  2. User can fetch important shareholder pledge details for a given A-share ticker, receiving holder name, pledge amounts, ratios, pledgee, closeout price, and dates
  3. AKShare 6-digit stock codes are automatically normalized to internal ticker format (e.g., 600519 becomes 600519.SH, 000002 becomes 000002.SZ)
  4. Pledge ratio data is cached in Redis with 24h TTL keyed by trade date, and pledge detail data is cached in Redis with 24h TTL keyed by latest, avoiding redundant bulk fetches
  5. When no trade date is specified, the system automatically finds the latest available date by trying the last 10 calendar days in reverse order

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 29-01-PLAN.md — Pydantic models for pledge data, field mapping, ticker normalization

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 29-02-PLAN.md — AKShare client pledge methods, ExternalDataService pledge interfaces, Redis caching, date backfill, Tushare fallback

**Wave 3** *(blocked on Waves 1 and 2 -- gap closure)*

- [x] 29-03-PLAN.md — Fix code review issues (CR-01, WR-01 to WR-04, IN-01 to IN-03), wire normalize_a_share_ticker, record DATA-07 deviation

### Phase 30: Pledge Risk Calculation

**Goal**: System grades equity pledge risk across company ratio, controlling shareholder ratio, and closeout safety margin, applying combination upgrade rules and merging with financial risk
**Depends on**: Phase 29
**Requirements**: RISK-01, RISK-02, RISK-03, RISK-04, RISK-05, RISK-06, RISK-07, RISK-08, RISK-09
**Success Criteria** (what must be TRUE):

  1. System grades company overall pledge risk into LOW/MEDIUM/HIGH based on company pledge ratio thresholds (<10% LOW, 20-30% MEDIUM, >30% HIGH, with notes for borderline ranges)
  2. System identifies the controlling shareholder or largest holder (highest pledged-to-holding ratio among top holders) and grades their pledge risk into LOW/MEDIUM/HIGH based on holder pledge ratio thresholds (<30% LOW, 50-80% MEDIUM, >80% HIGH)
  3. System calculates closeout safety margin as percentage above estimated closeout price and grades it (>50% LOW, 20-30% MEDIUM, <20% HIGH), and returns supported=false for HK tickers with appropriate warning
  4. System applies combination upgrade rules (high pledge + price drop, high pledge + financial flags) and merges pledge risk with financial risk where pledge can only upgrade the final risk level, producing an audit trail with structured red flags
  5. System classifies data freshness as CURRENT (within 10 days), STALE (older), or UNAVAILABLE (no data) based on the trade date of the pledge snapshot

**Plans**: 2 plans

Plans:

- [ ] 30-01-PLAN.md — Pledge risk grading pure functions (company ratio, holder ratio, closeout margin, freshness)
- [ ] 30-02-PLAN.md — Combination upgrade rules, risk merge logic, red flag generation, holder identification, HK unsupported

### Phase 31: Persistence & API Integration

**Goal**: Pledge risk data is persisted in the database and integrated into the existing risk API endpoint with full narrative support and graceful degradation
**Depends on**: Phase 30
**Requirements**: DB-01, DB-02, DB-03, DB-04, DB-05, DB-06, API-01, API-02, API-03, API-04, API-05, NARR-01, NARR-02, NARR-03, NARR-04
**Success Criteria** (what must be TRUE):

  1. Company pledge snapshots are persisted with unique constraint on (ticker, latest_date, source), and shareholder pledge details are persisted with indexes on (ticker, announcement_date) and (ticker, holder_name), both preserving raw API response for audit traceability
  2. The risk_scores table is extended with nullable pledge_risk JSONB and risk_level_breakdown JSONB columns via Alembic migration 021, without modifying existing data
  3. User can call the risk API with include_pledge_risk=true (default) and receive a pledge_risk object containing risk_level, company_pledge_ratio, controlling_holder_pledge_ratio, closeout_safety_margin, red_flags, and data_quality fields, plus a risk_level_breakdown showing financial_risk_level, pledge_risk_level, final_risk_level, and merge_reason
  4. When pledge data fetch fails, the risk API still returns complete financial risk results (M-Score, F-Score) with pledge_risk showing data_quality.freshness=UNAVAILABLE and an appropriate warning; HK stock requests return pledge_risk.supported=false without error
  5. Risk narrative includes an equity pledge paragraph when pledge data is available, explicitly forbids generating pledge numbers not in the structured fields, states "pledge data unavailable" when data is missing without implying low risk, and omits closeout distance when closeout_safety_margin is null

**Plans**: 2 plans

Plans:

- [ ] 31-01-PLAN.md — ORM models, Alembic migration 021, pledge repository with upsert and replace-all
- [ ] 31-02-PLAN.md — Risk API integration (include_pledge_risk param, response model extension, graceful degradation, HK handling)
- [ ] 31-03-PLAN.md — Narrative prompt extension for pledge risk with guarded output rules

## Progress

**Execution Order:**
Phases execute in numeric order: 29 -> 30 -> 31

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
| 26. Screening & Scoring Engine | v1.5 | 3/3 | Complete | 2026-06-04 |
| 27. Market Scanner Service | v1.5 | 3/3 | Complete | 2026-06-04 |
| 28. Worker & API Integration | v1.5 | 3/3 | Complete | 2026-06-05 |
| 29. Pledge Data Foundation | v1.6 | 3/3 | Complete   | 2026-06-06 |
| 30. Pledge Risk Calculation | v1.6 | 2/2 | Planned | - |
| 31. Persistence & API Integration | v1.6 | 0/3 | Not started | - |
