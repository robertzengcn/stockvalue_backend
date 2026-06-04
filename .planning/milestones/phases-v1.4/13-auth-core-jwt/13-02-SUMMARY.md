---
phase: 13-auth-core-jwt
plan: 02
subsystem: auth
tags: [jwt, bcrypt, authentication, token-management, password-hashing]

# Dependency graph
requires: []
provides:
  - JWTService with access/refresh token creation and validation
  - Token type discrimination (access vs refresh)
  - bcrypt password hashing and verification
  - AuthConfig frozen dataclass for JWT settings
affects: [13-03, 13-04, auth-routes]

# Tech tracking
tech-stack:
  added: [PyJWT 2.12+, bcrypt 5.0+]
  patterns: [frozen dataclass config, module-level singleton, token type field discrimination]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/services/jwt_service.py
  modified:
    - stockvaluefinder/stockvaluefinder/config.py
    - stockvaluefinder/pyproject.toml
    - stockvaluefinder/uv.lock

key-decisions:
  - "Access tokens include sub (user_id), role, type=access, iat, exp with 15-minute expiry"
  - "Refresh tokens include sub (user_id), role, type=refresh, iat, exp with 7-day expiry"
  - "Token type field prevents token confusion attacks via validate_access_token/validate_refresh_token"
  - "Password methods are static (no instance state needed) but use auth_config.BCRYPT_ROUNDS"
  - "AuthConfig reads JWT_SECRET from env var with dev-mode default"

patterns-established:
  - "Frozen dataclass config with env var fallback for secrets (AuthConfig pattern)"
  - "Module-level service singleton (jwt_service = JWTService())"
  - "Token type discrimination via payload type field"

requirements-completed: [AUTH-02, AUTH-03, AUTH-05]

# Metrics
duration: 4min
completed: 2026-05-10
---

# Phase 13 Plan 02: JWT Service Summary

**JWT service with access/refresh token generation, type-discriminated validation, and bcrypt password hashing via AuthConfig dataclass**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-10T14:34:44Z
- **Completed:** 2026-05-10T14:39:01Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- AuthConfig frozen dataclass added to config.py with JWT_SECRET, ACCESS_TOKEN_EXPIRE_MINUTES=15, REFRESH_TOKEN_EXPIRE_DAYS=7, BCRYPT_ROUNDS=12
- JWTService class with full token lifecycle: create, decode, validate (with type discrimination)
- bcrypt password hashing (hash_password, verify_password) with 12 rounds
- PyJWT 2.12+ and bcrypt 5.0+ added as project dependencies

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AuthConfig to config.py** - `7eba9c0` (feat)
2. **Task 2: Create JWT service with token management and bcrypt hashing** - `7f6041e` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/config.py` - Added AuthConfig frozen dataclass, auth field in AppConfig, auth_config singleton
- `stockvaluefinder/stockvaluefinder/services/jwt_service.py` - JWTService class with token management and password hashing
- `stockvaluefinder/pyproject.toml` - Added PyJWT and bcrypt dependencies
- `stockvaluefinder/uv.lock` - Updated lockfile

## Decisions Made
- Access tokens carry sub (user_id), role, type="access", iat, exp; refresh tokens carry sub, role, type="refresh", iat, exp
- Token type field in payload prevents token confusion attacks; validate_access_token rejects refresh tokens and vice versa
- Password hashing methods are static since they need no instance state, but reference auth_config.BCRYPT_ROUNDS
- JWT_SECRET defaults to "dev-secret-change-in-production" for dev, must be set via env var in production

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. For production deployment, set the JWT_SECRET environment variable to a cryptographically secure value of at least 32 bytes.

## Next Phase Readiness
- JWT service ready for consumption by auth routes (plan 13-03) for login/register endpoints
- AuthConfig integrated into AppConfig singleton chain
- Token type discrimination ready for middleware-based route protection (plan 13-04)

## Self-Check: PASSED

- FOUND: stockvaluefinder/stockvaluefinder/services/jwt_service.py
- FOUND: stockvaluefinder/stockvaluefinder/config.py
- FOUND: .planning/phases/13-auth-core-jwt/13-02-SUMMARY.md
- FOUND: 7eba9c0 (Task 1 commit)
- FOUND: 7f6041e (Task 2 commit)

---
*Phase: 13-auth-core-jwt*
*Completed: 2026-05-10*
