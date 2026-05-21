---
phase: 22
plan: 02
subsystem: tools
tags: [cli, typer, rich, reconcile, json-output, exit-codes]
dependency_graph:
  requires:
    - 22-01 (reconcile_core.py ReconcileResult, reconcile, reconcile_live)
    - 17-01 (metric_registry.yaml)
    - 17-02 (MetricRegistry, ComparisonResult, Tolerance)
  provides:
    - reconcile CLI entry point via Typer app
    - format_rich_table() colored PASS/FAIL table
    - format_json_output() machine-parseable JSON
    - format_verbose_output() per-metric audit trail text
    - Exit codes: 0/1/2
  affects: []
tech_stack:
  added: [typer>=0.25.1, rich (transitive via typer)]
  patterns: [typer-cli, rich-table-formatting, path-sanitization-in-errors]
key_files:
  created:
    - stockvaluefinder/tools/reconcile.py
    - stockvaluefinder/tests/unit/test_tools/test_reconcile_cli.py
  modified:
    - stockvaluefinder/pyproject.toml (added typer, rich dependencies)
decisions:
  - METRIC column shows both metric key and display name (e.g. "m_score (Beneish M-Score)") for grep-ability
  - Console width set to 200 in verbose mode to prevent Rich truncating column headers in CI/piped contexts
  - FileNotFoundError messages sanitized to show relative paths only (e.g. "tests/golden/...") not absolute filesystem paths
  - No __main__.py needed -- reconcile.py uses `if __name__ == "__main__": app()` pattern
metrics:
  duration_minutes: 5
  completed_date: "2026-05-21"
  tasks_total: 2
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  tests_added: 7
---

# Phase 22 Plan 02: Reconcile CLI Tool Summary

Typer CLI entry point wrapping reconcile_core logic with Rich colored tables for human inspection, JSON mode for CI/CD integration, verbose audit trail, and correct exit codes for automated gates.

## What Was Built

### reconcile.py (248 lines)

- **Typer app** with `main()` command accepting `--ticker`, `--year`, `--metric`, `--verbose/-v`, `--json`, `--live` options
- **format_rich_table()** -- Rich Table with colored PASS (green bold) / FAIL (red bold) status, metric key + display name, numeric formatting, tolerance display. Verbose mode adds PRIORITY (color-coded: P0=red, P1=yellow), CATEGORY, and AUDIT_TRAIL columns
- **format_json_output()** -- Machine-parseable JSON with ticker, year, summary, comparisons (each with metric_name, expected, computed, delta, tolerance, passed), skipped_metrics, p0_all_pass
- **format_verbose_output()** -- Detailed per-metric audit trail text printed after the table: display name, category, priority, expected vs computed, delta, tolerance, formula reference, audit trail availability
- **Exit codes**: 0=all P0 pass, 1=P0 failure, 2=error (FileNotFoundError, KeyError, generic exception)
- **--live flag**: uses `asyncio.run(reconcile_live(ticker, year, metric))` for live AKShare data
- **Path sanitization**: FileNotFoundError messages strip absolute filesystem paths, showing only `tests/golden/...` relative paths

### Test Suite (7 tests, all passing)

- test_cli_basic_invocation: exit 0, PASS in output, metric names visible
- test_cli_json_output: valid JSON with ticker/year/p0_all_pass/comparisons structure
- test_cli_single_metric: --metric m_score limits to single row
- test_cli_missing_ticker_exit_code_2: exit 2 for non-existent ticker
- test_cli_verbose_mode: PRIORITY column header present
- test_cli_json_structure_complete: all required top-level and summary keys present
- test_cli_no_args_shows_help: non-zero exit with help text

## TDD Compliance

| Gate | Commit | Hash |
|------|--------|------|
| RED | test(22-02): add failing tests for reconcile CLI | 0a18828 |
| GREEN | feat(22-02): add Typer CLI with Rich tables, JSON output, and live mode | d0f963a |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] METRIC column showed only display_name, not metric key**
- **Found during:** Task 1 GREEN phase -- test_cli_basic_invocation failed because "m_score" not in output
- **Issue:** Rich table displayed human-readable display names (e.g. "Beneish M-Score") but tests grep for metric keys (e.g. "m_score")
- **Fix:** Changed METRIC column to show "metric_key (display_name)" format so both machine-readable and human-readable names are visible
- **Files modified:** stockvaluefinder/tools/reconcile.py
- **Commit:** d0f963a

**2. [Rule 2 - Security] FileNotFoundError leaked absolute filesystem paths**
- **Found during:** Task 1 -- exit code 2 test showed full `/home/robertzeng/...` path in error output
- **Issue:** Threat model T-22-08 requires sanitizing paths to relative only
- **Fix:** Added path sanitization that strips absolute prefix, keeping only `tests/golden/...` relative portion
- **Files modified:** stockvaluefinder/tools/reconcile.py
- **Commit:** d0f963a

**3. [Rule 3 - Blocking] Rich table truncated verbose column headers at 80-char terminal width**
- **Found during:** Task 1 -- test_cli_verbose_mode failed because "PRIORITY" was truncated in CliRunner output
- **Issue:** CliRunner defaults to 80-char width, truncating PRIORITY/CATEGORY/AUDIT_TRAIL headers
- **Fix:** Set Console(width=200) when verbose mode is active
- **Files modified:** stockvaluefinder/tools/reconcile.py
- **Commit:** d0f963a

## Known Stubs

None -- all functionality is wired to real data sources.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model covers. Path sanitization mitigation (T-22-08) was applied.

## Self-Check: PASSED

Both created files verified present. Both commits (RED 0a18828, GREEN d0f963a) found in git log.
