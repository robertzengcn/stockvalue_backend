# Roadmap: StockValueFinder

## Milestones

- **v1.0 MVP** — Phases 1-4 (shipped 2026-05-01) — [Archive](milestones/v1.0-ROADMAP.md)
- **v1.1 Smart Financial Report Pipeline** — Phases 5-8 (shipped 2026-05-02) — [Archive](milestones/v1.1-ROADMAP.md)
- **v1.2 Alpha Engine V2.0** — Phases 9-12 (shipped 2026-05-07) — [Archive](milestones/v1.2-ROADMAP.md)
- **v1.3 User Auth & Admin API** — Phases 13-16 (shipped 2026-05-11)
- **v1.4 Financial Metrics Validation** — Phases 17-23 (in progress)

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

<details>
<summary>v1.2 Alpha Engine V2.0 (Phases 9-12) — SHIPPED 2026-05-07</summary>

- [x] Phase 9: ROIC-WACC Spread Analysis (3/3 plans) — ROIC, true WACC, spread classification, 3-year moat trend
- [x] Phase 10: Capital Allocation Scorecard (3/3 plans) — Buyback yield, dividend stability, blind expansion alerts
- [x] Phase 11: Policy Resonance Engine (3/3 plans) — Policy upload, vector matching, DCF auto-adjustment
- [x] Phase 12: Alpha Composite Score (3/3 plans) — Weighted composite, unified API, persistence with audit trail

</details>

### v1.3 User Auth & Admin API (Shipped 2026-05-11)

**Milestone Goal:** Add JWT-based user authentication and admin management APIs to transition from single-user to multi-user system.

#### Phase 13: Auth Core & JWT
**Goal**: User model, JWT token service, auth middleware, and protected endpoints
**Depends on**: Nothing (first phase of v1.3)
**Requirements**: AUTH-01–07, RBAC-01–02, RBAC-05, ADMN-06–07, PROT-01–04, DB-01, DB-03–04
**Success Criteria** (what must be TRUE):
  1. User can register with email + password and receive JWT tokens
  2. User can login, refresh tokens, and logout
  3. All 7 analysis endpoints + document/pipeline endpoints require valid JWT
  4. Health check and root endpoints remain public
  5. First registered user automatically becomes admin
  6. Disabled users cannot login (403)
**Plans**: 4 plans

Plans:
- [x] 13-01: User ORM model + Alembic migration + Pydantic schemas
- [x] 13-02: JWT service (token generation, validation, refresh, bcrypt hashing)
- [x] 13-03: Auth routes (register, login, refresh, logout) + auth middleware (get_current_user, require_admin)
- [x] 13-04: Protect existing endpoints + tests for auth flow

#### Phase 14: Admin Management API
**Goal**: Admin endpoints for user CRUD, role management, enable/disable
**Depends on**: Phase 13
**Requirements**: RBAC-03–04, ADMN-01–05
**Success Criteria** (what must be TRUE):
  1. Admin can list all users (paginated) and view user details
  2. Admin can enable/disable user accounts
  3. Admin can change user roles (admin ↔ user)
  4. Admin can soft-delete users
  5. Non-admin users get 403 on admin endpoints
**Plans**: 3 plans

Plans:
- [x] 14-01: UserRepository with CRUD + admin-specific queries
- [x] 14-02: Admin routes (list, get, update role, disable/enable, delete)
- [x] 14-03: Admin route tests + RBAC enforcement tests

#### Phase 15: Access Control & Rate Limiting
**Goal**: Per-user stock access control and per-user rate limiting
**Depends on**: Phase 13
**Requirements**: ACCL-01–04, RATE-01–03, RATE-05, DB-02
**Success Criteria** (what must be TRUE):
  1. Analysis endpoints reject requests for unauthorized tickers (403)
  2. Admin can assign/remove stock tickers per user
  3. Rate limiting enforces 100 requests/hour per user
  4. Rate limit headers in responses (X-RateLimit-Remaining, X-RateLimit-Reset)
  5. Exceeding limit returns 429 with Retry-After header
**Plans**: 3 plans

