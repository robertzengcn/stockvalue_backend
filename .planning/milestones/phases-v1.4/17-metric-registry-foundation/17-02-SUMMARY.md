---
phase: 17-metric-registry-foundation
plan: 02
subsystem: validation
tags: [lru-cache, frozen-dataclass, tolerance-comparison, singleton-loader, registry-check]
dependency_graph:
  requires:
    - phase: 17-metric-registry-foundation/01
      provides: "Pydantic schema (MetricRegistry, Tolerance) and metric_registry.yaml"
  provides:
    - "lru_cache singleton loader: load_metric_registry()"
    - "Frozen ComparisonResult dataclass with tolerance comparison"
    - "MetricRegistry.check() method for metric-specific validation"
    - "Full public API export from validation package (9 symbols)"
  affects: [stockvaluefinder/validation/]
tech-stack:
  added: []
  patterns: [lru-cache-singleton-loader, frozen-dataclass-result, local-import-avoid-circular, tolerance-or-logic]
key-files:
  created:
    - stockvaluefinder/validation/loader.py
    - stockvaluefinder/validation/comparators.py
    - stockvaluefinder/tests/unit/test_validation/test_loader.py
    - stockvaluefinder/tests/unit/test_validation/test_comparators.py
  modified:
    - stockvaluefinder/validation/__init__.py
    - stockvaluefinder/validation/schema.py
key-decisions:
  - "D-10: Tolerance-based validation on registry.check() returns ComparisonResult with OR logic for combined tolerances"
  - "D-09: lru_cache(maxsize=1) singleton pattern for load_metric_registry(), matching AppConfig.get_instance() style"
  - "Local import of comparators inside MetricRegistry.check() to avoid circular dependency (schema -> comparators -> schema.Tolerance)"
patterns-established:
  - "Local import pattern: schema.py imports comparators inside method body to break circular dependency"
  - "dataclasses.replace() for creating new frozen dataclass instances with modified fields"
  - "compare_within_tolerance() returns ComparisonResult with empty metric_name, caller fills it via replace()"
requirements-completed:
  - REG-04
  - REG-05
metrics:
  duration_seconds: 210
  completed_date: 2026-05-21
---

# Phase 17 Plan 02: Loader and Comparators Summary

lru_cache singleton loader, frozen ComparisonResult dataclass with tolerance OR logic, and MetricRegistry.check() method enabling metric-specific validation for 28 financial metrics.

## Results

| Metric | Value |
|--------|-------|
| Tasks completed | 1/1 |
| Tests passing | 60 total (33 prior + 27 new) |
| New test files | 2 (test_comparators.py, test_loader.py) |
| Public API symbols | 9 |
| Duration | ~3.5 minutes |

## Task Summary

### Task 1: Create loader.py with lru_cache singleton and comparators.py with tolerance logic (TDD)

- **Commit:** bb54f9f
- **Files:** `validation/loader.py`, `validation/comparators.py`, `validation/__init__.py`, `validation/schema.py`, `tests/unit/test_validation/test_comparators.py`, `tests/unit/test_validation/test_loader.py`
- **Details:** TDD approach: wrote 27 tests first (RED), then implemented all 3 modules (GREEN). Created `comparators.py` with frozen `ComparisonResult` dataclass and `compare_within_tolerance()` pure function supporting absolute, relative, and combined tolerances with OR logic. Created `loader.py` with `lru_cache(maxsize=1)` singleton using `Path(__file__).parent` for package-relative YAML loading. Added `MetricRegistry.check(name, expected, computed, sector)` method to schema.py using local import to avoid circular dependency. Updated `__init__.py` to export all 9 public symbols.

## Key Decisions

1. **Local import for circular dependency avoidance**: `schema.py` imports `compare_within_tolerance` inside the `check()` method body rather than at module level. This prevents the circular import chain: `schema.py -> comparators.py -> schema.py` (comparators imports `Tolerance`). This is the standard Python pattern for circular imports.

2. **dataclasses.replace() for immutable result modification**: `compare_within_tolerance()` returns a `ComparisonResult` with an empty `metric_name` string. The `check()` method uses `dataclasses.replace()` to create a new instance with the correct `metric_name` filled in. This preserves immutability while avoiding parameter clutter in the comparator function.

3. **OR logic for combined tolerances**: When a metric specifies both `absolute` and `relative` tolerances, the value passes if EITHER is satisfied. This is the standard approach in scientific computing (similar to numpy's `allclose` behavior).

4. **Expected=0 edge case**: When `expected=0` and only `relative` tolerance is set, falls back to comparing `delta <= relative` directly. This avoids division by zero while maintaining a sensible fallback.

## Verification

- All 60 tests pass: `cd stockvaluefinder && DATABASE_URL=... uv run pytest tests/unit/test_validation/ -v`
- End-to-end load + check: `cd stockvaluefinder && uv run python -c "from stockvaluefinder.validation import load_metric_registry; r = load_metric_registry(); result = r.check('m_score', -2.5, -2.52); print(f'Passed: {result.passed}, Delta: {result.delta}')"`
- Linting clean: `cd stockvaluefinder && uv run ruff check stockvaluefinder/validation/`
- Format clean: `cd stockvaluefinder && uv run ruff format --check stockvaluefinder/validation/`
- Coverage: comparators.py 100%, loader.py 100%, schema.py 98%

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None. Trust boundaries handled per T-17-03 (Path(__file__).parent prevents path traversal) and T-17-04 (O(1) float comparison).

## Self-Check: PASSED

All 4 created files verified present. Commit hash bb54f9f found in git log. All 60 tests pass.

---
*Phase: 17-metric-registry-foundation*
*Completed: 2026-05-21*
