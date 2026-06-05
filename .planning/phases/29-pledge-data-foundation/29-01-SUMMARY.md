---
phase: 29-pledge-data-foundation
plan: 01
subsystem: models
tags: [pydantic, enums, validators, equity-pledge, ticker-normalization]

# Dependency graph
requires: []
provides:
  - DataFreshness enum (CURRENT/STALE/UNAVAILABLE) for data quality classification
  - EquityPledgeSnapshot frozen model for company-level pledge summary
  - EquityPledgeDetail frozen model for shareholder-level pledge records
  - EquityPledgeDataQuality frozen model for fetch metadata
  - normalize_a_share_ticker utility for AKShare code-to-internal-format translation
affects: [29-pledge-data-foundation]

# Tech tracking
tech-stack:
  added: []
  patterns: [frozen-pydantic-models, ticker-prefix-mapping, data-quality-metadata]

key-files:
  created:
    - stockvaluefinder/stockvaluefinder/models/equity_pledge.py
    - stockvaluefinder/tests/unit/test_models/test_equity_pledge.py
  modified:
    - stockvaluefinder/stockvaluefinder/models/enums.py
    - stockvaluefinder/stockvaluefinder/utils/validators.py
    - stockvaluefinder/tests/unit/test_utils/test_validators.py

key-decisions:
  - "DataFreshness placed in enums.py following existing RiskLevel/Market enum pattern"
  - "BSE codes (8xx/4xx) return None rather than raising to enable graceful filtering"
  - "EquityPledgeSnapshot company_pledge_ratio stored as percentage (35.5 = 35.5%) matching AKShare raw format"

patterns-established:
  - "Frozen Pydantic models for all pledge data contracts with Field descriptions"
  - "Ticker normalization via prefix mapping (6->SH, 0/3->SZ) with None for unsupported exchanges"

requirements-completed: [DATA-03]

# Metrics
duration: 5min
completed: 2026-06-06
---

# Phase 29 Plan 01: Pledge Data Contracts Summary

**Frozen Pydantic models for equity pledge snapshots/details, DataFreshness enum, and normalize_a_share_ticker utility mapping AKShare codes to internal ticker format**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-05T18:52:17Z
- **Completed:** 2026-06-05T18:56:55Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created 3 frozen Pydantic models (EquityPledgeSnapshot, EquityPledgeDetail, EquityPledgeDataQuality) following risk.py pattern
- Added DataFreshness enum with CURRENT/STALE/UNAVAILABLE to enums.py
- Implemented normalize_a_share_ticker with 6xx->.SH, 0xx/3xx->.SZ prefix mapping, returning None for BSE and invalid codes
- 24 new tests (9 normalizer + 15 model) all passing with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: DataFreshness enum, Pydantic models, and ticker normalizer** - `7b46638` (feat)
2. **Task 2: Lint, type-check, and verify no regressions** - verification-only, no code changes

## Files Created/Modified
- `stockvaluefinder/stockvaluefinder/models/equity_pledge.py` - EquityPledgeSnapshot, EquityPledgeDetail, EquityPledgeDataQuality models
- `stockvaluefinder/stockvaluefinder/models/enums.py` - DataFreshness enum added
- `stockvaluefinder/stockvaluefinder/utils/validators.py` - normalize_a_share_ticker function added
- `stockvaluefinder/tests/unit/test_models/test_equity_pledge.py` - 15 model tests (4 test classes)
- `stockvaluefinder/tests/unit/test_utils/test_validators.py` - TestNormalizeAShareTicker class (9 tests)

## Decisions Made
- DataFreshness placed in enums.py following existing RiskLevel/Market enum pattern
- BSE codes (8xx/4xx) return None rather than raising exceptions, enabling graceful filtering in data fetching
- company_pledge_ratio stored as percentage form (35.5 = 35.5%) matching AKShare raw output format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-commit mypy hook rejected initial RED-phase commit (module not found for equity_pledge.py). Combined RED+GREEN into a single commit since the hook requires the implementation to exist. Tests were written first and verified failing before implementation was added.

## Next Phase Readiness
- All data contracts ready for Plan 02 (data fetching via AKShare)
- normalize_a_share_ticker ready for use in field mapping from AKShare 6-digit codes to internal ticker format
- DataFreshness enum ready for data quality metadata in data_service pledge methods

---
*Phase: 29-pledge-data-foundation*
*Completed: 2026-06-06*

## Self-Check: PASSED
- equity_pledge.py: FOUND
- test_equity_pledge.py: FOUND
- 29-01-SUMMARY.md: FOUND
- Commit 7b46638: FOUND
