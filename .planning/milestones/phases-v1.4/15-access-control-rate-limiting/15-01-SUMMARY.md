---
phase: 15-access-control-rate-limiting
plan: 01
subsystem: access-control
tags: [orm, pydantic, alembic, fastapi, dependency-injection, access-control]

# Dependency graph
requires:
  - phase: 13-01
    provides: "UserDB ORM model with id, role columns and users table"
  - phase: 13-03
    provides: "get_current_user and require_admin FastAPI dependencies with JWT bearer token validation"
provides:
  - "UserStockAccessDB ORM model with unique (user_id, ticker) constraint"
  - "Pydantic schemas: StockAccessEntry, StockAccessListResponse, StockAccessUpdateRequest, StockAccessAddRequest, StockAccessRemoveRequest"
  - "Alembic migration 017 creating user_stock_access table with FK to users.id"
  - "UserStockAccessRepository with get_accessible_tickers, add_access, remove_access, set_access, get_all_for_user, clear_access"
  - "require_stock_access FastAPI dependency enforcing per-user stock access (admin bypass + default-open + restricted modes)"
affects: [15-03, analysis-routes, admin-stock-access-endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns: [orm-unique-constraint, default-open-access-control, admin-bypass, case-insensitive-ticker-compare]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/db/models/user_stock_access.py
    - stockvaluefinder/stockvaluefinder/models/user_stock_access.py
    - stockvaluefinder/alembic/versions/017_user_stock_access_table.py
    - stockvaluefinder/stockvaluefinder/repositories/user_stock_access_repo.py
    - stockvaluefinder/tests/unit/test_db/__init__.py
    - stockvaluefinder/tests/unit/test_db/test_user_stock_access_model.py
    - stockvaluefinder/tests/unit/test_api/test_stock_access_dependency.py
  modified:
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py
    - stockvaluefinder/stockvaluefinder/api/dependencies.py

key-decisions:
  - "Default-open access model per ACCL-03: users with no entries can access all stocks"
  - "Admin bypass: role check before any DB query to avoid unnecessary I/O"
  - "Case-insensitive ticker comparison in require_stock_access to tolerate input casing"
  - "user_id stored as String matching UserDB.id (UUID-as-string), not native UUID column"
  - "Unique constraint on (user_id, ticker) at DB level to prevent duplicate entries"

patterns-established:
  - "Per-user access control via separate join table with FK to users.id"
  - "Default-open vs. restricted access modes determined by presence of any rows for the user"
  - "Repository pattern: get/add/remove/set/clear surface, IntegrityError caught for idempotent add_access"
  - "Pydantic ticker pattern validation via Field(pattern=r'^\\d{6}\\.(SH|SZ|HK)$')"

requirements-completed: [ACCL-01, ACCL-03, ACCL-04, DB-02]

# Metrics
duration: 6min
completed: 2026-05-11
---

# Phase 15 Plan 01: User Stock Access Control Foundation

**Per-user stock access table, ORM model, Pydantic schemas, Alembic migration 017, repository, and require_stock_access FastAPI dependency.**

> **Note:** This SUMMARY.md was reconstructed on 2026-05-22 during `/gsd-next` prior-phase completeness reconciliation. The original execution completed on 2026-05-11 (commits `5b4385f` RED + `a218a38` GREEN) but the summary file was never written. Content below was reconstructed from the PLAN, git log, and live verification of artifacts and tests.

## Performance

- **Duration:** ~6 min (between commits)
- **RED commit:** 2026-05-10T22:35:25Z (`5b4385f`)
- **GREEN commit:** 2026-05-10T22:41:35Z (`a218a38`)
- **Tasks:** 2
- **Files created/modified:** 9 (7 created + 2 modified)

## Accomplishments
- `UserStockAccessDB` ORM model with `id` (UUID PK), `user_id` (FK -> users.id, indexed), `ticker` (String(12)), `created_at`, plus unique constraint `uq_user_stock_access_user_ticker`
- Pydantic request/response schemas with ticker pattern validation (`^\d{6}\.(SH|SZ|HK)$`)
- Alembic migration 017 (down_revision 016) creating `user_stock_access` table with FK and unique index
- `UserStockAccessRepository` with 6 methods: `get_accessible_tickers`, `add_access`, `remove_access`, `set_access`, `get_all_for_user`, `clear_access`
- `require_stock_access` FastAPI dependency enforcing three access modes:
  - **Admin bypass:** role=="admin" returns immediately, zero DB queries
  - **Default open (ACCL-03):** users with zero entries can access any ticker
  - **Restricted:** users with entries can only access tickers in their list (case-insensitive)
- 35 unit tests across two files (23 model/schema/migration + 12 repository/dependency)

## Task Commits

Each task was committed atomically following the TDD RED/GREEN gate convention:

1. **Task 1: ORM model + Pydantic schemas + Alembic migration 017** -- `5b4385f` (test -> RED gate, all tests intentionally fail until impl)
2. **Task 2: UserStockAccessRepository + require_stock_access dependency** -- `a218a38` (feat -> GREEN gate, all 35 tests pass)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/db/models/user_stock_access.py` -- UserStockAccessDB ORM model (69 LOC)
- `stockvaluefinder/stockvaluefinder/db/models/__init__.py` -- registered UserStockAccessDB in __all__
- `stockvaluefinder/stockvaluefinder/models/user_stock_access.py` -- 5 Pydantic schemas (125 LOC)
- `stockvaluefinder/alembic/versions/017_user_stock_access_table.py` -- migration with FK + unique index (63 LOC)
- `stockvaluefinder/stockvaluefinder/repositories/user_stock_access_repo.py` -- UserStockAccessRepository (154 LOC)
- `stockvaluefinder/stockvaluefinder/api/dependencies.py` -- added require_stock_access + import (+58 LOC)
- `stockvaluefinder/tests/unit/test_db/__init__.py` -- test package init
- `stockvaluefinder/tests/unit/test_db/test_user_stock_access_model.py` -- 23 model/schema/migration tests (207 LOC)
- `stockvaluefinder/tests/unit/test_api/test_stock_access_dependency.py` -- 12 dependency + repository tests (402 LOC)

## Decisions Made
- **Default-open semantics (ACCL-03):** No entries == universal access. Chosen because most users do not need restrictions; admin opts a user *into* a whitelist by adding rows. Easier mental model than "must add a row for every stock."
- **Admin bypass before DB I/O:** Role check happens before constructing the repository, so admin requests never touch the user_stock_access table.
- **String user_id column:** Matches `UserDB.id` storage (UUID-as-string) rather than a native UUID column, avoiding cross-type FK comparison overhead.
- **Case-insensitive ticker comparison:** `ticker.upper()` on both sides of the membership check prevents accidental lockouts from input casing drift.
- **Idempotent add_access:** Catches `IntegrityError` from the unique constraint and returns the existing row, so repeated grants are a no-op rather than a 500.

## Deviations from Plan
None recorded in commit messages. The plan's behavior contracts, file list, and verification all match what shipped.

## Issues Encountered
None known. 35 tests passed at the GREEN commit and still pass on 2026-05-22 verification.

## User Setup Required
- Run `uv run alembic upgrade head` to apply migration 017 against a Postgres database before deploying this plan's code.

## Next Phase Readiness
- `require_stock_access` ready for 15-03 to wire into analysis route handlers
- `UserStockAccessRepository` ready for the admin stock-access management endpoints in 15-03
- Pydantic request/response schemas ready for the admin API surface

## TDD Gate Compliance
- **RED commit:** `5b4385f` (test: failing tests added for model, schemas, migration)
- **GREEN commit:** `a218a38` (feat: implementation + dependency landed, all 35 tests pass)
- Both RED and GREEN gate commits present in git log.

## Self-Check: PASSED (re-verified 2026-05-22)
- FOUND: `stockvaluefinder/stockvaluefinder/db/models/user_stock_access.py`
- FOUND: `stockvaluefinder/stockvaluefinder/models/user_stock_access.py`
- FOUND: `stockvaluefinder/alembic/versions/017_user_stock_access_table.py`
- FOUND: `stockvaluefinder/stockvaluefinder/repositories/user_stock_access_repo.py`
- FOUND: `stockvaluefinder/tests/unit/test_db/test_user_stock_access_model.py`
- FOUND: `stockvaluefinder/tests/unit/test_api/test_stock_access_dependency.py`
- FOUND: `UserStockAccessDB` in `stockvaluefinder/stockvaluefinder/db/models/__init__.py` __all__
- FOUND: `require_stock_access` in `stockvaluefinder/stockvaluefinder/api/dependencies.py` __all__
- FOUND: commits `5b4385f` (test) and `a218a38` (feat)
- VERIFIED: `uv run pytest tests/unit/test_db/test_user_stock_access_model.py tests/unit/test_api/test_stock_access_dependency.py` -> 35 passed in 0.19s (2026-05-22)

---
*Phase: 15-access-control-rate-limiting*
*Completed: 2026-05-11*
*Summary reconstructed: 2026-05-22*
