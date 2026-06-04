---
phase: 25-data-foundation
plan: 01
subsystem: database
tags: [sqlalchemy, pydantic, alembic, postgresql, frozen-dataclass, uuid, jsonb]

# Dependency graph
requires:
  - phase: prior-phases
    provides: "Existing ORM model patterns (AlphaScoreDB, PipelineTaskDB), BaseRepository, frozen config pattern (PipelineConfig)"
provides:
  - "MarketScannerConfig frozen dataclass with all screening thresholds (SCR-04)"
  - "ScanStatus/ScanType enums for scan lifecycle"
  - "4 Pydantic model sets (Create/Update/Result) for scanner domain"
  - "IndexConstituentDB ORM model with effective_date/removed_date history tracking (IDX-01, IDX-02)"
  - "MarketScanRunDB/CandidateDB/RuleDB ORM models for scan persistence (EXE-04)"
  - "Alembic migration 020 creating 4 scanner tables with indexes"
  - "83 unit tests covering all validation and model structure"
affects: [25-02-repositories, 26-screening-engine, 27-scanner-orchestration, 28-scanner-api]

# Tech tracking
tech-stack:
  added: []
  patterns: [frozen-dataclass-config, pydantic-create-update-result-layering, orm-uuid-pk-jsonb, alembic-multi-table-migration]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/market_scanner/__init__.py
    - stockvaluefinder/stockvaluefinder/market_scanner/config.py
    - stockvaluefinder/stockvaluefinder/models/market_scanner.py
    - stockvaluefinder/stockvaluefinder/db/models/index_constituent.py
    - stockvaluefinder/stockvaluefinder/db/models/market_scan.py
    - stockvaluefinder/alembic/versions/020_market_scanner_tables.py
    - stockvaluefinder/tests/unit/test_market_scanner/__init__.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_config.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_models.py
    - stockvaluefinder/tests/unit/test_market_scanner/test_orm.py
  modified:
    - stockvaluefinder/stockvaluefinder/models/enums.py
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py

key-decisions:
  - "No FK from index_constituents.ticker to stocks.ticker -- sync may run before stock records exist"
  - "Combined TDD RED+GREEN into single commits due to pre-commit mypy hook requiring type-complete code"
  - "Used class Config for json_schema_extra (matching alpha.py pattern) despite PydanticDeprecatedSince20 warning"

patterns-established:
  - "MarketScannerConfig: frozen dataclass with __post_init__ threshold validation, tuple for sequence fields"
  - "Scanner Pydantic models: Create/Update/Result layering with frozen Result models"
  - "ORM models: market_scanner package for config, separate db model files for ORM, enums in models/enums.py"

requirements-completed: [SCR-04, EXE-04, IDX-01, IDX-02]

# Metrics
duration: 10min
completed: 2026-06-04
---

# Phase 25 Plan 01: Data Foundation Summary

**Frozen MarketScannerConfig with 10 validated thresholds, 4 ORM models (IndexConstituent, ScanRun, ScanCandidate, ScanRule), 10 Pydantic domain models, Alembic migration 020, and 83 passing tests**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-04T04:49:05Z
- **Completed:** 2026-06-04T04:59:49Z
- **Tasks:** 2
- **Files modified:** 12 (10 created, 2 modified)

## Accomplishments
- MarketScannerConfig frozen dataclass with __post_init__ validation for all screening thresholds (index_codes, daily/weekly_top_n, min_margin_of_safety, min_composite_score, deep_analysis_concurrency)
- 4 ORM models (IndexConstituentDB, MarketScanRunDB, MarketScanCandidateDB, MarketScanRuleDB) with UUID PKs, JSONB fields, timezone-aware timestamps, and proper FK/index/constraint definitions
- 10 Pydantic models covering Create/Update/Result for runs, constituents, candidates, and rules with frozen Result models
- Alembic migration 020 creating all 4 tables in correct FK dependency order with 6 indexes
- 83 unit tests with comprehensive coverage of config validation, enum values, model structure, and __init__ exports

## Task Commits

Each task was committed atomically:

