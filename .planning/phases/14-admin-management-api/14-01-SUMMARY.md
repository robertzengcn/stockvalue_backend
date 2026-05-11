---
phase: 14-admin-management-api
plan: 01
subsystem: admin
tags: [sqlalchemy, pydantic, alembic, soft-delete, pagination, admin-api]

# Dependency graph
requires:
  - phase: 13-01
    provides: "UserDB ORM model with id, email, password_hash, role, is_active, timestamps"
  - phase: 13-03
    provides: "UserRepository with get_by_id, get_by_email, create, count_users, update_role, set_active"
provides:
  - "UserDB.deleted_at column for soft-delete tracking"
  - "Alembic migration 016 adding deleted_at to users table"
  - "UserRepository.list_users(page, limit) with paginated query excluding soft-deleted users"
  - "UserRepository.soft_delete(user_id) setting deleted_at timestamp"
  - "Admin Pydantic schemas: UserListResponse, UserRoleUpdate, UserDetailResponse"
affects: [14-02, 14-03, 14-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [soft-delete-pattern, paginated-user-listing, admin-pydantic-schemas]

key-files:
  created:
    - stockvaluefinder/alembic/versions/016_users_soft_delete.py
  modified:
    - stockvaluefinder/stockvaluefinder/db/models/user.py
    - stockvaluefinder/stockvaluefinder/repositories/user_repo.py
    - stockvaluefinder/stockvaluefinder/models/user.py

key-decisions:
  - "list_users excludes soft-deleted users via deleted_at IS NULL filter in both count and list queries"
  - "soft_delete checks deleted_at IS NULL to prevent double-delete and returns None if already deleted"
  - "Pagination params clamped: page min 1, limit range [1, 100] for safety"
  - "UserDetailResponse includes deleted_at field for admin visibility into soft-deleted state"
  - "Imported PaginationMeta from api.py for UserListResponse pagination metadata"

patterns-established:
  - "Soft-delete pattern: nullable deleted_at column + IS NULL filter in queries"
  - "Paginated listing: count query + offset/limit list query with parameter clamping"

requirements-completed: [ADMN-01, ADMN-04]

# Metrics
duration: 3min
completed: 2026-05-11
---

# Phase 14 Plan 01: UserDB Soft-Delete + UserRepository Enhancements + Admin Schemas Summary

**Soft-delete column on UserDB with Alembic migration 016, paginated list_users and soft_delete repository methods, and admin Pydantic response schemas**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-10T21:57:21Z
- **Completed:** 2026-05-10T22:00:33Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added nullable `deleted_at` column to UserDB ORM model for soft-delete tracking
- Created Alembic migration 016 adding deleted_at column with upgrade/downgrade support
- Added `list_users(page, limit)` to UserRepository with pagination and soft-delete exclusion filter
- Added `soft_delete(user_id)` to UserRepository setting deleted_at timestamp
- Created admin Pydantic schemas: UserListResponse, UserRoleUpdate, UserDetailResponse

## Task Commits

Each task was committed atomically:

1. **Task 1: Add deleted_at column to UserDB + Alembic migration 016** - `b3b315e` (feat)
2. **Task 2: Add list_users/soft_delete to UserRepository + admin Pydantic schemas** - `609303f` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/db/models/user.py` - Added `deleted_at: Mapped[datetime | None]` column for soft-delete tracking
- `stockvaluefinder/alembic/versions/016_users_soft_delete.py` - Alembic migration adding deleted_at column with add_column/drop_column
- `stockvaluefinder/stockvaluefinder/repositories/user_repo.py` - Added list_users (paginated) and soft_delete methods with deleted_at IS NULL filters
- `stockvaluefinder/stockvaluefinder/models/user.py` - Added UserListResponse, UserRoleUpdate, UserDetailResponse admin schemas

## Decisions Made
- list_users excludes soft-deleted users via `deleted_at IS NULL` in both count and list queries (threat model T-14-01-01 mitigation)
- soft_delete checks `deleted_at IS NULL` before setting timestamp to prevent double-delete and return None for already-deleted users
- Pagination parameters clamped to safe ranges (page min 1, limit 1-100) to prevent abuse
- UserDetailResponse includes `deleted_at: datetime | None` so admin UI can show deletion status
- Imported PaginationMeta from api.py to reuse existing pagination model rather than duplicating fields

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- UserDB with soft-delete column ready for 14-02 (admin route handlers)
- UserRepository with list_users and soft_delete ready for admin endpoints
- Admin Pydantic schemas ready for request/response serialization in admin routes
- Alembic migration 016 ready to apply alongside existing migrations

---
*Phase: 14-admin-management-api*
*Completed: 2026-05-11*

## Self-Check: PASSED

- FOUND: stockvaluefinder/stockvaluefinder/db/models/user.py
- FOUND: stockvaluefinder/alembic/versions/016_users_soft_delete.py
- FOUND: stockvaluefinder/stockvaluefinder/repositories/user_repo.py
- FOUND: stockvaluefinder/stockvaluefinder/models/user.py
- FOUND: b3b315e (Task 1 commit)
- FOUND: 609303f (Task 2 commit)
