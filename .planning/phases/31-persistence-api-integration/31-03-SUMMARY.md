---
phase: 31-persistence-api-integration
plan: 03
subsystem: narrative-prompts
tags: [narrative, pledge-risk, guardrails, llm-prompt]
dependency_graph:
  requires: [31-01, 31-02]
  provides: [narrative-pledge-extension]
  affects: [risk_routes, narrative_prompts]
tech_stack:
  added: []
  patterns: [conditional-prompt-section, lambda-closure-for-optional-args]
key_files:
  created: []
  modified:
    - stockvaluefinder/stockvaluefinder/services/narrative_prompts.py
    - stockvaluefinder/stockvaluefinder/api/risk_routes.py
    - stockvaluefinder/tests/unit/test_services/test_narrative_prompts.py
decisions:
  - D-01: PromptBuilder type alias changed to Callable[..., tuple[str, str]] to allow optional pledge_data parameter without breaking narrative_service.py
  - D-02: Lambda closure in risk_routes.py captures pledge_risk_result for two-arg prompt_builder protocol
  - D-03: pledge_section uses three-tier conditional: unsupported (HK), UNAVAILABLE freshness, and full data
metrics:
  duration: 491s
  completed: 2026-06-07
  tasks: 1/1
  files: 3
---

# Phase 31 Plan 03: Narrative Prompt Pledge Extension Summary

Extend build_risk_prompt() with pledge risk data section and explicit guardrails for LLM narrative generation.

## Requirements Satisfied

| Requirement | Description | Status |
|-------------|-------------|--------|
| NARR-01 | Full pledge risk paragraph with structured data fields in narrative prompt | SATISFIED |
| NARR-02 | Guardrail: only use data from structured fields, no fabrication | SATISFIED |
| NARR-03 | State "pledge data unavailable" when missing without implying low risk | SATISFIED |
| NARR-04 | Omit closeout distance when safety_margin is null | SATISFIED |

## Changes Made

### stockvaluefinder/services/narrative_prompts.py

- Updated PromptBuilder type alias from Callable[[str, dict[str, Any]], ...] to Callable[..., ...] to support optional pledge_data parameter
- Extended build_risk_prompt() signature with pledge_data: dict[str, Any] | None = None
- Added conditional pledge section with three tiers:
  - HK stocks (supported=False): Simple note that HK stocks do not support pledge data
  - UNAVAILABLE freshness: Explicit "data unavailable" statement with NARR-03 guardrail forbidding risk inference
  - CURRENT/STALE freshness: Full structured data section (final risk level, company ratio, holder ratio, closeout margin) with NARR-02 and NARR-04 guardrails
- Backward compatible: existing callers passing only (ticker, result_data) continue to work unchanged

### stockvaluefinder/api/risk_routes.py

- Updated generate_and_serialize_narrative call to pass pledge data via lambda closure
- Lambda wraps build_risk_prompt(t, d, pledge_data=...) to match the two-arg protocol of generate_and_serialize_narrative

### tests/unit/test_services/test_narrative_prompts.py

- Added TestBuildRiskPromptPledgeSection test class with 6 new tests:
  - test_backward_compatible_no_pledge_data: No pledge section when pledge_data is None
  - test_hk_stock_unsupported: HK stock note, no risk analysis details
  - test_unavailable_freshness_guardrail: NARR-03 guardrail text present
  - test_full_pledge_data_with_guardrails: NARR-01 data values + NARR-02 guardrails
  - test_null_safety_margin_omits_closeout_distance: NARR-04 compliance
  - test_stale_freshness_shows_full_section: STALE treated same as CURRENT

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Backward compat | build_risk_prompt('600519.SH', {'risk_level': 'LOW'}) | PASS |
| HK stock | pledge_data={'supported': False, ...} | PASS |
| Unavailable | freshness='UNAVAILABLE' | PASS |
| Full data + guardrails | Full pledge_data with all fields | PASS |
| NARR-04 null margin | safety_margin=None | PASS |
| All 14 unit tests | pytest test_narrative_prompts.py | PASS |
| Ruff check | ruff check | PASS |
| Ruff format | ruff format | PASS |
| Pre-commit hooks | All passed (mypy, ruff) | PASS |

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. PromptBuilder type alias: Changed to Callable[..., tuple[str, str]] so that narrative_service.py (which calls prompt_builder(ticker, result_data) with 2 args) continues to work while build_risk_prompt accepts an optional 3rd arg
2. Lambda closure in risk_routes.py: Used lambda t, d: build_risk_prompt(t, d, pledge_data=...) to bridge the 2-arg protocol of generate_and_serialize_narrative to the 3-arg signature of build_risk_prompt
3. Three-tier conditional: HK unsupported -> unavailable freshness -> full data, each with appropriate guardrail language

## Auth Gates

None.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| stockvaluefinder/stockvaluefinder/services/narrative_prompts.py | FOUND |
| stockvaluefinder/stockvaluefinder/api/risk_routes.py | FOUND |
| stockvaluefinder/tests/unit/test_services/test_narrative_prompts.py | FOUND |
| 31-03-SUMMARY.md | FOUND |
| Commit ac91d48 (feat(31-03)) | FOUND |
