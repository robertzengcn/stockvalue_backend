---
phase: 23
reviewers: [claude]
reviewed_at: 2026-05-21T22:55:26Z
plans_reviewed: [23-01-PLAN.md, 23-02-PLAN.md]
notes: "claude invoked as a separate session (CLAUDECODE unset) since no other independent CLI was authenticated. Single-reviewer run — no cross-AI consensus available."
---

# Cross-AI Plan Review — Phase 23

> **Note:** Only one reviewer (claude in a separate session) was available — cursor was unauthenticated and no other CLIs (gemini, codex, opencode, qwen) were installed. This is a single-perspective review, not a true cross-AI consensus.

## Claude Review

# Cross-AI Plan Review: Phase 23 — CI Integration & Polish

---

## Plan 23-01: CI Workflow + Registry Validation + Pre-commit Hook

### Summary

Plan 23-01 creates a GitHub Actions workflow with 4 parallel jobs (l1-formula, l2-mapping, golden, golden-live-scheduled), a Pydantic-based registry validation script, and a pre-commit hook to enforce registry integrity on every commit. The plan is well-scoped and directly addresses requirements CI-01 through CI-05. I note that the workflow file, pre-commit hook, and pytest.ini already exist in the working tree (partially executed from a prior session), which validates the plan's feasibility but raises questions about whether re-execution would clobber existing working state.

### Strengths

- **Direct requirements traceability** — Each of the 4 CI jobs maps cleanly to CI-01..CI-04, and the pre-commit hook satisfies CI-05. Success criteria are testable.
- **Correct trigger design** — `golden-live-scheduled` correctly uses `schedule` + `workflow_dispatch` with an `if:` guard to prevent it from running on push/PR, while sharing the same workflow file.
- **Leverages existing infrastructure** — `MetricRegistry.from_yaml_file()` and the Pydantic schema already exist, so `validate_registry.py` is a thin wrapper, not a new validation layer.
- **Practical verification steps** — Each task has automated grep-based verification that can be run locally.
- **Explicit `continue-on-error: false`** — Makes intent clear even though it's the default.

### Concerns

- **HIGH — Coverage overhead in CI**: `pytest.ini` has `--cov=stockvaluefinder --cov-report=html --cov-report=term-missing -v` in `addopts`. This runs for **every** `pytest` invocation including all 4 CI jobs. With 14 golden stocks x 28 metrics + L1/L2 tests, this means 4x coverage collection, 4x HTML report generation, and verbose output. The plan explicitly says "Do NOT change it" but CI commands should override with `--override-ini="addopts="` or use `-p no:cacheprovider` to avoid this. The `-v` flag also contradicts the plan's own `-q` flag (which pytest will ignore since `addopts` runs first).

- **HIGH — 4 separate jobs = 4x `uv sync`**: Each job independently runs `checkout -> setup-uv -> setup-python -> uv sync`. For a project with many dependencies (akshare, langchain, qdrant-client, etc.), `uv sync` could take 30-60s per job. Total CI wall time could be 2-4 minutes just on setup. A matrix strategy would reduce this to 1 sync + parallel test execution:
  ```yaml
  strategy:
    matrix:
      marker: [l1_formula, l2_mapping, golden]
  ```
  This is a design trade-off worth calling out explicitly.

- **MEDIUM — `golden-live-scheduled` failure surfacing**: The plan acknowledges T-23-03 (failures must surface) but the only mitigation is `continue-on-error: false`. GitHub scheduled workflow failures are easy to miss — they don't appear in PR checks, don't send notifications by default, and the GitHub "Actions" tab is not monitored by most developers. The plan defers Slack notification but doesn't mention GitHub's built-in `jobs.<id>.steps.outcome` checks or `actions/create-github-app-token` for notification workflows. At minimum, add a comment in the YAML about where to check for failures.

- **MEDIUM — AKShare downtime during weekly `golden_live`**: AKShare is a free, community-maintained package that scrapes Chinese financial data. It frequently breaks when upstream sites (East Money, Sina Finance) change their HTML structure. A weekly scheduled job hitting a potentially broken API will generate noisy failures. The plan should specify a timeout (`timeout-minutes: 15`) and consider whether `golden_live` failures should block anything or just be informational.