Plans:
- [x] 15-01: UserStockAccess model + access control dependency
- [x] 15-02: Rate limiter (Redis-backed, per-user, configurable)
- [x] 15-03: Admin stock access endpoints + wiring + integration tests

#### Phase 16: Usage Analytics
**Goal**: Track and expose API usage per user for admin visibility
**Depends on**: Phase 13, Phase 15
**Requirements**: ANLY-01–05, RATE-04
**Success Criteria** (what must be TRUE):
  1. Every API call is tracked per user per endpoint
  2. Admin can view per-user usage summary (call counts, last active)
  3. Admin can view aggregate stats (total calls, top users, error rates)
  4. Admin can adjust per-user rate limits
  5. Usage data persists to DB periodically from Redis
**Plans**: 3 plans

Plans:
- [x] 16-01: Usage tracking middleware (Redis counters per user/endpoint)
- [x] 16-02: Analytics aggregation service + periodic DB flush
- [x] 16-03: Admin analytics routes + rate limit config routes + tests

### v1.4 Financial Metrics Validation (In Progress)

**Milestone Goal:** Build a systematic 3-layer verification system to validate that all financial analysis indicators produce numerically correct results end-to-end.

#### Phase 17: Metric Registry Foundation
**Goal**: YAML-based metric registry as single source of truth for all financial metrics across all 7 analysis modules
**Depends on**: Nothing (first phase of v1.4)
**Requirements**: REG-01, REG-02, REG-03, REG-04, REG-05
**Success Criteria** (what must be TRUE):
  1. `metric_registry.yaml` covers all metrics from all 7 analysis modules
  2. Each metric has formula reference, input field mappings, and output tolerance
  3. Sector variants defined for financial vs non-financial ROIC
  4. Pydantic validation catches schema errors at load time
  5. Registry can be loaded and queried by test/CLI code
**Plans**: 2 plans

Plans:
- [x] 17-01: Create validation module with Pydantic schema models + metric_registry.yaml with all metrics
- [ ] 17-02: Create loader (lru_cache), YAML schema validation, and registry query helpers

#### Phase 18: Golden Dataset Construction
**Goal**: 12-15 CSI 300 stocks with hand-verified expected values from annual reports
**Depends on**: Phase 17
**Requirements**: GOLD-01, GOLD-02, GOLD-03, GOLD-04, GOLD-05
**Success Criteria** (what must be TRUE):
  1. 12-15 stocks covering all major sectors (consumer, banking, insurance, tech, real estate, high-dividend, pharma, energy, industrials, materials)
  2. Each stock has frozen AKShare JSON for income/balance/cashflow statements
  3. Hand-verified expected_metrics.yaml sourced from annual reports, NOT AKShare
  4. provenance.md documents source page/line item for each golden value
  5. manifest.yaml catalogs all entries and drives test discovery
**Plans**: 2 plans

Plans:
- [ ] 18-01: Golden directory structure, manifest.yaml, provenance template
- [ ] 18-02: Hand-verify 12-15 stocks × 1 year each (2023), populate expected_metrics.yaml + frozen AKShare JSON

#### Phase 19: L1 Formula Verification
**Goal**: Verify every pure calculate_* function against published paper reference values
**Depends on**: Phase 17
**Requirements**: LV1-01, LV1-02, LV1-03, LV1-04, LV1-05
**Success Criteria** (what must be TRUE):
  1. M-Score 8 sub-indices each tested with paper-published input/output pairs
  2. ROIC both financial and non-financial formulas tested with 3+ examples each
  3. F-Score all 9 binary components tested at boundary conditions
  4. Remaining modules (WACC, FCF, Yield, CapEx, Policy, Alpha) have L1 reference tests
  5. All tests marked @pytest.mark.l1_formula
**Plans**: 2 plans

Plans:
- [ ] 19-01: L1 tests for risk_service (M-Score indices, F-Score, 存贷双高, goodwill)
- [ ] 19-02: L1 tests for roic_service, valuation_service, yield_service, capex_service, policy_service, alpha_service

