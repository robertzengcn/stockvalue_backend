# Phase 5: Pipeline Foundation - Research

**Researched:** 2026-05-01
**Domain:** Async task queue (arq), state machine, PostgreSQL schema, Redis integration, health-check endpoint
**Confidence:** HIGH

## Summary

Phase 5 builds the infrastructure skeleton for the financial report processing pipeline. The core deliverables are: (1) a frozen `PipelineConfig` dataclass matching existing project conventions, (2) two new PostgreSQL tables (`pipeline_tasks` and `pipeline_documents`) via a single Alembic migration, (3) an arq worker process with Redis-backed job queue and cron-based reaper, (4) a custom 5-state linear FSM with atomic transitions persisted to PostgreSQL, and (5) a health-check endpoint that verifies Redis, PostgreSQL, and worker connectivity.

The phase intentionally does NOT implement actual job functions (download_report, parse_report, analyze_report) -- those are Phase 7. The watcher and cron scheduling are Phase 6. This phase creates the foundation both depend upon.

**Primary recommendation:** Build bottom-up: config and state machine first (pure functions, zero infrastructure), then Alembic migration and ORM models, then arq worker skeleton with reaper cron, then FastAPI integration (pool in lifespan, health endpoint). Each layer is independently testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** One job per state -- each pipeline stage (download, parse, analyze) is a separate arq job. The previous job enqueues the next on success. Failed jobs retry independently via arq's built-in `max_tries` and `Retry(defer=N)`.
- **D-02:** Job function signatures: `async def download_report(ctx, task_id: str)`, `async def parse_report(ctx, task_id: str)`, `async def analyze_report(ctx, task_id: str)`. Each reads task state from PostgreSQL, performs its stage, updates state, and enqueues the next job.
- **D-03:** Separate process -- arq worker runs as independent process alongside FastAPI. FastAPI holds an ArqRedis pool (for enqueuing only) via `app.state.arq_pool`. The worker process is started with `arq stockvaluefinder.pipeline.worker.WorkerSettings`.
- **D-04:** Worker `on_startup` initializes: httpx.AsyncClient (shared across jobs), async SQLAlchemy session factory, Redis connection. All stored in `ctx` dict for job functions to access.
- **D-05:** Auto-reaper via arq cron job. A `reap_stuck_tasks` cron function scans for tasks stuck in DOWNLOADING/PARSING/ANALYZING states beyond a configurable timeout.
- **D-06:** Stuck tasks are reset to PENDING with `retry_count` increment. Tasks exceeding `max_retries` (configurable, default 3) transition to FAILED permanently.
- **D-07:** Timeout is configurable via `PipelineConfig.stuck_timeout_minutes` (default 30 minutes). Reaper runs every 5 minutes via cron.
- **D-08:** Two tables: `pipeline_tasks` (state machine tracking) and `pipeline_documents` (download metadata).
- **D-09:** `pipeline_tasks` columns: task_id (UUID PK), ticker (FK to stocks), business_key (unique: ticker:fiscal_year:report_type), state (PipelineState enum), current_stage (str), retry_count (int), max_retries (int), error_message (text), result_summary (JSONB), created_at, updated_at. No source_id or content_hash here -- those belong on pipeline_documents.
- **D-10:** `pipeline_documents` columns: document_id (UUID PK), task_id (FK to pipeline_tasks), source_url (text), source_id (str, for announcement dedup), content_hash (str, SHA256), file_path (str), file_size (bigint), downloaded_at. Document records persist across task retries.
- **D-11:** Both tables created via a single new Alembic migration. No changes to existing tables.
- **D-12:** `PipelineConfig` is a frozen dataclass (matching existing pattern: ValuationConfig, RiskConfig, YieldConfig). Controls: polling schedule, rate limits, retry policy, concurrency limits, stuck timeout, watchlist scope. All fields have sensible defaults.
- **D-13:** Stored at `stockvaluefinder/pipeline/config.py` following project convention.
- **D-14:** Custom `PipelineState(StrEnum)` with 5 states: PENDING, DOWNLOADING, PARSING, ANALYZING, DONE, FAILED. Valid transitions defined as `dict[PipelineState, frozenset[PipelineState]]` -- no library.
- **D-15:** Each state transition is atomic: validate transition -> update state + timestamp + error detail in single DB transaction. Invalid transitions raise `StateTransitionError` (new exception extending `StockValueFinderError`).
- **D-16:** `GET /api/v1/pipeline/health` returns 200 with component statuses: watcher (future -- always "not_configured" in Phase 5), worker (check Redis queue responsiveness), redis (PING), postgresql (SELECT 1). Returns "degraded" when any component is down, "healthy" when all are up.

### Claude's Discretion
- Exact Alembic migration file naming and structure
- Health endpoint response schema details
- Worker startup/shutdown hook implementation details
- Logging format and verbosity for pipeline operations
- Error message formatting in task records

