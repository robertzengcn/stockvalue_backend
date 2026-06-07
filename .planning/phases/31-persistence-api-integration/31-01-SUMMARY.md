---
phase: "31"
plan: "01"
subsystem: "persistence-api-integration"
tags: ["orm", "migration", "repository", "pledge-risk"]
dependency_graph:
  requires: ["phase-30-pledge-risk-analyzer"]
  provides: ["equity-pledge-orm-models", "equity-pledge-repositories", "risk-score-pledge-fields"]
  affects: ["risk_scores", "risk_repo", "risk-domain-models"]
tech_stack:
  added: ["sqlalchemy-orm-equity-pledge", "alembic-021"]
  patterns: ["upsert-by-natural-key", "replace-details-for-ticker"]
key_files:
  created:
    - stockvaluefinder/stockvaluefinder/db/models/equity_pledge.py
    - stockvaluefinder/stockvaluefinder/repositories/equity_pledge_repo.py
    - stockvaluefinder/alembic/versions/021_equity_pledge_tables.py
  modified:
    - stockvaluefinder/stockvaluefinder/db/models/risk.py
    - stockvaluefinder/stockvaluefinder/db/models/__init__.py
    - stockvaluefinder/stockvaluefinder/models/risk.py
    - stockvaluefinder/stockvaluefinder/repositories/risk_repo.py
decisions:
  - D-01: pledge_risk and risk_level_breakdown stored as nullable JSONB on risk_scores
  - D-03: migration 021 chains from revision 020
  - D-04: source_raw JSONB column on both pledge tables for audit traceability
  - DB-03: pledge columns nullable to support HK tickers without pledge data
  - DB-06: two new tables (equity_pledge_snapshots, equity_pledge_details) plus risk_scores alter
metrics:
  duration: "8m22s"
  completed: "2026-06-07T13:20:58Z"
  tasks: 2
  files: 7
---

# Phase 31 Plan 01: ORM Models, Migration, Repositories Summary

Equity pledge ORM models (snapshot + detail), Alembic migration 021, pledge repositories with upsert/replace patterns, and risk domain model extensions for pledge risk persistence.

## Tasks Completed

### Task 1: ORM models for pledge tables and migration 021

- Created `EquityPledgeSnapshotDB` with UniqueConstraint on (ticker, latest_date, source)
- Created `EquityPledgeDetailDB` with composite indexes on (ticker, announcement_date) and (ticker, holder_name)
- Extended `RiskScoreDB` with `pledge_risk` and `risk_level_breakdown` JSONB columns
- Created Alembic migration 021 chaining from revision 020
- Registered new models in `db/models/__init__.py`
- Commit: cae3449

### Task 2: Pledge repositories and extended RiskScoreCreate/upsert

- Created `PledgeSnapshotRepository` with `upsert_by_ticker_date_source` and `get_by_ticker`
- Created `PledgeDetailRepository` with `replace_details_for_ticker` and `get_by_ticker`
- Added `pledge_risk` and `risk_level_breakdown` optional fields to `RiskScoreCreate`
- Added `pledge_risk` and `risk_level_breakdown` optional fields to `RiskScore`
- Extended `RiskScoreRepository.upsert_by_report_id` and `create` with pledge columns
- Commit: 50d9962

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All four verification commands passed:
1. ORM model imports OK
2. RiskScoreDB.pledge_risk attribute exists
3. Repository imports OK
4. RiskScoreCreate import OK

## Self-Check: PASSED

All files verified present:
- stockvaluefinder/stockvaluefinder/db/models/equity_pledge.py (FOUND)
- stockvaluefinder/stockvaluefinder/db/models/risk.py (FOUND, extended)
- stockvaluefinder/stockvaluefinder/db/models/__init__.py (FOUND, extended)
- stockvaluefinder/alembic/versions/021_equity_pledge_tables.py (FOUND)
- stockvaluefinder/stockvaluefinder/repositories/equity_pledge_repo.py (FOUND)
- stockvaluefinder/stockvaluefinder/models/risk.py (FOUND, extended)
- stockvaluefinder/stockvaluefinder/repositories/risk_repo.py (FOUND, extended)

Commits verified in git log:
- cae3449 (FOUND)
- 50d9962 (FOUND)
