---
phase: 14-admin-management-api
plan: 02
subsystem: admin
tags: [fastapi, admin-routes, rbac, user-management, require-admin]

# Dependency graph
requires:
  - phase: 13-03
    provides: "require_admin FastAPI dependency for admin role enforcement, get_db for session injection"
  - phase: 14-01
    provides: "UserRepository.list_users/soft_delete, UserListResponse/UserDetailResponse/UserRoleUpdate Pydantic schemas, deleted_at column"
provides:
  - "GET /api/v1/admin/users -- paginated user listing (ADMN-01)"
  - "GET /api/v1/admin/users/{user_id} -- single user detail (ADMN-02)"
  - "PATCH /api/v1/admin/users/{user_id}/status -- enable/disable user (ADMN-03)"
  - "PATCH /api/v1/admin/users/{user_id}/role -- change user role (ADMN-05, RBAC-03)"
  - "DELETE /api/v1/admin/users/{user_id} -- soft-delete user (ADMN-04)"
  - "Self-demotion and self-delete prevention guards"
affects: [14-03, 14-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [admin-route-pattern, self-action-prevention-guard]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/api/admin_routes.py
  modified:
    - stockvaluefinder/stockvaluefinder/main.py

key-decisions:
  - "All admin endpoints use Depends(require_admin) for 403 enforcement on non-admin access (T-14-02-01)"
  - "Self-role-change prevention: admin cannot demote themselves via user_id comparison with admin dict"
  - "Self-delete prevention: admin cannot delete their own account via user_id comparison"
  - "delete_user fetches user data before soft_delete to build response from pre-deletion state"
  - "UserStatusUpdate model defined locally in admin_routes.py (not in models/user.py) for endpoint-specific schema"

patterns-established:
  - "Admin route pattern: /api/v1/admin prefix with require_admin dependency on every endpoint"
  - "Self-action guard: compare str(user_id) == admin.get('user_id') to prevent admins from mutating themselves"

requirements-completed: [RBAC-03, RBAC-04, ADMN-01, ADMN-02, ADMN-03, ADMN-04, ADMN-05]

# Metrics
duration: 8min
completed: 2026-05-11
---

# Phase 14 Plan 02: Admin Routes with require_admin Summary

**5 admin user management endpoints (list, get, status toggle, role change, soft-delete) all guarded by require_admin dependency with self-action prevention**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-10T22:02:34Z
- **Completed:** 2026-05-10T22:10:39Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created admin_routes.py with 5 REST endpoints for user management
- All endpoints enforce admin-only access via Depends(require_admin) -- returns 403 for non-admin
- Self-demotion and self-delete guards prevent admins from locking themselves out
- Registered admin router in main.py before _rebuild_forward_refs()
- UserStatusUpdate Pydantic model for enable/disable request body

## Task Commits

Each task was committed atomically:

1. **Task 1: Create admin routes with 5 endpoints** - `f94edff` (feat)
2. **Task 2: Register admin router in main.py** - `c4f7804` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/api/admin_routes.py` - 5 admin endpoints with require_admin guards, UserStatusUpdate model, self-action prevention
- `stockvaluefinder/stockvaluefinder/main.py` - Added admin_router import and app.include_router(admin_router)

## Decisions Made
- UserStatusUpdate defined locally in admin_routes.py rather than in models/user.py because it is an endpoint-specific request schema not reused elsewhere
- delete_user captures user data before soft_delete call to return pre-deletion state in response (since soft_delete sets deleted_at)
- Self-action checks use str(user_id) == admin.get("user_id") string comparison since admin dict stores user_id as string

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing E402 ruff errors in main.py triggered when ruff format reorganized imports (load_dotenv placement). Resolved by restoring original file and applying only the two required lines (import + include_router).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Admin routes ready for 14-03 (admin route tests)
- All 5 endpoints follow consistent ApiResponse[T] envelope pattern
- require_admin dependency proven working across all endpoints

---
*Phase: 14-admin-management-api*
*Completed: 2026-05-11*

## Self-Check: PASSED

- FOUND: stockvaluefinder/stockvaluefinder/api/admin_routes.py
- FOUND: stockvaluefinder/stockvaluefinder/main.py
- FOUND: f94edff (Task 1 commit)
- FOUND: c4f7804 (Task 2 commit)