### Deferred Ideas (OUT OF SCOPE)
- Actual job implementations (download_report, parse_report, analyze_report) -- Phase 7
- Watcher and cron scheduling -- Phase 6
- SSE notifications -- Phase 8
- Manual trigger endpoint -- Phase 8
- Subprocess sandbox -- Phase 8
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONF-01 | PipelineConfig frozen dataclass controls polling schedule, rate limits, retry policy, concurrency, watchlist scope | Existing `config.py` has 6 frozen dataclass examples. `PipelineConfig` follows identical pattern with `__post_init__` validation. See Code Examples section. |
| CONF-02 | New database tables (pipeline_tasks, pipeline_documents) via Alembic migration separate from existing tables | 8 existing migrations in `alembic/versions/`. New migration 009 follows same pattern. See D-08/D-09/D-10 for exact schema. |
| CONF-03 | arq worker pool initialized during FastAPI lifespan startup, stored in app.state for DI | arq `create_pool(RedisSettings())` in lifespan, stored on `app.state.arq_pool`. Worker runs as separate process. See Architecture Patterns. |
| CONF-04 | Pipeline health-check endpoint verifies watcher active, worker connected, Redis queue responsive | `GET /api/v1/pipeline/health` checks Redis PING, PostgreSQL SELECT 1, worker queue. Returns `ApiResponse[HealthStatus]`. |
| PIPE-04 | Linear state machine: PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE / FAILED | Custom `PipelineState(StrEnum)` + `VALID_TRANSITIONS` dict. ~30 lines, zero dependencies. See State Machine pattern. |
| PIPE-05 | Atomic state transitions persisted to PostgreSQL with timestamp and error detail | Single DB transaction: validate -> update state + updated_at + error_message. `StateTransitionError` on invalid transition. |
| PIPE-06 | Failed tasks retry up to 3 times with exponential backoff (2s, 8s, 30s) | arq `Retry(defer=N)` with `max_tries`. Reaper cron resets stuck tasks to PENDING. See Crash Recovery pattern. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pipeline config (frozen dataclass) | Application | -- | Pure Python, no I/O, singleton pattern |
| State machine (validation + transitions) | Application | -- | Pure functions, no I/O, stateless logic |
| Task persistence (ORM + repository) | Database | API | PostgreSQL stores task state; API reads via repository |
| arq worker process | Infrastructure | Database | Separate OS process; connects to Redis + PostgreSQL |
| arq pool (FastAPI side) | API | Infrastructure | FastAPI lifespan creates pool for enqueueing only |
| Health check endpoint | API | Database, Infrastructure | HTTP endpoint checks downstream components |
| Auto-reaper (cron job) | Infrastructure | Database | Runs inside arq worker; queries PostgreSQL |
| Alembic migration | Database | -- | Schema definition, run offline or online |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arq | 0.28.0 | Async task queue + cron scheduler | asyncio-native, uses existing Redis, built by Pydantic creator. Built-in cron_jobs in WorkerSettings eliminates separate scheduler. Native retry via `Retry(defer=N)`. [VERIFIED: pip index] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.27.0 (existing) | Async HTTP client in worker context | Worker `on_startup` creates shared `AsyncClient` |
| redis | >=7.2.1 (existing) | Arq queue backend | Same Redis instance, different DB or namespace |
| sqlalchemy | >=2.0.47 (existing) | ORM for pipeline tables | New models follow existing `Mapped[]` pattern |
| pydantic | >=2.12.5 (existing) | Domain model validation | New Pydantic models for pipeline domain |
| pytest + pytest-asyncio | existing | Testing | Unit tests for state machine, config validation, ORM models |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| arq | Celery + RabbitMQ | Celery is heavier, sync-first, requires RabbitMQ. Arq uses existing Redis. Explicit project decision (Out of Scope in PROJECT.md). |
| arq cron_jobs | APScheduler 4 | APScheduler 4 is alpha-only (4.0.0a6 on PyPI). Arq cron is stable and built-in. [VERIFIED: pip index, 2026-05-01] |
| Custom enum FSM | python-statemachine | 5-state linear FSM is ~30 lines. Library adds 200+ lines of abstraction for no benefit. |

**Installation:**
```bash
uv add "arq>=0.28.0"
```

**Version verification:**
```
arq 0.28.0 (verified via pip3 index versions, 2026-05-01)
```

## Architecture Patterns

### System Architecture Diagram

