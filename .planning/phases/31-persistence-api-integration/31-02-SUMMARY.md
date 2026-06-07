---
phase: "31"
plan: "02"
subsystem: risk-api-pledge-integration
tags: [api, pledge-risk, graceful-degradation, risk-merge]
dependency_graph:
  requires: [31-01]
  provides: [risk-api-pledge-endpoint]
  affects: [risk_routes, narrative]
tech_stack:
  added: [PledgeRiskAnalyzer, PledgeSnapshotRepository, PledgeDetailRepository]
  patterns: [graceful-degradation, transactional-persistence]
key_files:
  created: []
  modified:
    - stockvaluefinder/api/risk_routes.py
decisions:
  - D-01: Pledge computation separated from pledge persistence; persistence runs inside DB save try/except for proper rollback
  - D-02: include_pledge_risk defaults True so existing clients automatically get pledge data
metrics:
  duration: 10m
  completed: 2026-06-07
---

# Phase 31 Plan 02: Risk API Pledge Integration Summary

Integrate pledge risk analysis (PledgeRiskAnalyzer) into the existing POST /analyze/risk endpoint with graceful degradation, HK stock handling, and transactional persistence of pledge data.

## Changes Made

### risk_routes.py

**New imports:** PledgeRiskAnalyzer, is_hk_ticker, PledgeSnapshotRepository, PledgeDetailRepository

**RiskAnalysisRequest:** Added `include_pledge_risk: bool = Field(True)` flag per API-01, allowing clients to opt out of pledge analysis.

**Pledge computation block (lines 170-203):**
- For A-share tickers: fetches snapshot + details from ExternalDataService, runs PledgeRiskAnalyzer.analyze()
- For HK tickers: returns `supported=False` result per API-05
- Wrapped in try/except with graceful degradation: on any failure, pledge_risk_result stays None
- Stores pledge_snapshot and pledge_details as local variables for later persistence

**Narrative enrichment:** Passes pledge risk result data into `result_data_for_narrative` so the LLM can reference pledge risk in its narrative.

**Risk level merge:** Uses `pledge_risk_result.risk_level_breakdown.final_risk_level` when available, falling back to financial-only risk_level. Pledge can only upgrade risk, never downgrade.

**Database persistence (lines 228-306):**
- RiskScoreCreate now includes `pledge_risk` and `risk_level_breakdown` fields
- Pledge snapshot/detail persistence runs within the same try/except as risk score save (same transaction)
- Guard: only persists when `include_pledge_risk=True`, pledge analysis succeeded, and ticker is not HK
- Guard: skips snapshot persistence when `latest_date` is None (mypy type safety)

**Response construction:** Returns `RiskScoreWithNarrative` with pledge_risk and risk_level_breakdown embedded. Final risk_level reflects pledge upgrade if applicable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Pledge persistence transaction safety**
- **Found during:** Task 1 implementation
- **Issue:** Plan placed pledge persistence inside the pledge computation try/except, but this could leave the DB session in a dirty state if persistence fails. The plan stated "G. Pledge persistence runs WITHIN the existing try/except block that handles the database save" which contradicted the code placement.
- **Fix:** Separated pledge computation (fetch + analyze, gracefully degrades) from pledge persistence (runs inside the DB save try/except with proper rollback). Stored snapshot/details as local variables so they survive the computation try/except and can be persisted later.
- **Files modified:** stockvaluefinder/api/risk_routes.py
- **Commit:** 9e00edf

**2. [Rule 1 - Bug] mypy type error on nullable latest_date**
- **Found during:** Pre-commit hook (mypy)
- **Issue:** `EquityPledgeSnapshot.latest_date` is `date | None` but `PledgeSnapshotRepository.upsert_by_ticker_date_source` expects `date`.
- **Fix:** Added `if pledge_snapshot.latest_date is not None` guard before calling upsert.
- **Files modified:** stockvaluefinder/api/risk_routes.py
- **Commit:** 9e00edf

### Deferred Issues

None.

## Verification Results

1. RiskAnalysisRequest has include_pledge_risk field: PASS
2. analyze_risk imports correctly: PASS
3. RiskScoreWithNarrative has pledge_risk and risk_level_breakdown fields (inherited from RiskScore): PASS
4. ruff check: PASS
5. ruff format: PASS
6. mypy: PASS
7. All pre-existing tests: No new failures

## Self-Check: PASSED

- stockvaluefinder/stockvaluefinder/api/risk_routes.py: EXISTS (modified)
- Commit 9e00edf: EXISTS in git log