- **MEDIUM — Pre-commit `always_run: true` friction**: The `validate-registry` hook runs on every commit regardless of which files changed. Combined with the existing `mypy`, `ruff-check`, and `ruff-format` hooks (all `always_run: true`), every commit already triggers 4 hooks. Adding a 5th increases friction. Consider `files: "stockvaluefinder/validation/metric_registry\\.yaml$"` to only trigger when the registry or schema changes. The plan's rationale ("a change to schema.py could break the registry without touching the YAML") is valid, but this should be a CI check, not a local pre-commit hook.

- **LOW — `bash -c` in pre-commit entry**: The hook uses `entry: bash -c "cd stockvaluefinder && uv run python ..."` which is a shell invocation. While this matches the existing hooks' pattern and is committed to the repo (not untrusted input), it's worth noting that `language: system` hooks bypass pre-commit's isolation. This is consistent with the project's existing pattern.

- **LOW — Plan states `.github/ does NOT exist yet`**: The plan context says the directory must be created, but it already exists with `validation.yml` in the working tree. This suggests the plan was partially executed and the context section is stale. Re-execution should handle this gracefully.

### Suggestions

- **Override coverage in CI**: Change CI commands to `uv run pytest -m l1_formula -x -q --override-ini="addopts="` or add a separate `pytest-ci.ini` without coverage. CI is not the place for HTML coverage reports.
- **Add `timeout-minutes` to all jobs**: Default GitHub Actions timeout is 6 hours. Set `timeout-minutes: 10` on each job to prevent hanging builds from consuming runner minutes.
- **Consolidate to matrix strategy**: Use `strategy.matrix.marker` for the 3 PR-gated jobs. Keep `golden-live-scheduled` as a separate job.
- **Add failure notification for scheduled job**: Even a simple step that creates a GitHub issue on failure would be better than silent failure:
  ```yaml
  - if: failure()
    run: gh issue create --title "Weekly golden_live tests failed" ...
  ```
- **Scope the pre-commit hook**: Use `files:` regex to trigger only on registry/schema changes, and rely on CI for the comprehensive check.
- **Pin action versions with SHA**: `actions/checkout@v4` could be compromised if the tag is moved. Pin to a full commit SHA for production CI.

---

## Plan 23-02: Validation Guide Documentation

### Summary

Plan 23-02 creates a single documentation file (`doc/validation_guide.md`) covering the 3-layer validation pyramid, test commands, reconcile CLI usage, golden stock contribution workflow, and tolerance configuration reference. The plan is appropriately scoped as a single-task documentation effort with clear section requirements. The context section provides concrete interface examples from pytest.ini, reconcile.py, and metric_registry.yaml that give the executor sufficient material to write accurate documentation.

### Strengths

- **Well-structured section breakdown** — The 5 sections follow a logical progression from understanding (overview) to doing (running tests, CLI) to extending (contributing golden stocks) to configuring (tolerances).
- **Concrete context** — The plan includes actual CLI usage examples, pytest commands, metric counts (28 metrics, 7 categories, 14 stocks), and tolerance values. This eliminates guesswork for the executor.
- **Practical focus** — The plan explicitly says "No fluff, no motivational prose. This is a reference document." This is the right tone for developer documentation.
- **Verification is grep-based and practical** — Checking for the presence of key terms (`l1_formula`, `reconcile`, `tolerance`, `manifest.yaml`) is a reasonable documentation completeness check.

### Concerns

- **MEDIUM — Tolerance values may drift from source**: The plan hard-codes tolerance examples in the task description (e.g., "Risk: absolute 0.05, ROIC: relative 0.02"). If the executor writes these into the documentation, they become a second source of truth that can drift from `metric_registry.yaml`. The guide should note "as of [date]" or link to the registry file directly.

- **MEDIUM — Section 3 references `reconcile.py` but plan doesn't verify it exists**: The plan assumes the reconcile CLI tool from Phase 22 is complete and functional. If Phase 22 is incomplete or the CLI interface differs, the documentation will be inaccurate. The plan should include a verification step that runs `uv run python -m stockvaluefinder.tools.reconcile --help` to confirm the CLI exists and flags match.

- **LOW — Golden contribution step 2 references `freeze_akshare_data.py`**: The plan references a specific script (`tests/golden/freeze_akshare_data.py`) in the contribution workflow. This script exists in the working tree, but the plan doesn't verify its CLI interface matches the documented usage.

- **LOW — Documentation-only plan has no test coverage**: While a doc file doesn't need tests per se, the plan claims requirements CI-01 through CI-05 but only indirectly addresses them (the docs describe the CI system). The requirements mapping feels forced for a documentation task.