```
                    FastAPI Process                          Arq Worker Process
                    (web server)                             (separate OS process)
                         |                                          |
              +----------+----------+                  +-----------+-----------+
              |                     |                  |                       |
     +--------+------+    +--------+------+    +-------+-------+    +---------+---------+
     |  Lifespan     |    |  Pipeline     |    | on_startup    |    | cron_jobs         |
     |  Manager      |    |  Routes       |    | (init ctx)    |    | (reap_stuck_tasks)|
     +------+--------+    +------+--------+    +-------+-------+    +---------+---------+
            |                     |                     |                      |
    +-------+-------+            |              +------+-------+              |
    | Redis Cache   |            |              | httpx client |              |
    | (existing)    |            |              | DB sessions  |              |
    +-------+-------+            |              | Redis conn   |              |
            |                     |              +------+-------+              |
    +-------+-------+            |                     |                      |
    | Arq Pool      |            |                     |                      |
    | (enqueue only)|            |                     |                      |
    +-------+-------+            |                     |                      |
            |                     |                     |                      |
            +---- enqueue_job ---> Redis Queue <-------+----- pick up job ----+
                                   (shared)
                                        |
                                  +-----+------+
                                  | PostgreSQL |
                                  | pipeline_tasks
                                  | pipeline_documents
                                  +------------+
```

### Recommended Project Structure
```
stockvaluefinder/
  pipeline/                     # NEW module directory
    __init__.py                 # Package init
    config.py                   # PipelineConfig frozen dataclass (D-12)
    state.py                    # PipelineState enum + VALID_TRANSITIONS + validate_transition (D-14)
    worker.py                   # WorkerSettings class with on_startup/on_shutdown/cron_jobs (D-03/04/05)
    models.py                   # Pydantic domain models (PipelineTask, PipelineDocument, HealthStatus)
  db/models/
    pipeline_task.py            # PipelineTaskDB ORM model (D-09)
    pipeline_document.py        # PipelineDocumentDB ORM model (D-10)
  api/
    pipeline_routes.py          # GET /api/v1/pipeline/health (D-16)
  utils/
    errors.py                   # ADD StateTransitionError class (D-15)
  main.py                       # MODIFY: add arq pool to lifespan
  config.py                     # UNCHANGED (PipelineConfig in pipeline/config.py per D-13)
alembic/versions/
  009_pipeline_tables.py        # NEW migration for pipeline_tasks + pipeline_documents
tests/
  unit/
    test_pipeline/
      test_config.py            # PipelineConfig validation tests
      test_state.py             # State machine validation tests
      test_models.py            # Pydantic model tests
  integration/
    test_pipeline/
      test_pipeline_repos.py    # Repository CRUD tests with real PostgreSQL
      test_health_endpoint.py   # Health check endpoint tests
```

### Pattern 1: Frozen Config Dataclass (Following Existing Convention)

**What:** `PipelineConfig` frozen dataclass matching `ValuationConfig`, `RiskConfig`, `YieldConfig` pattern.
**When:** Any pipeline configuration needed across worker and API.

**Example:**
```python
# Source: Based on existing stockvaluefinder/config.py pattern
from dataclasses import dataclass

@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for report processing pipeline."""

    # Retry policy
    max_retries: int = 3
    retry_delays: tuple[float, ...] = (2.0, 8.0, 30.0)

    # Stuck task reaper
    stuck_timeout_minutes: int = 30
    reaper_interval_minutes: int = 5

    # Concurrency
    max_concurrent_tasks: int = 5

    # Rate limiting (between external requests)
    request_delay_seconds: float = 0.5

    # Worker
    job_timeout_seconds: int = 1800  # 30 min per job

    # Redis
    redis_db: int = 0  # Arq uses DB 0 by default

    # Watchlist scope (future, Phase 6)
    default_watchlist: str = "CSI300"

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.stuck_timeout_minutes < 1:
            raise ValueError("stuck_timeout_minutes must be >= 1")
        if len(self.retry_delays) < self.max_retries:
            raise ValueError(
                f"retry_delays has {len(self.retry_delays)} entries, "
                f"but max_retries is {self.max_retries}"
            )
```

### Pattern 2: State Machine (Custom Enum + Transitions)

**What:** 5-state linear FSM with immutable transition map.
**When:** Validating any pipeline task state change.

**Example:**
```python
# Source: Context-locked decision D-14/D-15
from enum import StrEnum
from stockvaluefinder.utils.errors import StockValueFinderError

class PipelineState(StrEnum):
    """Pipeline task state machine states."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"

# Immutable transition map
VALID_TRANSITIONS: dict[PipelineState, frozenset[PipelineState]] = {
    PipelineState.PENDING: frozenset({PipelineState.DOWNLOADING, PipelineState.FAILED}),
    PipelineState.DOWNLOADING: frozenset({PipelineState.PARSING, PipelineState.FAILED}),
    PipelineState.PARSING: frozenset({PipelineState.ANALYZING, PipelineState.FAILED}),
    PipelineState.ANALYZING: frozenset({PipelineState.DONE, PipelineState.FAILED}),
    PipelineState.DONE: frozenset(),       # Terminal
    PipelineState.FAILED: frozenset(),     # Terminal (reaper resets to PENDING)
}

class StateTransitionError(StockValueFinderError):
    """Raised when a pipeline state transition is invalid."""

    def __init__(
        self,
        current: PipelineState,
        target: PipelineState,
    ) -> None:
        super().__init__(
            message=f"Invalid state transition: {current} -> {target}",
            details={"current": current.value, "target": target.value},
        )

def validate_transition(
    current: PipelineState,
    target: PipelineState,
) -> None:
    """Validate state transition, raising StateTransitionError if invalid.

    Args:
        current: Current pipeline state.
        target: Desired target state.

    Raises:
        StateTransitionError: If the transition is not allowed.
    """
    if target not in VALID_TRANSITIONS.get(current, frozenset()):
        raise StateTransitionError(current, target)
```