1. **Task 1: MarketScannerConfig, enums, and Pydantic models** - `cb344e8` (feat)
2. **Task 2: ORM models, migration, and __init__ registration** - `b2b5f53` (feat)

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/market_scanner/__init__.py` - Scanner package init
- `stockvaluefinder/stockvaluefinder/market_scanner/config.py` - MarketScannerConfig frozen dataclass with threshold validation
- `stockvaluefinder/stockvaluefinder/models/market_scanner.py` - 10 Pydantic models for scanner domain
- `stockvaluefinder/stockvaluefinder/models/enums.py` - Added ScanStatus and ScanType enums
- `stockvaluefinder/stockvaluefinder/db/models/index_constituent.py` - IndexConstituentDB ORM model
- `stockvaluefinder/stockvaluefinder/db/models/market_scan.py` - MarketScanRunDB, CandidateDB, RuleDB ORM models
- `stockvaluefinder/stockvaluefinder/db/models/__init__.py` - Added 4 new model exports
- `stockvaluefinder/alembic/versions/020_market_scanner_tables.py` - Migration creating 4 tables
- `stockvaluefinder/tests/unit/test_market_scanner/__init__.py` - Test package init
- `stockvaluefinder/tests/unit/test_market_scanner/test_config.py` - 16 config validation tests
- `stockvaluefinder/tests/unit/test_market_scanner/test_models.py` - 27 Pydantic model tests
- `stockvaluefinder/tests/unit/test_market_scanner/test_orm.py` - 40 ORM structure and export tests

## Decisions Made
- **No FK from index_constituents.ticker to stocks.ticker**: Constituent sync may run before stock records exist in the database. The FK would cause constraint violations during sync. The research confirmed this design choice.
- **Combined TDD RED+GREEN commits**: Pre-commit mypy hook requires type-complete code, making separate RED commits (with failing imports) impossible. Both test and implementation are committed together.
- **Kept `class Config` for json_schema_extra**: Matches the existing alpha.py pattern used throughout the codebase, even though PydanticDeprecatedSince20 warns about it. This is a pre-existing project-wide pattern, not introduced by this plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed unused `postgresql` import in migration**
- **Found during:** Task 2 (migration creation)
- **Issue:** Ruff flagged `from sqlalchemy.dialects import postgresql` as unused because migration uses `sa.dialects.postgresql.UUID` directly
- **Fix:** Removed the unused import
- **Files modified:** alembic/versions/020_market_scanner_tables.py
- **Verification:** `ruff check` passes
- **Committed in:** b2b5f53 (Task 2 commit)

**2. [Rule 3 - Blocking] Removed unused `pytest` import in ORM tests**
- **Found during:** Task 2 (pre-commit hook)
- **Issue:** Ruff flagged `import pytest` as unused in test_orm.py (tests use assert, not pytest.raises)
- **Fix:** Removed the unused import
- **Files modified:** tests/unit/test_market_scanner/test_orm.py
- **Verification:** `ruff check` passes
- **Committed in:** b2b5f53 (Task 2 commit)

**3. [Rule 3 - Blocking] Simplified status index test for mypy compatibility**
- **Found during:** Task 2 (pre-commit hook)
- **Issue:** mypy error on `MarketScanRunDB.__table__.indexes` -- FromClause has no `indexes` attribute in mypy types
- **Fix:** Simplified test to check `status_col.index is True` directly instead of iterating table indexes
- **Files modified:** tests/unit/test_market_scanner/test_orm.py
- **Verification:** mypy passes, test passes
- **Committed in:** b2b5f53 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking issues)
**Impact on plan:** All auto-fixes were lint/type compatibility adjustments. No scope creep.

## Issues Encountered
- Pre-commit mypy hook prevents separate TDD RED commits because it validates type completeness. Combined RED+GREEN into single commits as a workaround.

## TDD Gate Compliance

**Note:** This plan has `type: tdd` in frontmatter, requiring RED/GREEN/REFACTOR gate commits. Due to the pre-commit mypy hook requiring type-complete code, separate RED commits (with failing imports) are not possible. Both test and implementation are committed together in a single GREEN commit per task.

- RED gate: Tests were written before implementation and verified to fail due to missing imports
- GREEN gate: Implementation written to pass all tests, verified with 83 passing tests
- REFACTOR gate: Code was formatted by pre-commit hooks (ruff format); no additional refactoring needed

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Data foundation complete: 4 ORM models, Pydantic models, config, and migration ready for Plan 02 (repositories)
- Plan 02 will build IndexConstituentRepository, MarketScanRunRepository, MarketScanCandidateRepository, and MarketScanRuleRepository extending BaseRepository
- Migration 020 ready to apply to database when PostgreSQL is available

---
*Phase: 25-data-foundation*
*Completed: 2026-06-04*
