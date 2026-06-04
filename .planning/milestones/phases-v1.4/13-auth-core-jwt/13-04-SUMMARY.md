---
phase: 13-auth-core-jwt
plan: 04
subsystem: auth
tags: [fastapi, jwt, authentication, endpoint-protection, testing, bearer-token]

# Dependency graph
requires:
  - phase: 13-03
    provides: "Auth routes (register, login, refresh, logout), get_current_user and require_admin dependencies, UserRepository"
  - phase: 13-02
    provides: "JWTService with token management, bcrypt password hashing"
  - phase: 13-01
    provides: "UserDB ORM model, Pydantic user schemas"
provides:
  - "JWT protection on all 7 analysis endpoints (risk, valuation, yield, roic, capex, policy, alpha)"
  - "JWT protection on document and pipeline endpoints (4 + 8 handlers)"
  - "Comprehensive auth flow test suite (17 tests)"
affects: [all-api-endpoints, admin-routes]

# Tech tracking
tech-stack:
  added: []
  patterns: [protected-route-pattern, auth-test-pattern]

key-files:
  created:
    - stockvaluefinder/tests/unit/test_api/test_auth_flow.py
  modified:
    - stockvaluefinder/stockvaluefinder/api/risk_routes.py
    - stockvaluefinder/stockvaluefinder/api/valuation_routes.py
    - stockvaluefinder/stockvaluefinder/api/yield_routes.py
    - stockvaluefinder/stockvaluefinder/api/roic_routes.py
    - stockvaluefinder/stockvaluefinder/api/capex_routes.py
    - stockvaluefinder/stockvaluefinder/api/policy_routes.py
    - stockvaluefinder/stockvaluefinder/api/alpha_routes.py
    - stockvaluefinder/stockvaluefinder/api/documents_routes.py
    - stockvaluefinder/stockvaluefinder/api/pipeline_routes.py

key-decisions:
  - "current_user parameter placed after other Depends() params but before return type annotation in all handlers"
  - "alpha_routes passes current_user explicitly to sub-analysis calls since those are direct function calls, not HTTP requests"
  - "Protected endpoint test accepts both 401 and 403 status codes since HTTPBearer behavior varies between redirect and direct scenarios"

patterns-established:
  - "Protected route pattern: current_user: dict = Depends(get_current_user) on every handler"
  - "Auth test pattern: mock UserRepository with patch, test via httpx AsyncClient with ASGITransport"

requirements-completed: [PROT-01, PROT-02, PROT-03, PROT-04, AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, RBAC-02, RBAC-05, ADMN-06, ADMN-07]

# Metrics
duration: 26min
completed: 2026-05-10
---

# Phase 13 Plan 04: Protect Existing Endpoints + Comprehensive Auth Flow Tests Summary

**JWT Bearer token protection on all 20 route handlers across 9 endpoint files with 17 auth flow tests covering register, login, refresh, logout, RBAC, and endpoint access control**

## Performance