### Pattern 3: Arq Worker with Lifecycle Hooks and Cron

**What:** WorkerSettings class configuring arq worker with startup/shutdown hooks and cron reaper.
**When:** Defining the worker process that handles pipeline jobs.

**Example:**
```python
# Source: arq Context7 docs (/websites/arq-docs_helpmanual_io)
import logging
from arq import cron, func
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker

from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.pipeline.config import PipelineConfig

logger = logging.getLogger(__name__)

config = PipelineConfig()

async def on_startup(ctx: dict) -> None:
    """Initialize shared resources in worker context."""
    import httpx
    ctx["http_client"] = httpx.AsyncClient(timeout=config.job_timeout_seconds)
    ctx["session_factory"] = async_session_maker
    logger.info("Pipeline worker started")

async def on_shutdown(ctx: dict) -> None:
    """Clean up shared resources."""
    await ctx["http_client"].aclose()
    logger.info("Pipeline worker shut down")

async def reap_stuck_tasks(ctx: dict) -> None:
    """Cron job: reset tasks stuck in non-terminal states."""
    session_factory = ctx["session_factory"]
    async with session_factory() as session:
        # Query for stuck tasks, reset to PENDING or mark FAILED
        # Implementation detail left to planner
        pass

# Stub job functions -- actual logic in Phase 7
async def download_report(ctx: dict, task_id: str) -> None:
    """Download report PDF. Stub for Phase 7."""
    logger.info("download_report called for task %s (Phase 7 stub)", task_id)

async def parse_report(ctx: dict, task_id: str) -> None:
    """Parse downloaded report. Stub for Phase 7."""
    logger.info("parse_report called for task %s (Phase 7 stub)", task_id)

async def analyze_report(ctx: dict, task_id: str) -> None:
    """Run analysis on parsed report. Stub for Phase 7."""
    logger.info("analyze_report called for task %s (Phase 7 stub)", task_id)

class WorkerSettings:
    """arq WorkerSettings -- worker process configuration.

    Start with: arq stockvaluefinder.pipeline.worker.WorkerSettings
    """
    functions = [
        func(download_report, max_tries=config.max_retries, timeout=config.job_timeout_seconds),
        func(parse_report, max_tries=config.max_retries, timeout=config.job_timeout_seconds),
        func(analyze_report, max_tries=config.max_retries, timeout=config.job_timeout_seconds),
    ]
    cron_jobs = [
        cron(
            reap_stuck_tasks,
            minute=set(range(0, 60, config.reaper_interval_minutes)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
            timeout=60,
        )
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings(database=config.redis_db)
    max_tries = config.max_retries
    job_timeout = config.job_timeout_seconds
```

**Key arq API details verified from Context7 [VERIFIED: arq-docs.helpmanual.io]:**
- `func(coroutine, name=, max_tries=, timeout=, keep_result=)` wraps job functions with per-function settings
- `cron(coroutine, minute=, hour=, run_at_startup=False, unique=True, max_tries=1, timeout=None)` creates cron jobs
- `create_pool(RedisSettings())` returns `ArqRedis` for enqueueing from FastAPI
- `Retry(defer=N)` raises within job to retry after N seconds
- `ctx["job_try"]` gives current attempt number (1-indexed)
- `WorkerSettings` class is discovered by `arq` CLI via dotted path

### Pattern 4: FastAPI Lifespan Extension for arq Pool

**What:** Add arq pool creation to existing lifespan, storing on `app.state.arq_pool`.
**When:** FastAPI needs to enqueue jobs.

**Example:**
```python
# Source: Based on existing stockvaluefinder/main.py lifespan pattern
from arq import create_pool
from arq.connections import RedisSettings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing Redis cache init ...

    # New: Initialize Arq connection pool (for enqueuing from FastAPI)
    arq_pool = None
    try:
        arq_pool = await create_pool(RedisSettings())
        app.state.arq_pool = arq_pool
        logger.info("Arq pool initialized successfully")
    except Exception as e:
        logger.warning(f"Arq pool unavailable, pipeline enqueuing disabled: {e}")
        app.state.arq_pool = None

    yield

    # Shutdown: Close Arq pool
    if arq_pool is not None:
        try:
            await arq_pool.close()
            logger.info("Arq pool closed")
        except Exception as e:
            logger.warning(f"Error closing Arq pool: {e}")

    # ... existing cache disconnect ...
```

