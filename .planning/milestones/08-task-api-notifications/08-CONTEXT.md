# Phase 8: Task API, Notifications & Sandbox - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

## Phase Boundary

Users can monitor pipeline status, trigger processing manually, receive real-time completion notifications via SSE, and calculations run in an isolated subprocess with resource limits. This is the final phase of the v1.1 milestone.

## Implementation Decisions

### SSE Event Design

- **D-01:** Redis-backed event log for SSE reconnect replay. Store last 100 events in Redis list with configurable TTL. Client reconnects with Last-Event-ID header to get missed events.
- **D-02:** 3 event types: task_created (new task enqueued), task_completed (DONE state), task_failed (FAILED state). Each carries task_id, ticker, business_key, state, timestamp.

### Manual Trigger API

- **D-03:** POST /api/v1/pipeline/trigger accepts {ticker, fiscal_year?, report_type?}. If fiscal_year/report_type omitted, processes latest available.
- **D-04:** By default, dedup blocks reprocessing existing DONE tasks. Add force=true query param to bypass dedup and re-download/re-analyze. Returns the new task_id.
- **D-05:** Trigger queues a download_report job directly — full pipeline from download → parse → analyze. If ticker not in watchlist, auto-add it first.

### Sandbox Subprocess Design

- **D-06:** Python subprocess.run() with timeout (default 30s) and resource limits (via resource module on Linux). Receives JSON via stdin, returns JSON via stdout.
- **D-07:** Optional — sandbox is an enhancement. Pipeline works without it (in-process execution as today). Config flag enables/disables. Graceful fallback.

### Pipeline Status Endpoint

- **D-08:** GET /api/v1/pipeline/status returns per-state counts (pending, downloading, parsing, analyzing, done, failed), last_poll_time from watcher_state, next_poll_time (computed from schedule), total_tasks.

### Claude's Discretion

- SSE endpoint implementation details (FastAPI StreamingResponse)
- Event ID format and Redis key structure
- Subprocess JSON protocol (input/output schema)
- Task listing query optimization (pagination, filtering)
- Resource limit configuration details
- CalculationSandboxService class structure

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §TASK — TASK-01 through TASK-05
- `.planning/REQUIREMENTS.md` §SBOX — SBOX-01 through SBOX-04

### Prior Phase Context
- `.planning/phases/05-pipeline-foundation/05-CONTEXT.md` — Pipeline infrastructure
- `.planning/phases/05-pipeline-foundation/05-02-SUMMARY.md` — Worker stubs, state machine
- `.planning/phases/06-smart-watcher/06-CONTEXT.md` — Watcher service decisions
- `.planning/phases/07-report-processing/07-CONTEXT.md` — Report processing decisions

### Existing Code
- `stockvaluefinder/stockvaluefinder/api/pipeline_routes.py` — Health endpoint + watchlist CRUD
- `stockvaluefinder/stockvaluefinder/pipeline/worker.py` — download_report, parse_report, analyze_report
- `stockvaluefinder/stockvaluefinder/pipeline/repo.py` — PipelineTaskRepository
- `stockvaluefinder/stockvaluefinder/pipeline/config.py` — PipelineConfig
- `stockvaluefinder/stockvaluefinder/pipeline/watcher.py` — WatcherService
- `stockvaluefinder/stockvaluefinder/services/calculation_sandbox.py` — Existing stub

## Existing Code Insights

### Reusable Assets
- **PipelineTaskRepository**: get_by_id, transition_state, create_task with business_key
- **PipelineState**: 6 states with VALID_TRANSITIONS
- **ApiResponse[T]**: Standard response envelope
- **WorkerSettings**: arq worker with cron_jobs and functions
- **Redis CacheManager**: `stockvaluefinder/utils/cache.py` — existing Redis integration
- **pipeline_routes.py**: Already has health + watchlist endpoints — add more here

### Integration Points
- **pipeline_routes.py**: Add status, tasks, trigger, events endpoints
- **worker.py**: Emit SSE events on state transitions (task_created, task_completed, task_failed)
- **pipeline/repo.py**: Add aggregate query methods for status endpoint
- **services/calculation_sandbox.py**: Replace existing stub with subprocess implementation
- **pipeline/config.py**: Add sandbox_enabled, sandbox_timeout fields

## Deferred Ideas

- Webhook notification (DingTalk, WeChat Server酱) — future milestone
- Batch CSI 300 screening — future milestone
- Separate DB users for worker vs API — future milestone

---

*Phase: 08-task-api-notifications*
*Context gathered: 2026-05-02*
