# Phase 5: Pipeline Foundation - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

## Phase Boundary

Build the pipeline infrastructure: arq worker connects to Redis, state machine transitions are persisted to PostgreSQL, and a health-check endpoint confirms all subsystems are alive. This phase creates the foundation that Phase 6 (Smart Watcher), Phase 7 (Report Processing), and Phase 8 (Task API & Notifications) build upon. No actual report downloading or analysis happens here — just the infrastructure skeleton.

## Implementation Decisions

### Task Granularity

- **D-01:** One job per state — each pipeline stage (download, parse, analyze) is a separate arq job. The previous job enqueues the next on success. Failed jobs retry independently via arq's built-in `max_tries` and `Retry(defer=N)`.
- **D-02:** Job function signatures: `async def download_report(ctx, task_id: str)`, `async def parse_report(ctx, task_id: str)`, `async def analyze_report(ctx, task_id: str)`. Each reads task state from PostgreSQL, performs its stage, updates state, and enqueues the next job.

### Worker Deployment

- **D-03:** Separate process — arq worker runs as independent process alongside FastAPI. FastAPI holds an ArqRedis pool (for enqueuing only) via `app.state.arq_pool`. The worker process is started with `arq stockvaluefinder.pipeline.worker.WorkerSettings`.
- **D-04:** Worker `on_startup` initializes: httpx.AsyncClient (shared across jobs), async SQLAlchemy session factory, Redis connection. All stored in `ctx` dict for job functions to access.

### Crash Recovery

- **D-05:** Auto-reaper via arq cron job. A `reap_stuck_tasks` cron function scans for tasks stuck in DOWNLOADING/PARSING/ANALYZING states beyond a configurable timeout.
- **D-06:** Stuck tasks are reset to PENDING with `retry_count` increment. Tasks exceeding `max_retries` (configurable, default 3) transition to FAILED permanently.
- **D-07:** Timeout is configurable via `PipelineConfig.stuck_timeout_minutes` (default 30 minutes). Reaper runs every 5 minutes via cron.

### DB Schema

- **D-08:** Two tables: `pipeline_tasks` (state machine tracking) and `pipeline_documents` (download metadata).
- **D-09:** `pipeline_tasks` columns: task_id (UUID PK), ticker (FK to stocks), business_key (unique: ticker:fiscal_year:report_type), state (PipelineState enum), current_stage (str), retry_count (int), max_retries (int), error_message (text), result_summary (JSONB), created_at, updated_at. No source_id or content_hash here — those belong on pipeline_documents.
- **D-10:** `pipeline_documents` columns: document_id (UUID PK), task_id (FK to pipeline_tasks), source_url (text), source_id (str, for announcement dedup), content_hash (str, SHA256), file_path (str), file_size (bigint), downloaded_at. Document records persist across task retries.
- **D-11:** Both tables created via a single new Alembic migration. No changes to existing tables.

### Configuration

- **D-12:** `PipelineConfig` is a frozen dataclass (matching existing pattern: ValuationConfig, RiskConfig, YieldConfig). Controls: polling schedule, rate limits, retry policy, concurrency limits, stuck timeout, watchlist scope. All fields have sensible defaults.
- **D-13:** Stored at `stockvaluefinder/pipeline/config.py` following project convention.

### State Machine

- **D-14:** Custom `PipelineState(StrEnum)` with 5 states: PENDING, DOWNLOADING, PARSING, ANALYZING, DONE, FAILED. Valid transitions defined as `dict[PipelineState, frozenset[PipelineState]]` — no library.
- **D-15:** Each state transition is atomic: validate transition → update state + timestamp + error detail in single DB transaction. Invalid transitions raise `StateTransitionError` (new exception extending `StockValueFinderError`).

### Health Check

- **D-16:** `GET /api/v1/pipeline/health` returns 200 with component statuses: watcher (future — always "not_configured" in Phase 5), worker (check Redis queue responsiveness), redis (PING), postgresql (SELECT 1). Returns "degraded" when any component is down, "healthy" when all are up.

### Claude's Discretion

- Exact Alembic migration file naming and structure
- Health endpoint response schema details
- Worker startup/shutdown hook implementation details
- Logging format and verbosity for pipeline operations
- Error message formatting in task records

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Stack and Architecture
- `.planning/research/STACK.md` — arq integration patterns, WorkerSettings class structure, Redis configuration, state machine code samples, FastAPI lifespan integration
- `.planning/research/FEATURES.md` — Feature dependency graph, table stakes vs differentiators
- `.planning/research/ARCHITECTURE.md` — Component integration details, build order

### Project Context
- `.planning/PROJECT.md` — Current milestone goals, architecture pattern, key decisions
- `.planning/REQUIREMENTS.md` — CONF-01 to CONF-04, PIPE-04 to PIPE-06 (Phase 5 requirements)
- `.planning/ROADMAP.md` §Phase 5 — Success criteria (5 items)

### Reference PRDs
- `doc/auto_download_fincialreport/auto_download_fincialreport-prd.md` — Original product requirements for the pipeline
- `doc/auto_download_fincialreport/README.md` — Technical implementation suggestions

## Existing Code Insights

### Reusable Assets

- **Frozen config pattern**: `stockvaluefinder/config.py` — `ValuationConfig`, `RiskConfig`, `YieldConfig` are all `frozen=True` dataclasses. `PipelineConfig` follows same pattern.
- **FastAPI lifespan**: `stockvaluefinder/main.py` — Already initializes Redis cache, Qdrant health, DB engine. Extend with Arq pool initialization.
- **Base repository**: `stockvaluefinder/repositories/base.py` — Generic `BaseRepository[ModelType, CreateSchemaType, UpdateSchemaType]` with async CRUD. New pipeline repos can extend this.
- **Error hierarchy**: `stockvaluefinder/utils/errors.py` — `StockValueFinderError` base with `DataValidationError`, `CalculationError`, `ExternalAPIError`, `CacheError`. Add `StateTransitionError`.
- **Redis CacheManager**: `stockvaluefinder/utils/cache.py` — Existing Redis connection and config. Arq uses same Redis instance, different DB or namespace.

### Established Patterns

- **Frozen dataclass config**: All configs are `frozen=True` with sensible defaults and `__post_init__` validation.
- **StrEnum for categorization**: RiskLevel, ValuationLevel, Market all use `StrEnum`. PipelineState follows suit.
- **ApiResponse[T] envelope**: All API endpoints return generic envelope. Health endpoint should follow this pattern.
- **Alembic migrations**: 8 existing migrations in `alembic/versions/`. New migration for pipeline tables.
- **Absolute imports**: All imports use `from stockvaluefinder.xxx import Yyy` pattern.

### Integration Points

- **main.py lifespan**: Add `arq_pool = await create_pool(RedisSettings())` after existing Redis init, store on `app.state.arq_pool`.
- **db/models/**: New `pipeline_task.py` and `pipeline_document.py` ORM models alongside existing 8 models.
- **alembic/versions/**: New migration file for pipeline tables.
- **api/**: New route file `pipeline_routes.py` with health endpoint.
- **New module**: `stockvaluefinder/pipeline/` directory with `config.py`, `state.py`, `worker.py`, `models.py`.

## Deferred Ideas

- Actual job implementations (download_report, parse_report, analyze_report) — Phase 7
- Watcher and cron scheduling — Phase 6
- SSE notifications — Phase 8
- Manual trigger endpoint — Phase 8
- Subprocess sandbox — Phase 8

---

*Phase: 05-pipeline-foundation*
*Context gathered: 2026-05-01*