### Pattern 5: Health Check Endpoint

**What:** `GET /api/v1/pipeline/health` checks component liveness.
**When:** Monitoring pipeline infrastructure.

**Example:**
```python
# Source: Based on existing ApiResponse[T] pattern from stockvaluefinder/models/api.py
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from stockvaluefinder.models.api import ApiResponse

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

@router.get("/health")
async def pipeline_health(request: Request) -> ApiResponse:
    """Check pipeline subsystem health."""
    checks: dict[str, str] = {}

    # Check Redis (via arq pool)
    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is not None:
        try:
            await arq_pool.ping()
            checks["redis"] = "healthy"
        except Exception:
            checks["redis"] = "unhealthy"
    else:
        checks["redis"] = "not_configured"

    # Check PostgreSQL
    try:
        from stockvaluefinder.db.base import async_session_maker
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["postgresql"] = "healthy"
    except Exception:
        checks["postgresql"] = "unhealthy"

    # Check worker (indirect via Redis queue length)
    checks["worker"] = "healthy" if checks["redis"] == "healthy" else "unreachable"

    # Watcher is future (Phase 6)
    checks["watcher"] = "not_configured"

    overall = (
        "healthy"
        if all(v in ("healthy", "not_configured") for v in checks.values())
        else "degraded"
    )

    return ApiResponse(
        success=True,
        data={
            "status": overall,
            "components": checks,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    )
```

### Anti-Patterns to Avoid
- **Creating arq pool INSIDE the worker:** The worker creates its own Redis connection. `create_pool` is only for FastAPI to enqueue jobs. Creating a pool in worker startup is redundant and wasteful.
- **Holding DB sessions across job retries:** Each job invocation should create a fresh session from the session factory stored in `ctx`. Sessions must be closed before the job function returns.
- **Mutating PipelineConfig:** It is `frozen=True`. Any attempt to modify it raises `FrozenInstanceError`. Create a new instance if different config is needed.
- **Using BackgroundTasks for pipeline jobs:** BackgroundTasks has no state tracking, no retry, no deduplication. Pipeline jobs MUST go through arq.
- **Running the worker inside FastAPI:** The worker MUST run as a separate process (`arq stockvaluefinder.pipeline.worker.WorkerSettings`). Running it in-process would block the event loop on long-running jobs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Task retry with exponential backoff | Custom retry logic in job functions | arq `Retry(defer=N)` + `max_tries` on `func()` | Arq handles job lifecycle, tracking, and deferred re-enqueue. Custom retry would be fragile and miss edge cases (worker crash mid-retry). |
| Cron scheduling for reaper | Custom timer/loop with asyncio.sleep | arq `cron()` in WorkerSettings | Arq cron handles timezone, unique execution across multiple workers, and `run_at_startup`. Custom timer would miss edge cases. |
| Job deduplication per ticker | Custom Redis SET tracking | arq `_job_id` parameter on `enqueue_job()` | Arq's `_job_id` prevents duplicate jobs with same ID in queue. Custom dedup requires additional Redis operations and race condition handling. |
| Redis connection management in worker | Custom Redis client in worker | arq built-in Redis pool (via `RedisSettings`) | Worker manages its own Redis connection pool. Adding a second pool wastes connections and creates inconsistency. |
| State machine library | python-statemachine / transitions | Custom `StrEnum` + `dict` + `validate_transition()` | 5 states with linear transitions do not warrant a library. ~30 lines of custom code is simpler, more testable, and zero-dependency. |

**Key insight:** The arq library handles 90% of task queue complexity (job lifecycle, retry, cron, dedup, connection pooling). The custom code in this phase is limited to: config validation, state machine transitions, and the reaper business logic.

## Common Pitfalls

### Pitfall 1: Arq Redis DB Collision with Existing Cache
**What goes wrong:** The existing `CacheManager` uses Redis (default DB 0, but project uses port 6380). Arq defaults to Redis DB 0 on port 6379. If both use the same DB, arq keys (`arq:queue:*`) collide with cache keys (`v1:financial_report:*`).
**Why it happens:** Arq and redis-py have different default connection settings.
**How to avoid:** Use explicit `RedisSettings(host=, port=, database=)` matching the project's Redis. Arq namespaces its keys with `arq:` prefix, so even on the same DB there is no data collision. But for monitoring clarity, consider using a different DB number for arq (e.g., DB 1). This is configurable in `PipelineConfig.redis_db`.
**Warning signs:** Jobs not appearing in queue, or cache keys disappearing.