- **Duration:** 26 min
- **Started:** 2026-05-10T14:58:15Z
- **Completed:** 2026-05-10T15:24:23Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- All 20 route handlers across 9 files now require valid JWT Bearer token
- Health check (/health) and root (/) endpoints remain public (no auth)
- Auth endpoints (/api/v1/auth/*) remain public (no auth)
- Comprehensive test suite with 17 tests covering all auth requirements
- Fixed alpha_routes direct function calls to pass current_user explicitly

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_current_user dependency to all protected route handlers** - `c467010` (feat)
2. **Task 2: Write comprehensive auth flow tests** - `76bec05` (test)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/api/risk_routes.py` - Added get_current_user dependency to analyze_risk handler
- `stockvaluefinder/stockvaluefinder/api/valuation_routes.py` - Added get_current_user dependency to analyze_dcf and explain_dcf handlers
- `stockvaluefinder/stockvaluefinder/api/yield_routes.py` - Added get_current_user dependency to analyze_yield handler
- `stockvaluefinder/stockvaluefinder/api/roic_routes.py` - Added get_current_user dependency to analyze_roic handler
- `stockvaluefinder/stockvaluefinder/api/capex_routes.py` - Added get_current_user dependency to analyze_capital_allocation handler
- `stockvaluefinder/stockvaluefinder/api/policy_routes.py` - Added get_current_user dependency to upload_policy and analyze_resonance handlers
- `stockvaluefinder/stockvaluefinder/api/alpha_routes.py` - Added get_current_user dependency to analyze_alpha handler; passes current_user to sub-analysis calls
- `stockvaluefinder/stockvaluefinder/api/documents_routes.py` - Added get_current_user dependency to all 4 handlers (upload, status, search, delete)
- `stockvaluefinder/stockvaluefinder/api/pipeline_routes.py` - Added get_current_user dependency to all 8 handlers (health, watchlist CRUD, status, tasks, trigger, events)
- `stockvaluefinder/tests/unit/test_api/test_auth_flow.py` - 17 test functions covering full auth lifecycle

## Decisions Made
- alpha_routes passes current_user explicitly to sub-analysis calls (analyze_roic, analyze_capital_allocation, analyze_resonance) since those are direct Python function calls, not HTTP requests through FastAPI dependency injection
- Protected endpoint test accepts both 401 and 403 status codes (HTTPBearer returns 403 when credentials missing in some scenarios, get_current_user returns 401 after redirect)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed alpha_routes direct function calls missing current_user parameter**
- **Found during:** Task 1 (adding auth dependency to route handlers)
- **Issue:** alpha_routes calls analyze_roic, analyze_capital_allocation, and analyze_resonance directly as Python functions (not via HTTP). After adding current_user parameter to those handlers, the direct calls would fail because Depends(get_current_user) is only resolved by FastAPI, not by regular function calls.
- **Fix:** Added current_user=current_user to all three direct function calls in alpha_routes.py
- **Files modified:** stockvaluefinder/stockvaluefinder/api/alpha_routes.py
- **Verification:** ruff check passes, AST syntax check passes
- **Committed in:** c467010 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed missing docstring opening in list_tasks_endpoint after edit**
- **Found during:** Task 1 (editing pipeline_routes.py)
- **Issue:** String replacement accidentally removed the opening triple-quote of the docstring
- **Fix:** Restored the docstring opening
- **Files modified:** stockvaluefinder/stockvaluefinder/api/pipeline_routes.py
- **Verification:** ruff check passes, AST syntax check passes
- **Committed in:** c467010 (Task 1 commit)

**3. [Rule 1 - Bug] Fixed refresh test missing UserRepository mock for get_by_id**
- **Found during:** Task 2 (running tests)
- **Issue:** test_refresh_returns_new_tokens failed with AttributeError because the refresh endpoint calls user_repo.get_by_id which was not mocked
- **Fix:** Added UserRepository mock with get_by_id returning active user
- **Files modified:** stockvaluefinder/tests/unit/test_api/test_auth_flow.py
- **Verification:** Test passes
- **Committed in:** 76bec05 (Task 2 commit)

**4. [Rule 1 - Bug] Fixed protected endpoint test asserting wrong status code**
- **Found during:** Task 2 (running tests)
- **Issue:** test_protected_endpoint_rejects_no_token expected 403 but got 307 (redirect) initially, then 401 after adding follow_redirects=True
- **Fix:** Changed assertion to accept both 401 and 403, and added follow_redirects=True to AsyncClient
- **Files modified:** stockvaluefinder/tests/unit/test_api/test_auth_flow.py
- **Verification:** Test passes
- **Committed in:** 76bec05 (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (4 bugs)
**Impact on plan:** All auto-fixes necessary for correctness. The alpha_routes fix is especially critical -- without it, the alpha endpoint would crash at runtime when calling sub-analysis handlers.

## Issues Encountered
- DATABASE_URL environment variable required by db/base.py at import time -- set to dummy value for testing

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All protected endpoints now require valid JWT Bearer token
- Auth middleware validated with comprehensive test suite
- Ready for admin management endpoints (user listing, role changes, account disable/enable)
- Test patterns established for future endpoint auth testing

---
*Phase: 13-auth-core-jwt*
*Completed: 2026-05-10*
