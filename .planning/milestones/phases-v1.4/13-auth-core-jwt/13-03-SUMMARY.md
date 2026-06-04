---
phase: 13-auth-core-jwt
plan: 03
subsystem: auth
tags: [fastapi, jwt, bcrypt, authentication, rbac, middleware, user-repository]

# Dependency graph
requires:
  - phase: 13-01
    provides: "UserDB ORM model, Pydantic user schemas (UserCreate, TokenResponse, UserResponse)"
  - phase: 13-02
    provides: "JWTService with token management and bcrypt password hashing, AuthConfig"
provides:
  - "UserRepository with get_by_id, get_by_email, create, count_users, update_role, set_active"
  - "Auth routes: POST /api/v1/auth/register, /login, /refresh, /logout"
  - "get_current_user FastAPI dependency for JWT bearer token validation"
  - "require_admin FastAPI dependency for admin role enforcement"
  - "First-user-becomes-admin bootstrap logic"
affects: [13-04, admin-routes, protected-routes]

# Tech tracking
tech-stack:
  added: []
  patterns: [auth-route-pattern, fastapi-bearer-dependency, first-user-admin-bootstrap, generic-auth-error]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/repositories/user_repo.py
    - stockvaluefinder/stockvaluefinder/api/auth_routes.py
  modified:
    - stockvaluefinder/stockvaluefinder/api/dependencies.py
    - stockvaluefinder/stockvaluefinder/main.py

key-decisions:
  - "UserRepository does NOT extend BaseRepository -- uses direct SQLAlchemy queries with UserDB ORM objects"
  - "Generic 'Invalid email or password' error prevents user enumeration on login (T-13-03-01, T-13-03-04)"
  - "Login uses HTTPException 403 for disabled users to distinguish from auth failures"
  - "Refresh endpoint re-fetches role from DB rather than trusting stale token payload"
  - "get_current_user uses lazy import for pyjwt and UserDB to avoid circular import at module level"

patterns-established:
  - "Auth route pattern: register/login/refresh/logout at /api/v1/auth prefix"
  - "FastAPI Bearer dependency: HTTPBearer + validate_access_token + DB user lookup"
  - "First-user-admin bootstrap: count_users() == 0 triggers admin role assignment"
  - "Generic auth errors: same message for wrong email and wrong password to prevent enumeration"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, AUTH-04, RBAC-02, RBAC-05, ADMN-06, ADMN-07, PROT-04]

# Metrics
duration: 5min
completed: 2026-05-10
---

# Phase 13 Plan 03: Auth Routes + UserRepository + Auth Middleware Summary

**Auth routes (register, login, refresh, logout) with UserRepository, JWT bearer middleware dependencies, and first-user-becomes-admin bootstrap**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-10T14:45:54Z
- **Completed:** 2026-05-10T14:51:12Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- UserRepository with 6 methods: get_by_id, get_by_email, create, count_users, update_role, set_active
- 4 auth endpoints: register, login, refresh, logout at /api/v1/auth
- get_current_user FastAPI dependency: JWT validation + DB user lookup + active check
- require_admin FastAPI dependency: admin role enforcement layer
- First-user-becomes-admin bootstrap via count_users() check
- Generic error messages on login to prevent user enumeration

## Task Commits

Each task was committed atomically:

1. **Task 1: Create UserRepository and auth middleware dependencies** - `d912554` (feat)
2. **Task 2: Create auth routes and register in main.py** - `de541c2` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/repositories/user_repo.py` - UserRepository with auth-specific queries (get_by_email, count_users, update_role, set_active)
- `stockvaluefinder/stockvaluefinder/api/auth_routes.py` - 4 auth endpoints with register, login, refresh, logout
- `stockvaluefinder/stockvaluefinder/api/dependencies.py` - Added get_current_user and require_admin FastAPI dependencies with HTTPBearer scheme
- `stockvaluefinder/stockvaluefinder/main.py` - Registered auth_router before _rebuild_forward_refs()

## Decisions Made
- UserRepository uses direct UserDB objects instead of Pydantic Create schemas (unlike RiskScoreRepository pattern), because auth routes create UserDB directly with hashed passwords
- Generic "Invalid email or password" error on login prevents user enumeration (threat model T-13-03-01, T-13-03-04)
- Login endpoint raises HTTPException 403 for disabled users (distinguishable from 401 auth failures per ADMN-06)
- Refresh endpoint re-fetches role from DB on every refresh to avoid stale role in token
- get_current_user and require_admin use lazy imports for pyjwt/UserDB to avoid circular import issues at module level

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed login refresh_token using undefined `role` instead of `user.role`**
- **Found during:** Task 2 (auth routes implementation)
- **Issue:** Plan code had `refresh_token = jwt_service.create_refresh_token(user_id_str, role)` where `role` is undefined in the login function scope
- **Fix:** Changed to `user.role` to use the actual user's role from the DB lookup
- **Files modified:** stockvaluefinder/stockvaluefinder/api/auth_routes.py
- **Verification:** Python syntax check passed, ruff check passed
- **Committed in:** de541c2 (Task 2 commit)

**2. [Rule 1 - Bug] Removed unused UserResponse import from auth_routes.py**
- **Found during:** Task 2 (ruff lint check)
- **Issue:** Plan code imported UserResponse but no endpoint returns it
- **Fix:** Removed unused import to pass ruff F401 check
- **Files modified:** stockvaluefinder/stockvaluefinder/api/auth_routes.py
- **Verification:** ruff check passed after fix
- **Committed in:** de541c2 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness and lint compliance. No scope creep.

## Issues Encountered
- Import verification could not run end-to-end due to DATABASE_URL environment variable requirement in db/base.py (pre-existing). Verified via Python AST parsing and ruff lint instead.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Auth routes ready for 13-04 (admin user management endpoints)
- get_current_user and require_admin dependencies ready for protecting any route
- UserRepository ready for admin operations (update_role, set_active)

## Self-Check: PASSED

- FOUND: stockvaluefinder/stockvaluefinder/repositories/user_repo.py
- FOUND: stockvaluefinder/stockvaluefinder/api/auth_routes.py
- FOUND: stockvaluefinder/stockvaluefinder/api/dependencies.py
- FOUND: stockvaluefinder/stockvaluefinder/main.py
- FOUND: d912554 (Task 1 commit)
- FOUND: de541c2 (Task 2 commit)

---
*Phase: 13-auth-core-jwt*
*Completed: 2026-05-10*