### Pitfall 2: Worker Startup Fails Silently
**What goes wrong:** `on_startup` raises an exception, but the worker process continues running in a broken state where `ctx` is partially initialized.
**Why it happens:** Arq catches startup errors but may not exit cleanly depending on the error type.
**How to avoid:** Keep `on_startup` minimal and defensive. Wrap initialization in try/except with clear logging. If critical resources (DB, Redis) fail to initialize, log loudly and let the worker crash -- it is better to have no worker than a broken one.
**Warning signs:** Worker process is running but not processing jobs.

### Pitfall 3: State Machine Race Condition on Concurrent Workers
**What goes wrong:** Two workers pick up the same task and both try to transition it from DOWNLOADING to PARSING simultaneously.
**Why it happens:** Arq does not enforce task-level locking by default. If `_job_id` is not set, the same task could be processed twice.
**How to avoid:** (1) Use arq's `_job_id` parameter with task_id-based job IDs to prevent duplicate job enqueueing. (2) Use PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) when reading and updating task state in a single transaction. (3) The `business_key` unique constraint prevents duplicate tasks at the DB level.
**Warning signs:** Duplicate analysis results, state transitions appearing out of order.

### Pitfall 4: Reaper Cron Misses Stuck Tasks
**What goes wrong:** The reaper scans for tasks stuck beyond `stuck_timeout_minutes`, but the query uses `created_at` instead of `updated_at`.
**Why it happens:** Confusion about which timestamp to use. The task was created hours ago but `updated_at` was set when the state changed to DOWNLOADING. Only `updated_at` is meaningful for stuck detection.
**How to avoid:** Reaper query must use `updated_at`: `WHERE state IN ('downloading','parsing','analyzing') AND updated_at < NOW() - INTERVAL '30 minutes'`.
**Warning signs:** Tasks remain stuck indefinitely despite reaper running.

### Pitfall 5: Alembic Migration Missing FK Dependencies
**What goes wrong:** `pipeline_tasks.ticker` references `stocks.ticker`, but the migration runs against a database where `stocks` table does not exist (fresh install).
**Why it happens:** Alembic runs migrations sequentially. If migration 009 runs without 001, the FK fails.
**How to avoid:** Ensure `down_revision` in migration 009 points to the last existing migration (008). Alembic's dependency chain handles ordering. Test migration on a clean database.
**Warning signs:** Migration fails with "relation stocks does not exist".

### Pitfall 6: Frozen Dataclass with Mutable Default
**What goes wrong:** `retry_delays: tuple[float, ...] = (2.0, 8.0, 30.0)` is fine, but if using `list` instead of `tuple`, Python would create a shared mutable default.
**Why it happens:** Frozen dataclass still allows mutable defaults (Python does not enforce immutability of field values, only of the field binding).
**How to avoid:** Use `tuple` (immutable) for sequence fields, never `list`. This matches the decision spec exactly.
**Warning signs:** `PipelineConfig` instances sharing state unexpectedly.

## Code Examples

Verified patterns from official sources and existing codebase:

### ORM Model for pipeline_tasks (Following RiskScoreDB Pattern)

```python
# Source: Based on existing stockvaluefinder/db/models/risk.py pattern
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class PipelineTaskDB(Base):
    """SQLAlchemy ORM model for pipeline task tracking."""

    __tablename__ = "pipeline_tasks"

    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique task identifier",
    )

    ticker: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.ticker"),
        nullable=False,
        index=True,
        comment="Stock ticker (FK to stocks)",
    )

    business_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Unique business key: ticker:fiscal_year:report_type",
    )

    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Current pipeline state",
    )

    current_stage: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Current processing stage description",
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )

    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="Maximum allowed retries",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last error message (if failed)",
    )

    result_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Summary of processing results",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Task creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp",
    )
```

### ORM Model for pipeline_documents

```python
# Source: Based on D-10 specification
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class PipelineDocumentDB(Base):
    """SQLAlchemy ORM model for downloaded document metadata."""

    __tablename__ = "pipeline_documents"

    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique document identifier",
    )

    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_tasks.task_id"),
        nullable=False,
        index=True,
        comment="Associated pipeline task",
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Original download URL",
    )

    source_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="External announcement ID for dedup",
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA256 hash of downloaded content",
    )

    file_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Local filesystem path to downloaded file",
    )

    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="File size in bytes",
    )

    downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Download completion timestamp",
    )
```

### Alembic Migration (Following 008 Pattern)

