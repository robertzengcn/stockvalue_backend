---
phase: 05-pipeline-foundation
plan: 01
subsystem: infra
tags: [pipeline, state-machine, postgresql, sqlalchemy, alembic, pydantic, frozen-dataclass]

# Dependency graph
requires:
  - phase: 04-rag-pipeline
    provides: Existing ORM models, Alembic migrations 001-008, config.py pattern, errors.py pattern
provides:
  - PipelineConfig frozen dataclass with validation
  - PipelineState StrEnum (6 states) with VALID_TRANSITIONS map
  - StateTransitionError extending StockValueFinderError
  - PipelineTaskCreate, PipelineDocumentCreate, HealthStatus Pydantic models
  - PipelineTaskDB and PipelineDocumentDB ORM models
  - Alembic migration 009 for pipeline_tasks and pipeline_documents tables
affects: [05-02, 05-03, 06-watcher, 07-report-processing, 08-task-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Frozen dataclass config with __post_init__ validation for pipeline settings"
    - "Custom StrEnum state machine with frozenset transition map"
    - "Deduplication via business_key unique constraint"

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/pipeline/__init__.py
    - stockvaluefinder/stockvaluefinder/pipeline/config.py
    - stockvaluefinder/stockvaluefinder/pipeline/state.py
    - stockvaluefinder/stockvaluefinder/pipeline/models.py
    - stockvaluefinder/stockvaluefinder/db/models/pipeline_task.py
    - stockvaluefinder/stockvaluefinder/db/models/pipeline_document.py
    - stockvaluefinder/alembic/versions/009_pipeline_tables.py
    - stockvaluefinder/tests/unit/test_pipeline/test_config.py
    - stockvaluefinder/tests/unit/test_pipeline/test_state.py
    - stockvaluefinder/tests/unit/test_pipeline/test_models.py
    - stockvaluefinder/tests/unit/test_pipeline/test_orm_models.py
  modified:
    - stockvaluefinder/stockvaluefinder/utils/errors.py
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py

key-decisions:
  - "Ticker regex allows 4-6 digits to support HK tickers (0700.HK has 4 digits, SH/SZ have 6)"
  - "StateTransitionError uses simple string args to avoid circular imports"

patterns-established:
  - "PipelineConfig frozen dataclass follows ValuationConfig/RiskConfig/YieldConfig pattern"
  - "PipelineState StrEnum follows RiskLevel/ValuationLevel enum pattern"
  - "PipelineTaskCreate/DocumentCreate follow Pydantic BaseModel pattern with json_schema_extra examples"

requirements-completed: [CONF-01, CONF-02, PIPE-04]

# Metrics
duration: 8min
completed: 2026-05-01
---

# Phase 5 Plan 01: Pipeline Foundation Types Summary

**Frozen PipelineConfig, custom 6-state StrEnum state machine with validation, Pydantic domain models, ORM models for pipeline_tasks and pipeline_documents, and Alembic migration 009**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-01T03:57:46Z
- **Completed:** 2026-05-01T04:06:34Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- PipelineConfig frozen dataclass with 9 configurable fields and __post_init__ validation
- PipelineState StrEnum with 6 states and VALID_TRANSITIONS enforcing linear progression with FAILED escape hatch
- StateTransitionError with descriptive message and structured details dict
- Pydantic models (PipelineTaskCreate, PipelineDocumentCreate, HealthStatus) with input validation
- PipelineTaskDB and PipelineDocumentDB SQLAlchemy ORM models with FKs, indexes, and defaults
- Alembic migration 009 creating both tables with correct dependency order
- 94 unit tests covering all pipeline types (100% coverage on pipeline module)

## Task Commits

Each task was committed atomically:

1. **Task 1: PipelineConfig, PipelineState, StateTransitionError, and Pydantic domain models** - `3861d5a` (feat)
2. **Task 2: PipelineTaskDB and PipelineDocumentDB ORM models with migration 009** - `81b9d32` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/pipeline/__init__.py` - Module init with __all__ exports
- `stockvaluefinder/stockvaluefinder/pipeline/config.py` - PipelineConfig frozen dataclass with validation
- `stockvaluefinder/stockvaluefinder/pipeline/state.py` - PipelineState enum, VALID_TRANSITIONS, validate_transition
- `stockvaluefinder/stockvaluefinder/pipeline/models.py` - PipelineTaskCreate, PipelineDocumentCreate, HealthStatus Pydantic models
- `stockvaluefinder/stockvaluefinder/db/models/pipeline_task.py` - PipelineTaskDB ORM model (12 columns)
- `stockvaluefinder/stockvaluefinder/db/models/pipeline_document.py` - PipelineDocumentDB ORM model (8 columns)
- `stockvaluefinder/alembic/versions/009_pipeline_tables.py` - Migration creating both tables
- `stockvaluefinder/stockvaluefinder/utils/errors.py` - Added StateTransitionError class
- `stockvaluefinder/stockvaluefinder/db/models/__init__.py` - Registered new ORM models
- `stockvaluefinder/tests/unit/test_pipeline/test_config.py` - 17 tests for PipelineConfig
- `stockvaluefinder/tests/unit/test_pipeline/test_state.py` - 23 tests for state machine
- `stockvaluefinder/tests/unit/test_pipeline/test_models.py` - 26 tests for Pydantic models
- `stockvaluefinder/tests/unit/test_pipeline/test_orm_models.py` - 28 tests for ORM models

## Decisions Made
- **Ticker regex allows 4-6 digits:** The plan specified `^\d{6}\.(SH|SZ|HK)$` but HK tickers like 0700.HK have only 4 digits. Changed to `^\d{4,6}\.(SH|SZ|HK)$` to support all valid formats.
- **StateTransitionError uses simple string args:** Instead of forward-referencing PipelineState in the error class, the constructor accepts string values directly, keeping the error module independent of the pipeline module.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] HK ticker regex too strict**
- **Found during:** Task 1 (test_valid_hk_ticker failed)
- **Issue:** Plan specified `^\d{6}\.(SH|SZ|HK)$` but HK tickers can have 4-5 digits (e.g., 0700.HK, 0941.HK)
- **Fix:** Changed pattern to `^\d{4,6}\.(SH|SZ|HK)$`
- **Files modified:** stockvaluefinder/stockvaluefinder/pipeline/models.py
- **Verification:** test_valid_hk_ticker passes with 4-digit HK ticker
- **Committed in:** 3861d5a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor regex adjustment for correctness. No scope creep.

## Issues Encountered
- Pre-commit hooks required `# type: ignore[call-arg]` annotations on intentional ValidationError tests where required Pydantic fields are omitted
- SQLAlchemy `__new__` instantiation does not work with mapped_column attributes for repr testing; switched to inspect-based test

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All pipeline types and database schema are ready for Plan 05-02 (arq worker, repository, FastAPI integration)
- StateTransitionError is available for the atomic state transition repository methods
- HealthStatus model is ready for the health-check endpoint in Plan 05-03

---
*Phase: 05-pipeline-foundation*
*Completed: 2026-05-01*
