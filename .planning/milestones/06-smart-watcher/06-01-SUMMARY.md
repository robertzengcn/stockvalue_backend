---
phase: 06-smart-watcher
plan: 01
subsystem: pipeline/watcher
tags: [pipeline, config, pydantic, sqlalchemy, alembic, frozen-dataclass, orm, migration]

# Dependency graph
requires:
  - phase: 05-pipeline-foundation
    provides: PipelineConfig, PipelineTaskCreate, PipelineTaskDB, migration 009, existing patterns
provides:
  - PipelineConfig with season-aware polling fields (high_season_months, high_season_cron, off_season_cron)
  - WatchlistItemCreate, WatchlistItemResponse Pydantic models for watchlist API
  - WatcherStateUpdate Pydantic model for watcher state tracking
  - PendingDisclosureCreate Pydantic model for disclosure staging
  - WatchlistDB ORM model for watchlist table
  - WatcherStateDB ORM model for watcher_state table
  - PendingDisclosureDB ORM model for pending_disclosures staging table
  - Alembic migration 010 for all three new tables
affects: [06-02, 06-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Literal type for constrained string fields (report_type, source) per Pydantic best practice"
    - "frozenset[int] for high_season_months in frozen dataclass"

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/db/models/watchlist.py
    - stockvaluefinder/stockvaluefinder/db/models/watcher_state.py
    - stockvaluefinder/stockvaluefinder/db/models/pending_disclosure.py
    - stockvaluefinder/alembic/versions/010_watcher_tables.py
    - stockvaluefinder/tests/unit/test_pipeline/test_watcher_orm.py
  modified:
    - stockvaluefinder/stockvaluefinder/pipeline/config.py
    - stockvaluefinder/stockvaluefinder/pipeline/models.py
    - stockvaluefinder/stockvaluefinder/pipeline/__init__.py
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py
    - stockvaluefinder/tests/unit/test_pipeline/test_config.py
    - stockvaluefinder/tests/unit/test_pipeline/test_models.py

key-decisions:
  - "report_type uses Literal['annual', 'semi_annual', 'q1', 'q3'] for strict validation instead of plain str"
  - "source uses Literal['akshare', 'cninfo'] for strict validation per D-01"
  - "high_season_months stored as frozenset[int] in PipelineConfig for immutability and O(1) membership testing"

patterns-established:
  - "Literal-based string enums for constrained Pydantic fields instead of StrEnum"
  - "UUID poll_id on pending_disclosures for grouping disclosures from same poll cycle"

requirements-completed: [WATCH-03, WATCH-04]

# Metrics
duration: 11min
completed: 2026-05-01
---

# Phase 6 Plan 01: Watcher Data Layer Summary

**Extended PipelineConfig with season-aware polling fields, created 4 new Pydantic models, 3 new ORM models, and Alembic migration 010 for watchlist, watcher_state, and pending_disclosures tables**

## Performance

- **Duration:** 11 min
- **Started:** 2026-05-01T15:14:05Z
- **Completed:** 2026-05-01T15:25:03Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- PipelineConfig extended with high_season_months (frozenset), high_season_cron, and off_season_cron with full validation
- WatchlistItemCreate and WatchlistItemResponse Pydantic models for watchlist API endpoints
- WatcherStateUpdate Pydantic model for watcher state observability
- PendingDisclosureCreate Pydantic model with Literal-based report_type and source validation
- WatchlistDB ORM model with ticker PK, name, added_at, is_active columns
- WatcherStateDB ORM model with watcher_id PK, poll counters, and success flags
- PendingDisclosureDB ORM model with UUID PK, poll_id index, processed index, and JSONB source_raw
- Alembic migration 010 creating all 3 tables with correct dependency chain
- 144 new unit tests across config, models, and ORM test files (all passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend PipelineConfig and add new Pydantic models** - `bf2f65a` (feat)
2. **Task 2: ORM models and Alembic migration 010** - `7f27d69` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/pipeline/config.py` - Added 3 new fields with __post_init__ validation
- `stockvaluefinder/stockvaluefinder/pipeline/models.py` - Added 4 new Pydantic models (WatchlistItemCreate, WatchlistItemResponse, WatcherStateUpdate, PendingDisclosureCreate)
- `stockvaluefinder/stockvaluefinder/pipeline/__init__.py` - Updated exports for all new models
- `stockvaluefinder/stockvaluefinder/db/models/watchlist.py` - New WatchlistDB ORM model
- `stockvaluefinder/stockvaluefinder/db/models/watcher_state.py` - New WatcherStateDB ORM model
- `stockvaluefinder/stockvaluefinder/db/models/pending_disclosure.py` - New PendingDisclosureDB ORM model
- `stockvaluefinder/stockvaluefinder/db/models/__init__.py` - Registered 3 new ORM models
- `stockvaluefinder/alembic/versions/010_watcher_tables.py` - Migration creating watchlist, watcher_state, pending_disclosures
- `stockvaluefinder/tests/unit/test_pipeline/test_config.py` - Extended with 14 new season-aware config tests
- `stockvaluefinder/tests/unit/test_pipeline/test_models.py` - Extended with 35 new model validation tests
- `stockvaluefinder/tests/unit/test_pipeline/test_watcher_orm.py` - New file with 69 ORM model and migration tests

## Decisions Made
- **report_type uses Literal type:** Instead of a plain str field, report_type uses `Literal["annual", "semi_annual", "q1", "q3"]` for strict compile-time and runtime validation. This prevents invalid report types from being stored.
- **source uses Literal type:** Similar to report_type, the source field uses `Literal["akshare", "cninfo"]` per D-01 (two known sources).
- **frozenset for high_season_months:** Using frozenset[int] provides immutability (consistent with frozen dataclass) and O(1) membership testing for the month-check in the cron function.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Validation] PendingDisclosureCreate.report_type needed Literal validation**
- **Found during:** Task 1 GREEN phase (test_invalid_report_type_rejected failed)
- **Issue:** Plan specified `report_type: str = Field(...)` but test expected validation against known types. The threat model T-06-02 requires ticker regex validation, and consistent input validation demands report_type be constrained too.
- **Fix:** Changed to `Literal["annual", "semi_annual", "q1", "q3"]` matching D-03 (all four report types).
- **Files modified:** stockvaluefinder/stockvaluefinder/pipeline/models.py
- **Committed in:** bf2f65a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing validation)
**Impact on plan:** Strengthened input validation. No scope creep.

## Issues Encountered
- Pre-commit mypy hook required `# type: ignore[attr-defined]` annotations on SQLAlchemy table introspection calls (e.g., `__table__.primary_key.columns`, `col.type.length`). Same pattern as existing test_orm_models.py.
- Unused importlib import caught by ruff after migration test refactoring from import-based to file-read approach.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All data types ready for Plan 06-02 (WatcherService with poll_disclosures, process_disclosures)
- All data types ready for Plan 06-03 (Watchlist API endpoints)
- WatchlistDB available for WatchlistRepository CRUD
- PendingDisclosureDB available for staging table operations
- WatcherStateDB available for watcher state observability

---

*Phase: 06-smart-watcher*
*Completed: 2026-05-01*

## Self-Check: PASSED

All 12 key files verified present. Both commits (bf2f65a, 7f27d69) verified in git log. 258 pipeline tests passing.