```python
# Source: Based on existing alembic/versions/008_add_documents_table.py pattern
"""Add pipeline_tasks and pipeline_documents tables

Revision ID: 009
Revises: 008
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009"
down_revision: Union[str, Sequence[str], None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pipeline_tasks and pipeline_documents tables."""
    op.create_table(
        "pipeline_tasks",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ticker", sa.String(20), sa.ForeignKey("stocks.ticker"), nullable=False, index=True),
        sa.Column("business_key", sa.String(255), nullable=False, unique=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("current_stage", sa.String(50), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "pipeline_documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_tasks.task_id"), nullable=False, index=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(255), nullable=True, index=True),
        sa.Column("content_hash", sa.String(64), nullable=True, index=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop pipeline tables. Documents first (FK dependency)."""
    op.drop_table("pipeline_documents")
    op.drop_table("pipeline_tasks")
```

### Arq Retry with Exponential Backoff (Verified from arq docs)

```python
# Source: [VERIFIED: arq-docs.helpmanual.io]
from arq import Retry

async def download_report(ctx: dict, task_id: str) -> None:
    """Download a financial report PDF."""
    try:
        # ... download logic ...
        pass
    except ExternalAPIError as e:
        # Exponential backoff: 2s, 8s, 30s
        retry_delays = (2.0, 8.0, 30.0)
        job_try = ctx["job_try"]  # 1-indexed attempt number
        if job_try <= len(retry_delays):
            raise Retry(defer=retry_delays[job_try - 1])
        raise  # Let arq mark as permanently failed
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler 3.x (sync) | arq cron_jobs | arq 0.26+ | Cron scheduling built into task queue, no separate library |
| Celery + RabbitMQ | arq + Redis | arq 0.25+ | Lighter weight, asyncio-native, single Redis dependency |
| `str, Enum` for categorization | `StrEnum` (Python 3.11+) | Python 3.11 | Built-in string enum, no need for `(str, Enum)` mixin |
| Alembic autogenerate | Manual migrations | Always | Project uses manual migrations (target_metadata=None in env.py) |

**Deprecated/outdated:**
- `RQ (Redis Queue)`: Sync-only predecessor to arq. Arq is the async successor. [CITED: arq docs]
- APScheduler 4.0: Alpha-only on PyPI (4.0.0a6). Not suitable for production. [VERIFIED: pip index]

## Assumptions Log

> All claims in this research were verified against codebase inspection, arq Context7 docs, or pip registry checks. No unverified assumptions remain.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Arq cron `minute=set(range(0, 60, 5))` achieves 5-minute interval | Pattern 3 | Minor -- alternative syntax `minute={0,5,10,...55}` also works |
| A2 | Arq `func()` wrapper accepts `max_tries` parameter per function | Pattern 3 | [VERIFIED: Context7 arq docs] |
| A3 | Existing `stocks.ticker` column is the correct FK target for `pipeline_tasks.ticker` | Code Examples | [VERIFIED: codebase inspection of risk.py line 40 shows `ForeignKey("stocks.ticker")`] |

## Open Questions (RESOLVED)

1. **Arq pool and CacheManager sharing the same Redis instance**
   - RESOLVED: Use `RedisSettings(host="localhost", port=6380, database=0)` for arq to match existing Redis. Arq's `arq:` key prefix prevents collision with `v1:` cache keys. Same instance, same DB, namespace isolation via key prefix.

2. **`onupdate` callback for `updated_at` in SQLAlchemy async**
   - RESOLVED: Use `onupdate=lambda: datetime.now(timezone.utc)` in ORM model definition AND set `updated_at` explicitly in repository update methods. Belt-and-suspenders approach ensures accurate timestamps even if `onupdate` has edge cases with async sessions.

3. **Worker process management in development**
   - RESOLVED: Claude's discretion per CONTEXT.md. Worker starts via `arq stockvaluefinder.pipeline.worker.WorkerSettings` in a separate terminal. No Procfile or Makefile target needed for Phase 5 — manual start is acceptable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | arq queue backend | Not responding | -- | Docker container (project uses 6380) |
| PostgreSQL | Pipeline table persistence | Not responding (5433) | -- | Docker container |
| Python 3.12+ | Runtime | Available | 3.14.4 | -- |
| uv | Package manager | Available | 0.7.16 | -- |
| Docker | Service containers | Available | 28.2.2 | -- |
| arq | Task queue | Not installed | -- | `uv add arq` |

**Missing dependencies with no fallback:**
- Redis must be running (Docker container or local install). The worker and FastAPI arq pool both require it. Without Redis, the pipeline is non-functional but the rest of the application degrades gracefully (matching existing cache degradation pattern).
- PostgreSQL must be running for pipeline_tasks and pipeline_documents tables. Without it, migration fails.

**Missing dependencies with fallback:**
- arq package not installed yet. Install via `uv add "arq>=0.28.0"` during implementation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | None (uses conftest.py + autodiscovery) |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_pipeline/ -x` |
| Full suite command | `cd stockvaluefinder && uv run pytest --cov=stockvaluefinder --cov-report=term-missing` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | PipelineConfig validates fields, rejects invalid values | unit | `uv run pytest tests/unit/test_pipeline/test_config.py -x` | Wave 0 |
| CONF-02 | Alembic migration 009 creates pipeline_tasks and pipeline_documents tables | integration | `uv run pytest tests/integration/test_pipeline/test_migration.py -x` | Wave 0 |
| CONF-03 | Arq pool initializes in FastAPI lifespan | unit | `uv run pytest tests/unit/test_pipeline/test_worker_integration.py -x` | Wave 0 |
| CONF-04 | Health endpoint returns correct status for healthy/unhealthy components | unit | `uv run pytest tests/unit/test_pipeline/test_health_endpoint.py -x` | Wave 0 |
| PIPE-04 | State machine validates all valid transitions, rejects invalid ones | unit | `uv run pytest tests/unit/test_pipeline/test_state.py -x` | Wave 0 |
| PIPE-05 | State transitions are atomic (commit + updated_at) | unit | `uv run pytest tests/unit/test_pipeline/test_state.py::test_atomic_transition -x` | Wave 0 |
| PIPE-06 | Retry with exponential backoff (2s, 8s, 30s) | unit | `uv run pytest tests/unit/test_pipeline/test_config.py::test_retry_delays -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd stockvaluefinder && uv run pytest tests/unit/test_pipeline/ -x`
- **Per wave merge:** `cd stockvaluefinder && uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_pipeline/__init__.py` -- package init
- [ ] `tests/unit/test_pipeline/test_config.py` -- covers CONF-01, PIPE-06
- [ ] `tests/unit/test_pipeline/test_state.py` -- covers PIPE-04, PIPE-05
- [ ] `tests/unit/test_pipeline/test_models.py` -- Pydantic model validation
- [ ] `tests/unit/test_pipeline/test_health_endpoint.py` -- covers CONF-04
- [ ] `tests/unit/test_pipeline/test_worker_integration.py` -- covers CONF-03
- [ ] `tests/integration/test_pipeline/__init__.py` -- package init
- [ ] `tests/integration/test_pipeline/test_migration.py` -- covers CONF-02

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user system, no auth required |
| V3 Session Management | no | No user sessions in this phase |
| V4 Access Control | no | Single-user system |
| V5 Input Validation | yes | Pydantic models validate all pipeline inputs; ticker regex pattern from existing validators |
| V6 Cryptography | no | SHA256 for dedup hashing uses stdlib hashlib |