#### Phase 20: L2 Field Mapping Verification
**Goal**: Verify AKShare/efinance field extraction correctness and cross-source consistency
**Depends on**: Phase 18, Phase 19
**Requirements**: LV2-01, LV2-02, LV2-03, LV2-04, LV2-05
**Success Criteria** (what must be TRUE):
  1. Frozen AKShare JSON snapshot tests assert key fields are non-null after extraction
  2. IndexAuditDetail numerator/denominator traceability tests pass
  3. AKShare vs efinance core fields deviate < 2%
  4. Financial stocks correctly trigger financial-sector extraction paths
  5. All tests marked @pytest.mark.l2_mapping
**Plans**: 2 plans

Plans:
- [ ] 20-01: L2 mapping snapshot tests + field traceability tests
- [ ] 20-02: Cross-source consistency tests + sector-branch verification tests

#### Phase 21: L3 End-to-End Golden Testing
**Goal**: Full pipeline validation from frozen data through calculation to golden expected value
**Depends on**: Phase 18, Phase 20
**Requirements**: LV3-01, LV3-02, LV3-03, LV3-04, LV3-05
**Success Criteria** (what must be TRUE):
  1. Full pipeline tests for all golden stocks against hand-verified expected values
  2. P0 metrics (M-Score, ROIC) 100% pass; P1 (WACC/FCF, Yield, CapEx) >= 90% pass
  3. Structured diff report on failure showing expected/computed/delta/tolerance
  4. Frozen tests (`-m golden`) run on every PR; live tests (`-m golden_live`) run weekly
  5. Test conftest provides golden_loader/comparator fixtures
**Plans**: 3 plans

Plans:
- [ ] 21-01: Golden test conftest with fixtures (loader, registry, comparator, frozen data injector)
- [ ] 21-02: L3 test suite — test_l3_golden.py with per-stock parametrized tests
- [ ] 21-03: Diff report generation + tolerance assertion helpers

#### Phase 22: Reconcile CLI Tool
**Goal**: Standalone CLI for comparing any ticker+year computed metrics against golden expected values
**Depends on**: Phase 17, Phase 21
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06
**Success Criteria** (what must be TRUE):
  1. `reconcile --ticker 600519.SH --year 2023` fetches live data and compares all metrics
  2. `--metric m_score` limits to single metric
  3. `--verbose` shows full audit_trail breakdown
  4. `--json` outputs machine-parseable JSON
  5. Colored pass/fail table with all expected columns
  6. Non-zero exit code when P0 metrics fail
**Plans**: 2 plans

Plans:
- [ ] 22-01: Typer CLI entry point + reconcile core logic (data fetch, compute, compare)
- [ ] 22-02: Rich table output, --verbose audit_trail, --json mode, exit codes

#### Phase 23: CI Integration & Polish
**Goal**: pytest markers, CI gates, pre-commit hook, and documentation
**Depends on**: Phase 19, Phase 20, Phase 21, Phase 22
**Requirements**: CI-01, CI-02, CI-03, CI-04, CI-05
**Success Criteria** (what must be TRUE):
  1. `pytest -m l1_formula` passes on every PR
  2. `pytest -m l2_mapping` passes on every PR
  3. `pytest -m golden` passes on every PR
  4. `pytest -m golden_live` scheduled weekly
  5. Metric registry YAML validation in pre-commit
**Plans**: 2 plans

Plans:
- [ ] 23-01: pytest.ini markers, CI config, pre-commit YAML validation hook
- [ ] 23-02: Documentation (README section, usage examples, golden contribution guide)

## Progress

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
| 17. Metric Registry Foundation | v1.4 | 1/2 | In Progress | — |
| 18. Golden Dataset Construction | v1.4 | 0/2 | Pending | — |
| 19. L1 Formula Verification | v1.4 | 0/2 | Pending | — |
| 20. L2 Field Mapping Verification | v1.4 | 0/2 | Pending | — |
| 21. L3 End-to-End Golden Testing | v1.4 | 0/3 | Pending | — |
| 22. Reconcile CLI Tool | v1.4 | 0/2 | Pending | — |
| 23. CI Integration & Polish | v1.4 | 0/2 | Pending | — |
