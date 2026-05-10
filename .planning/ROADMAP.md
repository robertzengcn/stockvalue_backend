# Roadmap: StockValueFinder

## Milestones

- **v1.0 MVP** — Phases 1-4 (shipped 2026-05-01) — [Archive](milestones/v1.0-ROADMAP.md)
- **v1.1 Smart Financial Report Pipeline** — Phases 5-8 (shipped 2026-05-02) — [Archive](milestones/v1.1-ROADMAP.md)
- **v1.2 Alpha Engine V2.0** — Phases 9-12 (shipped 2026-05-07) — [Archive](milestones/v1.2-ROADMAP.md)
- **v1.3 User Auth & Admin API** — Phases 13-16 (in progress)

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

### v1.3 User Auth & Admin API (In Progress)

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
- [ ] 14-01: UserRepository with CRUD + admin-specific queries
- [ ] 14-02: Admin routes (list, get, update role, disable/enable, delete)
- [ ] 14-03: Admin route tests + RBAC enforcement tests

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
- [ ] 15-01: UserStockAccess model + access control middleware
- [ ] 15-02: Rate limiter (Redis-backed, per-user, configurable)
- [ ] 15-03: Access control routes + rate limit tests

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
- [ ] 16-01: Usage tracking middleware (Redis counters per user/endpoint)
- [ ] 16-02: Analytics aggregation service + periodic DB flush
- [ ] 16-03: Admin analytics routes + rate limit config routes + tests

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
| 14. Admin Management API | v1.3 | 0/3 | Not started | - |
| 15. Access Control & Rate Limiting | v1.3 | 0/3 | Not started | - |
| 16. Usage Analytics | v1.3 | 0/3 | Not started | - |