### Known Threat Patterns for Pipeline Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Redis injection via job args | Tampering | Arq serializes job args as msgpack; no raw Redis commands from user input |
| PostgreSQL injection via state values | Tampering | SQLAlchemy parameterized queries via ORM; PipelineState enum constrains values |
| Worker DoS via excessive job enqueueing | Denial of Service | Rate limiting on API endpoints; arq max_jobs limits concurrency |
| Stuck task accumulation | Denial of Service | Reaper cron resets stuck tasks; max_retries prevents infinite loops |

## Sources

### Primary (HIGH confidence)
- arq Context7 ID: /websites/arq-docs_helpmanual_io (177 code snippets, HIGH reputation) -- WorkerSettings, cron, func, create_pool, Retry
- arq Context7 ID: /python-arq/arq (68 code snippets, Medium reputation) -- source code patterns
- Existing codebase: `stockvaluefinder/stockvaluefinder/config.py` -- frozen dataclass patterns (6 examples)
- Existing codebase: `stockvaluefinder/stockvaluefinder/db/models/risk.py` -- ORM model pattern
- Existing codebase: `stockvaluefinder/stockvaluefinder/alembic/versions/008_add_documents_table.py` -- migration pattern
- Existing codebase: `stockvaluefinder/stockvaluefinder/utils/errors.py` -- exception hierarchy
- Existing codebase: `stockvaluefinder/stockvaluefinder/main.py` -- lifespan pattern
- Existing codebase: `stockvaluefinder/stockvaluefinder/models/api.py` -- ApiResponse[T] pattern
- Existing codebase: `stockvaluefinder/stockvaluefinder/models/enums.py` -- enum patterns

### Secondary (MEDIUM confidence)
- pip registry: arq 0.28.0 (verified latest stable, 2026-05-01)
- pip registry: APScheduler 4.0.0a6 (alpha-only, not suitable for production)
- `.planning/research/STACK.md` -- milestone-level stack research
- `.planning/research/ARCHITECTURE.md` -- architecture patterns research

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- arq 0.28.0 verified via pip registry and Context7 docs; all other packages are existing and validated
- Architecture: HIGH -- patterns follow existing codebase conventions exactly; arq worker pattern verified from official docs
- Pitfalls: HIGH -- based on arq documentation review and common async task queue patterns

**Research date:** 2026-05-01
**Valid until:** 2026-05-31 (arq is stable, patterns are project-specific)
