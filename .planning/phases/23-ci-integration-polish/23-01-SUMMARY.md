---
phase: 23-ci-integration-polish
plan: 01
subsystem: infra
tags: [github-actions, ci, pre-commit, validation, pytest]

# Dependency graph
requires:
  - phase: 19-l1-formula-tests
    provides: "L1 formula tests (161 tests) with l1_formula marker"
  - phase: 20-l2-mapping-tests
    provides: "L2 mapping tests (403 tests) with l2_mapping marker"
  - phase: 21-l3-golden-tests
    provides: "L3 golden tests (22 tests) with golden and golden_live markers"
provides:
  - "GitHub Actions workflow with 4 CI jobs gating PRs on L1/L2/golden tests"
  - "Weekly scheduled golden-live job for live AKShare API validation"
  - "validate_registry.py script for metric_registry.yaml schema validation"
  - "Pre-commit validate-registry hook catching registry drift"
affects: [all-future-phases, pull-requests]

# Tech tracking
tech-stack:
  added: [github-actions, astral-sh/setup-uv@v5]
  patterns: [ci-gated-pr, scheduled-live-tests, pre-commit-schema-validation]

key-files:
  created:
    - .github/workflows/validation.yml
    - stockvaluefinder/stockvaluefinder/tools/validate_registry.py
  modified:
    - stockvaluefinder/.pre-commit-config.yaml

key-decisions:
  - "Used python -m invocation for validate_registry to ensure package imports resolve correctly"
  - "Set golden-live-scheduled job to only run on schedule and workflow_dispatch (not PRs)"

patterns-established:
  - "CI gate pattern: 3 PR-gated jobs (l1-formula, l2-mapping, golden) + 1 scheduled job (golden-live)"
  - "Pre-commit schema validation: always_run ensures registry validated even on non-YAML changes"

requirements-completed: [CI-01, CI-02, CI-03, CI-04, CI-05]

# Metrics
duration: 2min
completed: 2026-05-21
---

# Phase 23 Plan 01: CI Integration & Polish Summary

**GitHub Actions workflow with 4 pytest jobs gating PRs and validate_registry pre-commit hook**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-21T22:14:54Z
- **Completed:** 2026-05-21T22:17:16Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- GitHub Actions workflow with 3 PR-gated jobs (l1-formula, l2-mapping, golden) and 1 weekly scheduled job (golden-live-scheduled)
- validate_registry.py script that validates metric_registry.yaml against Pydantic schema, printing category/priority summary
- Pre-commit validate-registry hook with always_run to catch schema drift on any commit

## Task Commits

Each task was committed atomically:

1. **Task 1: Create GitHub Actions validation workflow** - `5e9e135` (ci)
2. **Task 2: Create registry validation script and pre-commit hook** - `5e9e135` (ci, combined)

## Files Created/Modified
- `.github/workflows/validation.yml` - CI workflow with 4 jobs: l1-formula, l2-mapping, golden, golden-live-scheduled
- `stockvaluefinder/stockvaluefinder/tools/validate_registry.py` - Validates metric_registry.yaml, prints summary (28 metrics, 7 categories, P0/P1/P2 counts)
- `stockvaluefinder/.pre-commit-config.yaml` - Added validate-registry hook after ruff-format

## Decisions Made
- Used `python -m stockvaluefinder.tools.validate_registry` invocation in pre-commit hook because direct script execution fails with ModuleNotFoundError (package not on sys.path without pytest's pythonpath setting)
- golden-live-scheduled job uses `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'` to prevent it from running on every PR alongside the other 3 jobs
- pytest.ini addopts include `--cov=stockvaluefinder` which adds overhead in CI but is harmless with marker filtering, per plan guidance

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- validate_registry.py direct execution (`uv run python stockvaluefinder/tools/validate_registry.py`) failed with ModuleNotFoundError because the package is not installed on sys.path outside pytest context. Resolved by using `python -m` invocation which correctly resolves package imports.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CI enforcement layer complete. All future PRs will be gated by L1/L2/golden tests.
- Weekly golden-live-scheduled job will catch AKShare API regressions automatically.
- Phase 23 plan 01 is the only plan in this phase; phase 23 is now complete.

---
*Phase: 23-ci-integration-polish*
*Completed: 2026-05-21*