### Suggestions

- **Add a "Last Updated" footer**: Include a note that tolerance values are current as of the document creation date, with a pointer to `metric_registry.yaml` as the authoritative source.
- **Verify CLI before documenting**: Add a pre-step that runs `--help` on the reconcile CLI to confirm the documented flags match reality.
- **Consider a "Troubleshooting" section**: Common issues like "AKShare timeout during golden_live" or "metric_registry.yaml validation failed after adding new metric" would be high-value additions.
- **Link to actual files**: Use relative links to `stockvaluefinder/stockvaluefinder/validation/metric_registry.yaml` and `stockvaluefinder/pytest.ini` so developers can navigate directly.

---

## Risk Assessment

### Plan 23-01: **MEDIUM**

The plan is technically sound and directly achievable, but the CI performance concern (4x `uv sync`, coverage overhead) and the silent failure risk for scheduled jobs are real operational issues that will surface quickly in practice. The pre-commit friction from `always_run: true` will annoy developers on every commit. These are fixable but should be addressed before the plan is considered complete.

### Plan 23-02: **LOW**

Documentation plans carry minimal risk. The main risk is accuracy drift if tolerance values are hard-coded rather than referenced, and potential inaccuracy if the reconcile CLI interface differs from the documented examples. Both are easily caught during review.

### Overall Phase Risk: **LOW-MEDIUM**

Phase 23 is the final polish phase. The plans are well-scoped, have clear verification steps, and don't introduce complex dependencies. The main risk is operational (CI performance, notification gaps) rather than technical. The existing codebase already has most infrastructure in place (markers, registry, golden datasets, reconcile CLI), making this phase primarily about wiring and documentation rather than new development.

---

## Consensus Summary

> Only one reviewer was available, so there is no true consensus. Below is the single reviewer's prioritized synthesis.

### Top Concerns (single-reviewer)

1. **CI performance — HIGH** (Plan 23-01)
   - Coverage collection (`--cov`, `--cov-report=html`, `-v`) inherited from `pytest.ini` `addopts` runs on every CI job. Fix: override addopts in CI command or use a `pytest-ci.ini`.
   - 4 parallel jobs each run `uv sync` independently. Fix: consolidate to a `strategy.matrix.marker` job.

2. **Silent failure of scheduled `golden_live` — MEDIUM** (Plan 23-01)
   - Weekly cron failures don't appear on PRs and rarely get noticed. Fix: add a `if: failure()` step that opens a GitHub issue, and set `timeout-minutes: 15`.

3. **Pre-commit hook friction — MEDIUM** (Plan 23-01)
   - `always_run: true` adds a 5th unconditional hook on every commit. Fix: scope with `files: "metric_registry\\.yaml$|validation/schema\\.py$"` and rely on CI for the broader check.

4. **Documentation drift — MEDIUM** (Plan 23-02)
   - Hard-coded tolerance values in the guide will drift from `metric_registry.yaml`. Fix: include "Last Updated" + link to the registry as authoritative.

5. **CLI interface unverified — MEDIUM** (Plan 23-02)
   - Docs for reconcile CLI flags are written without verifying `--help` matches. Fix: add a pre-step to run `uv run python -m stockvaluefinder.tools.reconcile --help`.

### Strengths (single-reviewer)

- Both plans have direct, testable requirements traceability (CI-01..CI-05).
- Plan 23-01 correctly separates PR-gated jobs from scheduled jobs and uses `continue-on-error: false` explicitly.
- Plan 23-02 has concrete context (metric counts, tolerance examples, CLI signatures) that eliminates executor guesswork.
- Both plans leverage existing infrastructure (`MetricRegistry`, reconcile CLI from Phase 22) rather than rebuilding.

### Divergent Views

N/A — only one reviewer.

### Action Items if Replanning

If `/gsd-plan-phase 23 --reviews` is run:

1. Add a CI-specific pytest config (or `--override-ini="addopts="`) to drop coverage overhead in CI runs.
2. Consolidate the 3 PR-gated jobs into a matrix strategy to share `uv sync`.
3. Add `timeout-minutes` to all jobs and a `failure() -> gh issue create` step on `golden-live-scheduled`.
4. Scope the `validate-registry` pre-commit hook with a `files:` regex; keep the broad check in CI.
5. Add a "Last Updated" + registry link to the validation guide, plus a CLI `--help` verification step.
6. Pin GitHub Actions to commit SHAs (defense in depth).
