# Phase 6: Smart Watcher - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

## Phase Boundary

The system automatically discovers newly disclosed A-share financial reports and enqueues processing jobs without any manual intervention. This phase builds the watcher service, watchlist management API, and season-aware polling logic on top of the Phase 5 pipeline infrastructure. Actual report downloading and analysis happen in Phase 7.

## Implementation Decisions

### Disclosure Source Strategy

- **D-01:** Primary source: AKShare `stock_report_disclosure` API. Fallback: CNInfo (巨潮信息网) announcement API via HTTP when AKShare fails or returns stale data.
- **D-02:** Immediate CNInfo fallback in the same poll cycle when AKShare fails — no separate retry cycle needed.
- **D-03:** Monitor all report types: annual (年报), semi-annual (半年报), Q1 quarterly (一季报), Q3 quarterly (三季报).
- **D-04:** Construct business_key from poll data as `ticker:fiscal_year:report_type` for deduplication. Matches existing pipeline_tasks unique constraint.
- **D-05:** Reprocess amended reports — when a company re-submits a corrected report for the same fiscal year, create a new pipeline task.
- **D-06:** Detect amendments by comparing disclosure_date per business_key. If a new poll shows a later disclosure_date for an existing business_key, it's an amendment.

### Season-Aware Polling Schedule

- **D-07:** Month-based season detection via PipelineConfig fields: `high_season_months` (default Jan-Apr) and corresponding cron schedules.
- **D-08:** High season: daily at 09:00 CST (China Standard Time). Off-season: weekly Monday at 09:00 CST.
- **D-09:** Add `high_season_cron`, `off_season_cron`, `high_season_months` fields to PipelineConfig. The watcher cron checks current month and selects appropriate schedule.

### New Report Detection Logic

- **D-10:** Check pipeline_tasks table for existing business_key. If not found → new report. Simple SQL lookup on unique constraint.
- **D-11:** Two-phase architecture: poll cron writes disclosures to a `pending_disclosures` staging table. A separate worker job processes the staging table, detects new vs. amendment, and enqueues download jobs.
- **D-12:** Enqueue one arq job per new disclosure. Each job creates a pipeline task and processes independently.

### Watchlist Management

- **D-13:** New `watchlist` table in PostgreSQL: ticker (PK), name, added_at, is_active. User adds/removes via REST API.
- **D-14:** Empty by default — user must explicitly add stocks via API. No auto-seeding.
- **D-15:** Dedicated watchlist endpoints: POST /api/v1/pipeline/watchlist (add), GET (list), DELETE (remove). New Alembic migration 010.
- **D-16:** New `watcher_state` table: watcher_id, last_poll_time, last_akshare_success, last_cninfo_fallback, polls_count, errors_count. Updated each poll cycle.
- **D-17:** Single Alembic migration 010 for both watchlist and watcher_state tables. Keeps Phase 6 DB changes atomic.

### Claude's Discretion

- Exact AKShare client method signatures for `stock_report_disclosure` and `index_stock_cons`
- CNInfo HTTP client implementation details (URL, headers, parsing)
- Staging table schema for pending_disclosures
- Watcher service class structure and error handling
- Logging format and verbosity for watcher operations

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Stack and Architecture
- `.planning/research/STACK.md` — arq integration patterns, WorkerSettings class structure, cron job patterns
- `.planning/REQUIREMENTS.md` §WATCH — WATCH-01 through WATCH-05 requirements
- `.planning/ROADMAP.md` §Phase 6 — Success criteria (5 items)

### Prior Phase Context
- `.planning/phases/05-pipeline-foundation/05-CONTEXT.md` — Pipeline foundation decisions (task granularity, worker deployment, crash recovery, DB schema, state machine)
- `.planning/phases/05-pipeline-foundation/05-01-SUMMARY.md` — PipelineConfig, PipelineState, ORM models, migration 009 details
- `.planning/phases/05-pipeline-foundation/05-02-SUMMARY.md` — WorkerSettings, stub jobs, reaper cron, repo methods

### Product Requirements
- `doc/auto_download_fincialreport/auto_download_fincialreport-prd.md` — Smart Sync & Audit Pipeline PRD, Smart Watcher section (§4.1)

### Existing Code
- `stockvaluefinder/stockvaluefinder/pipeline/config.py` — Current PipelineConfig (needs new fields)
- `stockvaluefinder/stockvaluefinder/pipeline/worker.py` — Current WorkerSettings (needs watcher cron)
- `stockvaluefinder/stockvaluefinder/pipeline/repo.py` — PipelineTaskRepository (create_task for enqueuing)
- `stockvaluefinder/stockvaluefinder/external/akshare_client.py` — Existing AKShare client (needs new methods)

## Existing Code Insights

### Reusable Assets

- **PipelineConfig frozen dataclass**: `stockvaluefinder/pipeline/config.py` — Add `high_season_months`, `high_season_cron`, `off_season_cron` fields following existing pattern.
- **WorkerSettings**: `stockvaluefinder/pipeline/worker.py` — Add `watch_disclosures` cron job alongside existing `reap_stuck_tasks`.
- **PipelineTaskRepository**: `stockvaluefinder/pipeline/repo.py` — `create_task()` with business_key unique constraint handles new task creation and dedup.
- **AKShareClient**: `stockvaluefinder/external/akshare_client.py` — Add `get_report_disclosures()` and `get_index_constituents()` methods following existing pattern.
- **Alembic migrations**: `stockvaluefinder/alembic/versions/` — 9 existing migrations. Migration 010 for new tables.
- **API routes pattern**: `stockvaluefinder/api/pipeline_routes.py` — Add watchlist CRUD endpoints following existing ApiResponse[T] pattern.

### Established Patterns

- **Frozen dataclass config**: All configs `frozen=True` with `__post_init__` validation.
- **Repository pattern**: Standalone or extending BaseRepository with async SQLAlchemy sessions.
- **API response envelope**: `ApiResponse[T]` for all endpoints.
- **arq cron_jobs**: Uses `arq.cron()` wrapper with scheduling parameters in WorkerSettings.

### Integration Points

- **PipelineConfig**: Add new polling fields — extends existing frozen dataclass.
- **WorkerSettings.cron_jobs**: Add `watch_disclosures` cron alongside `reap_stuck_tasks`.
- **WorkerSettings.functions**: Add `process_disclosures` as a regular job function.
- **pipeline_routes.py**: Add watchlist CRUD endpoints.
- **akshare_client.py**: Add disclosure schedule and index constituent methods.
- **New tables**: `watchlist`, `watcher_state`, `pending_disclosures` via migration 010.
- **New module**: `stockvaluefinder/pipeline/watcher.py` — WatcherService class.

## Deferred Ideas

- HKEX (披露易) monitoring for Hong Kong stocks — future milestone
- Multi-market watcher abstraction — future milestone
- Batch import via Excel/text file — nice-to-have, single-add API sufficient for MVP
- Watchlist groups/tags — not needed for MVP

---

*Phase: 06-smart-watcher*
*Context gathered: 2026-05-01*
