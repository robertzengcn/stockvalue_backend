# Requirements: StockValueFinder v1.3 — User Auth & Admin API

**Defined:** 2026-05-10
**Core Value:** Transition from single-user to multi-user system with JWT auth, RBAC, admin management, usage analytics, and rate limiting.

## v1 Requirements

### Authentication

- [ ] **AUTH-01**: User can register with email and password (open registration)
- [ ] **AUTH-02**: User can login and receive access + refresh JWT tokens
- [ ] **AUTH-03**: User can refresh expired access token using refresh token
- [ ] **AUTH-04**: User can logout (invalidates refresh token)
- [ ] **AUTH-05**: Passwords are hashed with bcrypt (never stored plaintext)
- [ ] **AUTH-06**: Email must be unique across all users
- [ ] **AUTH-07**: Password minimum 8 characters, validated on registration

### Role-Based Access Control

- [ ] **RBAC-01**: Two roles: `admin` and `user` (stored as enum in DB)
- [ ] **RBAC-02**: New registrations default to `user` role
- [ ] **RBAC-03**: Admin can change any user's role
- [ ] **RBAC-04**: Admin-only endpoints return 403 for non-admin users
- [ ] **RBAC-05**: Auth middleware extracts user identity from JWT on all protected endpoints

### Admin User Management

- [ ] **ADMN-01**: Admin can list all users (paginated)
- [ ] **ADMN-02**: Admin can view single user details
- [ ] **ADMN-03**: Admin can disable/enable user accounts
- [ ] **ADMN-04**: Admin can delete user (soft delete)
- [ ] **ADMN-05**: Admin can change user role (admin ↔ user)
- [ ] **ADMN-06**: Disabled users cannot authenticate (login returns 403)
- [ ] **ADMN-07**: First user registered becomes admin automatically (bootstrap)

### Per-User Access Control

- [ ] **ACCL-01**: Users can only access stocks they are permitted to analyze
- [ ] **ACCL-02**: Admin can assign/remove stock tickers per user
- [ ] **ACCL-03**: By default, new users have access to all CSI 300 stocks
- [ ] **ACCL-04**: Analysis endpoints reject requests for unauthorized tickers (403)

### Usage Analytics

- [ ] **ANLY-01**: System tracks API call count per user per endpoint
- [ ] **ANLY-02**: System tracks last active timestamp per user
- [ ] **ANLY-03**: Admin can view usage summary per user (call counts, last active)
- [ ] **ANLY-04**: Admin can view aggregate usage stats (total calls, top users, error rates)
- [ ] **ANLY-05**: Usage data stored in Redis with periodic DB flush for persistence

### Rate Limiting

- [ ] **RATE-01**: Per-user rate limiting on all analysis endpoints
- [ ] **RATE-02**: Default limit: 100 requests/hour per user (configurable)
- [ ] **RATE-03**: Rate limit headers included in responses (X-RateLimit-Remaining, X-RateLimit-Reset)
- [ ] **RATE-04**: Admin can adjust rate limits per user
- [ ] **RATE-05**: Requests exceeding limit return 429 with retry-after header

### Endpoint Protection

- [ ] **PROT-01**: All 7 analysis endpoints require valid JWT (risk, valuation, yield, roic, capex, policy, alpha)
- [ ] **PROT-02**: Document and pipeline endpoints require valid JWT
- [ ] **PROT-03**: Health check and root endpoints remain public (no auth)
- [ ] **PROT-04**: Auth endpoints (register, login, refresh) remain public

### Database & Migration

- [ ] **DB-01**: New `users` table with id, email, password_hash, role, is_active, created_at, updated_at
- [ ] **DB-02**: New `user_stock_access` table linking users to permitted tickers
- [ ] **DB-03**: Alembic migration for new tables
- [ ] **DB-04**: User ORM model follows existing conventions (SQLAlchemy 2.0, async)

## v2 Requirements

### Enhanced Auth

- **AUTH-08**: Email verification after registration
- **AUTH-09**: Password reset via email link
- **AUTH-10**: OAuth/social login (WeChat, Google)
- **AUTH-11**: Two-factor authentication (TOTP)
- **AUTH-12**: Account lockout after N failed login attempts

### Enhanced Admin

- **ADMN-08**: Admin audit log (who changed what, when)
- **ADMN-09**: Bulk user import/export
- **ADMN-10**: Admin dashboard web UI

### Enhanced Analytics

- **ANLY-06**: Usage charts and time-series data
- **ANLY-07**: Per-endpoint latency tracking
- **ANLY-08**: Cost estimation per analysis type

## Out of Scope

| Feature | Reason |
|---------|--------|
| Email verification | Requires email service (SendGrid/SMTP), adds infrastructure complexity |
| OAuth/social login | Third-party dependency, not needed for initial user base |
| Admin web UI | API-only for this milestone, frontend later |
| User-facing frontend | API-only milestone |
| WebSocket auth | System uses SSE, not WebSocket |
| API key auth | JWT sufficient, API keys add complexity |
| Multi-tenant isolation | Single-tenant with per-user stock access is sufficient |
| SSO/SAML | Enterprise feature, not needed for MVP |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Pending |
| AUTH-02 | Phase 1 | Pending |
| AUTH-03 | Phase 1 | Pending |
| AUTH-04 | Phase 1 | Pending |
| AUTH-05 | Phase 1 | Pending |
| AUTH-06 | Phase 1 | Pending |
| AUTH-07 | Phase 1 | Pending |
| RBAC-01 | Phase 1 | Pending |
| RBAC-02 | Phase 1 | Pending |
| RBAC-03 | Phase 2 | Pending |
| RBAC-04 | Phase 2 | Pending |
| RBAC-05 | Phase 1 | Pending |
| ADMN-01 | Phase 2 | Pending |
| ADMN-02 | Phase 2 | Pending |
| ADMN-03 | Phase 2 | Pending |
| ADMN-04 | Phase 2 | Pending |
| ADMN-05 | Phase 2 | Pending |
| ADMN-06 | Phase 1 | Pending |
| ADMN-07 | Phase 1 | Pending |
| ACCL-01 | Phase 3 | Pending |
| ACCL-02 | Phase 3 | Pending |
| ACCL-03 | Phase 3 | Pending |
| ACCL-04 | Phase 3 | Pending |
| ANLY-01 | Phase 4 | Pending |
| ANLY-02 | Phase 4 | Pending |
| ANLY-03 | Phase 4 | Pending |
| ANLY-04 | Phase 4 | Pending |
| ANLY-05 | Phase 4 | Pending |
| RATE-01 | Phase 3 | Pending |
| RATE-02 | Phase 3 | Pending |
| RATE-03 | Phase 3 | Pending |
| RATE-04 | Phase 4 | Pending |
| RATE-05 | Phase 3 | Pending |
| PROT-01 | Phase 1 | Pending |
| PROT-02 | Phase 1 | Pending |
| PROT-03 | Phase 1 | Pending |
| PROT-04 | Phase 1 | Pending |
| DB-01 | Phase 1 | Pending |
| DB-02 | Phase 3 | Pending |
| DB-03 | Phase 1 | Pending |
| DB-04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 41 total
- Mapped to phases: 41
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-10*
*Last updated: 2026-05-10 after initial definition*
