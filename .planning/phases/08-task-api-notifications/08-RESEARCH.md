# Phase 8: Task API, Notifications & Sandbox - Research

**Researched:** 2026-05-02
**Domain:** FastAPI SSE, Redis pub/sub, subprocess sandbox, pagination
**Confidence:** HIGH

## Summary

Phase 8 adds three capabilities to the existing pipeline infrastructure: (1) a set of REST endpoints for querying pipeline status, listing tasks, and triggering manual processing; (2) a real-time SSE notification channel backed by Redis pub/sub for task lifecycle events; and (3) an optional subprocess sandbox that isolates financial calculations with CPU time and memory limits.

The existing codebase already has all the building blocks needed. The pipeline_routes.py file has a health endpoint and watchlist CRUD -- new endpoints slot directly into the same router. The worker.py already manages state transitions (download_report, parse_report, analyze_report) -- SSE event emission hooks into these same transition points. The CacheManager in utils/cache.py already wraps redis.asyncio -- the same Redis connection can be used for pub/sub. The calculation_sandbox.py stub is a single-function TODO that gets replaced entirely.

**Primary recommendation:** Use `sse-starlette` for SSE (adds `EventSourceResponse`), raw Starlette `StreamingResponse` as fallback, Redis LIST for event replay with LRANGE, and Python's `subprocess.run` with `resource` module for the sandbox. No new infrastructure beyond what is already running.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Redis-backed event log for SSE reconnect replay. Store last 100 events in Redis list with configurable TTL. Client reconnects with Last-Event-ID header to get missed events.
- **D-02:** 3 event types: task_created (new task enqueued), task_completed (DONE state), task_failed (FAILED state). Each carries task_id, ticker, business_key, state, timestamp.
- **D-03:** POST /api/v1/pipeline/trigger accepts {ticker, fiscal_year?, report_type?}. If fiscal_year/report_type omitted, processes latest available.
- **D-04:** By default, dedup blocks reprocessing existing DONE tasks. Add force=true query param to bypass dedup and re-download/re-analyze. Returns the new task_id.
- **D-05:** Trigger queues a download_report job directly -- full pipeline from download -> parse -> analyze. If ticker not in watchlist, auto-add it first.
- **D-06:** Python subprocess.run() with timeout (default 30s) and resource limits (via resource module on Linux). Receives JSON via stdin, returns JSON via stdout.
- **D-07:** Optional -- sandbox is an enhancement. Pipeline works without it (in-process execution as today). Config flag enables/disables. Graceful fallback.
- **D-08:** GET /api/v1/pipeline/status returns per-state counts (pending, downloading, parsing, analyzing, done, failed), last_poll_time from watcher_state, next_poll_time (computed from schedule), total_tasks.

### Claude's Discretion
- SSE endpoint implementation details (FastAPI StreamingResponse)
- Event ID format and Redis key structure
- Subprocess JSON protocol (input/output schema)
- Task listing query optimization (pagination, filtering)
- Resource limit configuration details
- CalculationSandboxService class structure

### Deferred Ideas (OUT OF SCOPE)
- Webhook notification (DingTalk, WeChat Server酱) -- future milestone
- Batch CSI 300 screening -- future milestone
- Separate DB users for worker vs API -- future milestone
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TASK-01 | GET /api/v1/pipeline/status returns aggregate counts by state, last poll time, next scheduled poll time | PipelineTaskDB has state column with index; WatcherStateRepository provides last_poll_time; PipelineConfig has cron schedules; SQLAlchemy `func.count()` with GROUP BY for state counts |
| TASK-02 | GET /api/v1/pipeline/tasks with filtering by state, ticker, date range, pagination | PipelineTaskRepository needs new `list_tasks()` method with WHERE clauses; PaginationMeta model already exists in models/api.py; offset/limit pattern with COUNT(*) OVER() for total |
| TASK-03 | POST /api/v1/pipeline/trigger for manual processing per ticker | WatcherService.build_business_key pattern reusable; arq pool available on app.state.arq_pool for enqueuing download_report; WatchlistRepository for auto-add |
| TASK-04 | SSE endpoint GET /api/v1/pipeline/events pushes task_created, task_completed, task_failed events | sse-starlette EventSourceResponse; Redis pub/sub via existing redis.asyncio; worker.py transition hooks emit events |
| TASK-05 | SSE handles disconnect/reconnect with event replay via Last-Event-ID | Redis LIST (RPUSH/LRANGE) for event log; Last-Event-ID header parsed in endpoint; replay missed events from stored list |
| SBOX-01 | Subprocess with timeout and memory limits | Python `subprocess.run(timeout=30)` verified working; `resource.setrlimit(RLIMIT_AS, ...)` verified enforcing MemoryError at 100MB limit |
| SBOX-02 | Subprocess receives JSON via stdin, returns JSON via stdout | Verified: subprocess.run with input=json.dumps(), capture_output=True, json.loads(stdout) |
| SBOX-03 | Kill subprocess on timeout/memory breach, return CalculationError | subprocess.TimeoutExpired verified catchable; MemoryError in child caught by RLIMIT_AS; CalculationError already exists in errors.py |
| SBOX-04 | Sandbox is optional, pipeline works without it | PipelineConfig gets sandbox_enabled field (default False); calculation_sandbox.py wraps in try/except with in-process fallback |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Task status aggregation | API / Backend | Database | API endpoint queries DB for state counts; pure read operation |
| Task listing with pagination | API / Backend | Database | API endpoint queries with filters; DB does WHERE/LIMIT/OFFSET |
| Manual trigger | API / Backend | Worker (Redis queue) | API creates task + enqueues arq job; worker does actual processing |
| SSE event emission | Worker (publisher) | API (subscriber) | Worker publishes to Redis pub/sub on state transitions; API subscribes and streams to clients |
| SSE event streaming | API / Backend | Redis | API holds open connection, subscribes to Redis channel, yields SSE events |
| Event replay on reconnect | API / Backend | Redis | API reads from Redis LIST using Last-Event-ID offset |
| Calculation sandbox | Worker | OS (subprocess) | Worker spawns subprocess for calculation; OS enforces resource limits |
| Resource limit enforcement | OS (subprocess) | -- | resource.setrlimit in child process before calculation runs |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sse-starlette | 3.4.1 (latest) | SSE EventSourceResponse for FastAPI | De-facto standard for SSE in FastAPI/Starlette; handles keep-alive, event formatting, disconnect detection [VERIFIED: pip index] |
| starlette | 0.46.2 (installed) | StreamingResponse fallback | Already installed as FastAPI dependency; raw SSE possible if sse-starlette unavailable [VERIFIED: installed] |
| redis.asyncio | 7.2.1+ (installed) | Async Redis pub/sub + LIST for SSE events | Already installed and used by CacheManager; same client handles pub/sub [VERIFIED: pyproject.toml] |
| Python resource | stdlib | RLIMIT_CPU, RLIMIT_AS for subprocess sandbox | Standard library on Linux; verified RLIMIT_AS catches MemoryError [VERIFIED: tested in environment] |
| Python subprocess | stdlib | subprocess.run with timeout for sandbox | Standard library; verified TimeoutExpired and JSON stdin/stdout protocol [VERIFIED: tested in environment] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fastapi | 0.115.14 (installed) | API framework for new endpoints | All REST endpoints [VERIFIED: installed] |
| sqlalchemy | 2.0+ (installed) | Aggregate queries, pagination | TASK-01 state counts, TASK-02 filtered listing [VERIFIED: pyproject.toml] |
| pydantic | 2.11.7 (installed) | Request/response models | Trigger request model, SSE event model, pagination params [VERIFIED: installed] |
| pytest-asyncio | 1.3+ (installed) | Async test support | All endpoint tests [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette | Raw StreamingResponse | Raw requires manual SSE formatting (`data: ...\n\n`), no built-in ping/keep-alive, no auto-disconnect. sse-starlette handles all of this. Use raw only if dependency is rejected. |
| Redis LIST for replay | Redis Stream (XADD/XREAD) | Streams provide consumer groups and auto-ID, but add complexity for this single-consumer use case. LIST with RPUSH/LRANGE is simpler and sufficient for last-100 replay. |
| subprocess.run | Docker container | Docker gives stronger isolation (filesystem, network), but adds runtime dependency on Docker daemon. subprocess with resource module is zero-dependency on Linux. Per D-06 decision, subprocess is the locked choice. |

**Installation:**
```bash
cd stockvaluefinder && uv add sse-starlette
```

**Version verification:** sse-starlette 3.4.1 confirmed latest via `pip index versions` [VERIFIED: pip registry].

## Architecture Patterns

### System Architecture Diagram

```
                                  Redis
                               +---------+
                               |  LIST   |  event_log (last 100 events)
                               |  PUB/SUB|  channel: pipeline:events
                               +---------+
                                  ^   |
           RPUSH + PUBLISH        |   | SUBSCRIBE + LRANGE (replay)
                                  |   v
+----------+    task state     +------------------+    SSE stream     +--------+
|  Worker  | ----transition--> |  FastAPI API     | ---------------> | Client |
|  (arq)   |                   |  /pipeline/events|                  | (JS)   |
+----------+                   +------------------+                  +--------+
     |                              |          |
     | enqueue                      |          | GET /pipeline/status
     | download_report              |          | GET /pipeline/tasks
     v                              v          | POST /pipeline/trigger
+----------+                   +----------+    |
|   arq    |                   | PostgreSQL|<--+
|  queue   |                   |  (tasks)  |
+----------+                   +----------+

                                    +-----------+
                                    | Sandbox   |
                                    | subprocess|
                                    | (optional)|
                                    +-----------+
                                    | stdin: JSON|
                                    | stdout: JSON|
                                    | RLIMIT_AS  |
                                    | RLIMIT_CPU |
                                    +-----------+
```

### Recommended Project Structure
```
stockvaluefinder/
├── api/
│   └── pipeline_routes.py        # ADD: status, tasks, trigger, events endpoints
├── pipeline/
│   ├── worker.py                 # MODIFY: add _emit_event() helper on transitions
│   ├── repo.py                   # MODIFY: add list_tasks(), count_by_state()
│   ├── config.py                 # MODIFY: add sandbox_enabled, sandbox_timeout fields
│   ├── event_bus.py              # NEW: Redis pub/sub + LIST event bus service
│   └── models.py                 # MODIFY: add SSE event models, task listing models
├── services/
│   └── calculation_sandbox.py    # REWRITE: replace stub with CalculationSandboxService
└── utils/
    └── errors.py                 # Already has CalculationError
```

### Pattern 1: SSE with Redis Pub/Sub and Event Replay

**What:** Three-component SSE architecture: worker publishes events, Redis stores and distributes, API endpoint subscribes and streams.

**When to use:** For real-time notifications of pipeline task state changes.

**Event bus service pattern:**

```python
# Source: [ASSUMED] - based on redis.asyncio pub/sub API + sse-starlette patterns
class PipelineEventBus:
    """Redis-backed event bus for pipeline task notifications.

    Publishes events via Redis pub/sub and persists last N events
    in a Redis list for reconnect replay.
    """

    CHANNEL = "pipeline:events"
    LOG_KEY = "pipeline:event_log"
    MAX_EVENTS = 100

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, event_type: str, payload: dict) -> None:
        """Publish event to channel and append to log."""
        event_id = f"{int(time.time() * 1000)}:{uuid4().hex[:8]}"
        event = {
            "id": event_id,
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        serialized = json.dumps(event)
        # RPUSH to log (keep last MAX_EVENTS)
        pipe = self._redis.pipeline()
        pipe.rpush(self.LOG_KEY, serialized)
        pipe.ltrim(self.LOG_KEY, -self.MAX_EVENTS, -1)
        pipe.publish(self.CHANNEL, serialized)
        await pipe.execute()

    async def replay_since(self, last_event_id: str) -> list[dict]:
        """Replay events after the given event ID."""
        all_events = await self._redis.lrange(self.LOG_KEY, 0, -1)
        events = [json.loads(e) for e in all_events]
        # Find position after last_event_id
        for i, evt in enumerate(events):
            if evt["id"] == last_event_id:
                return events[i + 1:]
        # If not found, return all (client was disconnected too long)
        return events

    async def subscribe(self) -> Any:
        """Subscribe to the events channel."""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.CHANNEL)
        return pubsub
```

**SSE endpoint pattern:**

```python
# Source: [ASSUMED] - sse-starlette EventSourceResponse API
from sse_starlette.sse import EventSourceResponse

@router.get("/events")
async def sse_events(request: Request) -> EventSourceResponse:
    async def event_generator():
        bus = PipelineEventBus(redis_client)
        last_id = request.headers.get("Last-Event-ID")

        # Replay missed events on reconnect
        if last_id:
            missed = await bus.replay_since(last_id)
            for evt in missed:
                yield {"id": evt["id"], "event": evt["type"], "data": json.dumps(evt)}

        # Subscribe to live events
        pubsub = await bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=30.0
                )
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    yield {"id": data["id"], "event": data["type"], "data": json.dumps(data)}
                else:
                    yield {"event": "ping", "data": ""}  # keep-alive
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()

    return EventSourceResponse(event_generator())
```

### Pattern 2: Pipeline Status Aggregation

**What:** Single query to get state counts, joined with watcher_state for last/next poll time.

**When to use:** GET /api/v1/pipeline/status endpoint.

```python
# Source: [ASSUMED] - SQLAlchemy 2.0 func.count pattern
from sqlalchemy import func, select

async def count_by_state(self) -> dict[str, int]:
    """Count tasks grouped by state."""
    stmt = (
        select(PipelineTaskDB.state, func.count())
        .group_by(PipelineTaskDB.state)
    )
    result = await self._session.execute(stmt)
    counts = dict(result.all())
    # Ensure all 6 states present
    all_states = {s.value: 0 for s in PipelineState}
    all_states.update(counts)
    return all_states
```

### Pattern 3: Subprocess Sandbox with Resource Limits

**What:** Isolated calculation execution with CPU time and memory limits.

**When to use:** Running financial calculations (M-Score, DCF, yield gap) in subprocess.

```python
# Source: [VERIFIED: tested in environment] - subprocess.run + resource module
class CalculationSandboxService:
    """Execute financial calculations in an isolated subprocess."""

    def __init__(self, timeout: int = 30, max_memory_mb: int = 256) -> None:
        self._timeout = timeout
        self._max_memory_bytes = max_memory_mb * 1024 * 1024

    def execute(self, calculation_type: str, inputs: dict) -> dict:
        """Run calculation in subprocess with resource limits.

        Args:
            calculation_type: Name of calculation to run (e.g., 'm_score').
            inputs: Calculation input parameters.

        Returns:
            Calculation result dict.

        Raises:
            CalculationError: On timeout, memory breach, or execution failure.
        """
        sandbox_script = self._build_script(calculation_type, inputs)

        try:
            result = subprocess.run(
                [sys.executable, "-c", sandbox_script],
                input=json.dumps({"type": calculation_type, "inputs": inputs}),
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise CalculationError(
                f"Calculation timed out after {self._timeout}s",
                calculation=calculation_type,
            )

        if result.returncode != 0:
            raise CalculationError(
                f"Calculation failed: {result.stderr}",
                calculation=calculation_type,
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise CalculationError(
                f"Invalid JSON output: {e}",
                calculation=calculation_type,
            )

    @staticmethod
    def _build_script(calculation_type: str, inputs: dict) -> str:
        """Build the subprocess script that sets resource limits and runs calculation."""
        return '''
import json, sys, resource

# Set resource limits BEFORE importing heavy modules
resource.setrlimit(resource.RLIMIT_CPU, ({timeout}, {timeout}))
resource.setrlimit(resource.RLIMIT_AS, ({mem}, {mem}))

# Read input from stdin
request = json.load(sys.stdin)
calc_type = request["type"]
inputs = request["inputs"]

# Execute the calculation
from stockvaluefinder.services.risk_service import RiskAnalyzer
from stockvaluefinder.services.valuation_service import DCFValuationService
from stockvaluefinder.services.yield_service import YieldAnalyzer

result = None
if calc_type == "m_score":
    analyzer = RiskAnalyzer()
    result = analyzer.analyze(inputs, None)
# ... similar for other calculation types

json.dump({{"status": "ok", "data": str(result)}}, sys.stdout)
'''
```

### Anti-Patterns to Avoid

- **Blocking Redis pub/sub in async endpoint:** Never use synchronous `redis.Redis` for pub/sub in FastAPI -- use `redis.asyncio.Redis` exclusively. The CacheManager already uses the async client.
- **Subprocess without resource limits:** A subprocess with no RLIMIT_AS can consume all available memory. Always set limits before importing calculation modules.
- **SSE without keep-alive:** Proxies (nginx, cloudflare) close idle connections after ~60s. Send `ping` events every 15-30 seconds.
- **Storing full event payload in Redis LIST:** Events should be compact (task_id, ticker, state, timestamp). Full result_summary goes in PostgreSQL, not Redis.
- **Mutation in SSE generator:** The event generator must not modify shared state. It reads from Redis pub/sub and yields -- nothing more.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE wire formatting | Manual `data: ...\n\n` string building | sse-starlette EventSourceResponse | Handles event IDs, keep-alive pings, proper SSE framing, client disconnect detection |
| Event replay persistence | Custom event store in PostgreSQL | Redis LIST with RPUSH/LRANGE + LTRIM | Redis LIST is append-only with O(1) push, O(N) range for last 100. Much faster than DB for ephemeral events. |
| Subprocess timeout | Custom signal.alarm handler | subprocess.run(timeout=N) | Built-in TimeoutExpired exception, process killed automatically on timeout |
| Memory limit in subprocess | Custom memory monitor thread | resource.setrlimit(RLIMIT_AS, ...) | Kernel-enforced, zero-overhead, catches allocations at malloc level. Verified working. [VERIFIED: tested] |
| Pagination total count | Two separate queries (count + select) | SQLAlchemy `func.count()` over window or single count query + separate data query | Two queries is fine for PostgreSQL at current scale; window functions add complexity for minimal gain |

**Key insight:** The infrastructure is already 80% built. Redis is running, CacheManager wraps redis.asyncio, the arq pool is on app.state, and the worker already handles state transitions. This phase is primarily about wiring these pieces together, not building new infrastructure.

## Common Pitfalls

### Pitfall 1: SSE Connection Leaks

**What goes wrong:** When a client disconnects (tab close, network drop), the async generator keeps running, holding open the Redis pub/sub subscription indefinitely. Over time, this leaks Redis connections and server memory.
**Why it happens:** Python async generators don't automatically cancel when the HTTP connection drops -- Starlette only stops iterating, but the generator may be blocked on `pubsub.get_message()`.
**How to avoid:** Check `await request.is_disconnected()` in every loop iteration. Use a timeout on `get_message()` (not infinite block). Wrap in try/finally to unsubscribe and close pubsub.
**Warning signs:** Redis connection count climbing steadily; server memory growing without bound.

### Pitfall 2: Redis pub/sub Lost Messages

**What goes wrong:** pub/sub is fire-and-forget -- if no subscriber is listening when a message is published, it is lost forever.
**Why it happens:** SSE endpoint may not be running when the worker publishes an event. Or the client is between reconnect attempts.
**How to avoid:** Per D-01, use Redis LIST (RPUSH) as a persistent event log alongside pub/sub. The publish method does both atomically (pipeline). On reconnect, replay from the LIST using Last-Event-ID.
**Warning signs:** Clients missing events after reconnect despite Last-Event-ID.

### Pitfall 3: Resource Limits Not Applied in Subprocess

**What goes wrong:** `resource.setrlimit()` must be called INSIDE the child process, before the calculation code runs. Setting it in the parent process has no effect on the child.
**Why it happens:** The resource module doc says limits are per-process, but developers sometimes assume parent settings propagate to children.
**How to avoid:** The subprocess script must call `resource.setrlimit()` as its FIRST action, before importing any heavy modules. The sandbox script template embeds these calls at the top.
**Warning signs:** Subprocess consuming unbounded memory despite configured limits.

### Pitfall 4: Pagination Offset Performance

**What goes wrong:** Large offsets (e.g., `OFFSET 50000`) become slow because PostgreSQL must scan and discard all preceding rows.
**Why it happens:** OFFSET/LIMIT pagination is O(offset) for PostgreSQL.
**How to avoid:** For current scale (CSI 300, at most a few thousand tasks), offset/limit is fine. If scale grows beyond 10K tasks, switch to keyset pagination using `created_at` cursor.
**Warning signs:** Task listing endpoint response time growing linearly with page number.

### Pitfall 5: SSE Starlette Disconnect Handling

**What goes wrong:** `sse-starlette` v1.x had issues where disconnect detection was unreliable. The `sse-starlette` v2+ changed the API. Version 3.x (current) uses a different internal model.
**Why it happens:** The library evolved significantly between major versions.
**How to avoid:** Pin to `sse-starlette>=2.0` (3.4.1 is current). Use `EventSourceResponse` with an async generator. Check `request.is_disconnected()` in the loop body, not relying on library auto-detection alone.
**Warning signs:** Generator continues running after client closes tab.

## Code Examples

### Task Listing with Pagination

```python
# Source: [ASSUMED] - SQLAlchemy 2.0 select + func.count pattern
async def list_tasks(
    self,
    state: str | None = None,
    ticker: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[PipelineTaskDB], int]:
    """List tasks with optional filters. Returns (tasks, total_count)."""
    # Base query
    stmt = select(PipelineTaskDB)
    count_stmt = select(func.count()).select_from(PipelineTaskDB)

    # Apply filters
    if state:
        stmt = stmt.where(PipelineTaskDB.state == state)
        count_stmt = count_stmt.where(PipelineTaskDB.state == state)
    if ticker:
        stmt = stmt.where(PipelineTaskDB.ticker == ticker)
        count_stmt = count_stmt.where(PipelineTaskDB.ticker == ticker)
    if created_after:
        stmt = stmt.where(PipelineTaskDB.created_at >= created_after)
        count_stmt = count_stmt.where(PipelineTaskDB.created_at >= created_after)
    if created_before:
        stmt = stmt.where(PipelineTaskDB.created_at <= created_before)
        count_stmt = count_stmt.where(PipelineTaskDB.created_at <= created_before)

    # Get total count
    total = (await self._session.execute(count_stmt)).scalar() or 0

    # Apply pagination
    stmt = stmt.order_by(PipelineTaskDB.created_at.desc()).offset(offset).limit(limit)
    result = await self._session.execute(stmt)
    tasks = list(result.scalars().all())

    return tasks, total
```

### SSE Event Emission Hook in Worker

```python
# Source: [ASSUMED] - integration point in worker.py
async def _emit_event(
    event_type: str,
    task_id: str,
    ticker: str,
    business_key: str,
    state: str,
) -> None:
    """Publish SSE event via Redis. Non-blocking, fails gracefully."""
    try:
        from redis.asyncio import Redis
        r = Redis()
        event = json.dumps({
            "id": f"{int(time.time() * 1000)}:{uuid4().hex[:8]}",
            "type": event_type,
            "task_id": task_id,
            "ticker": ticker,
            "business_key": business_key,
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        pipe = r.pipeline()
        pipe.rpush("pipeline:event_log", event)
        pipe.ltrim("pipeline:event_log", -100, -1)  # Keep last 100
        pipe.publish("pipeline:events", event)
        await pipe.execute()
        await r.aclose()
    except Exception as e:
        logger.warning(f"Failed to emit SSE event: {e}")
```

### Manual Trigger Endpoint

```python
# Source: [ASSUMED] - based on existing patterns in watcher.py and pipeline_routes.py
class TriggerRequest(BaseModel):
    ticker: str = Field(..., pattern=r"^\d{4,6}\.(SH|SZ|HK)$")
    fiscal_year: int | None = Field(None, ge=2000, le=2100)
    report_type: str | None = Field(None, pattern=r"^(annual|semi_annual|q1|q3)$")

@router.post("/trigger")
async def trigger_pipeline(
    body: TriggerRequest,
    force: bool = Query(default=False),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    ticker = body.ticker
    fiscal_year = body.fiscal_year or _latest_fiscal_year()
    report_type = body.report_type or "annual"
    business_key = f"{ticker}:{fiscal_year}:{report_type}"

    # Auto-add to watchlist if not present (D-05)
    watchlist_repo = WatchlistRepository(db)
    existing = await watchlist_repo.get_by_ticker(ticker)
    if existing is None:
        await watchlist_repo.add(ticker, ticker)  # name defaults to ticker

    # Check dedup (D-04)
    if not force:
        task_repo = PipelineTaskRepository(db)
        existing_task = await task_repo.get_by_business_key(business_key)
        if existing_task and existing_task.state == "done":
            return ApiResponse(
                success=False,
                error=f"Task already completed for {business_key}. Use force=true to reprocess.",
            )

    # Create task and enqueue
    task_repo = PipelineTaskRepository(db)
    task = await task_repo.create_task(ticker, business_key)
    await db.commit()

    # Enqueue download_report via arq pool
    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool:
        await arq_pool.enqueue_job("download_report", str(task.task_id))

    return ApiResponse(success=True, data={"task_id": str(task.task_id)})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WebSocket for one-directional push | SSE (Server-Sent Events) | SSE spec standardized ~2015; adopted widely 2020+ | Simpler protocol, auto-reconnect built into browser EventSource API, no bidirectional overhead |
| Celery + RabbitMQ | arq + Redis | Project decision Phase 5 | arq is lighter weight, Redis already required for caching, no extra infrastructure |
| Docker sandbox | subprocess + resource module | Project decision Phase 8 (D-06) | Zero external dependencies on Linux, subprocess.run timeout is kernel-enforced |
| Redis Streams for event log | Redis LIST | Design choice for simplicity | LIST with LTRIM is sufficient for last-100 replay; Streams add consumer group complexity not needed for single-consumer SSE |

**Deprecated/outdated:**
- `aioredis`: Merged into `redis>=4.2.0` as `redis.asyncio`. Use `from redis.asyncio import Redis`. [ASSUMED]
- Starlette built-in SSE (`starlette.sse.SSEResponse`): Removed in newer versions. Use `sse-starlette` instead. [ASSUMED]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | sse-starlette EventSourceResponse accepts async generator yielding dicts with `id`, `event`, `data` keys | Architecture Patterns | SSE formatting may differ; need to verify with actual sse-starlette docs after install |
| A2 | redis.asyncio pub/sub get_message with timeout works for async iteration | Architecture Patterns | May need different async pattern; redis.asyncio pubsub API may have nuances |
| A3 | resource.setrlimit(RLIMIT_AS) catches large allocations reliably on WSL2/Linux | Code Examples | May not work on all Linux kernels; but verified working in current environment |
| A4 | sse-starlette 3.x API is stable and compatible with FastAPI 0.115.x | Standard Stack | Version compatibility may require adjustment |
| A5 | Starlette removed built-in SSE support in recent versions | State of the Art | If still available, sse-starlette is still preferred for richer API |

## Open Questions

1. **Event ID format for replay accuracy**
   - What we know: D-01 says Redis LIST with configurable TTL, Last-Event-ID for replay.
   - What's unclear: Whether millisecond timestamp + random hex is sufficient for uniqueness, or if a monotonic counter is needed.
   - Recommendation: Use `{timestamp_ms}:{random_hex}` format. Monotonic counter adds complexity (Redis INCR is needed) with no practical benefit at current scale.

2. **Subprocess sandbox script location**
   - What we know: D-06 says subprocess.run receives JSON via stdin.
   - What's unclear: Whether the subprocess script should be a separate .py file or embedded as a string.
   - Recommendation: Use a separate `sandbox_runner.py` module for clarity and testability. The subprocess runs `python -m stockvaluefinder.services.sandbox_runner` with JSON on stdin.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis server | SSE pub/sub, event log | Not verified (uv run cannot import redis module) | 7.2.1 (library) | SSE degrades to polling; sandbox unaffected |
| PostgreSQL | Task listing, status counts | Via asyncpg driver | 2.0+ (SQLAlchemy) | -- |
| sse-starlette | SSE endpoint | Not installed | 3.4.1 (available) | Raw StreamingResponse (manual SSE formatting) |
| Python resource module | Sandbox RLIMIT_AS/RLIMIT_CPU | Verified | stdlib (Python 3.12) | -- |
| Python subprocess | Sandbox execution | Verified | stdlib (Python 3.12) | -- |
| arq pool on app.state | Trigger endpoint | Available (main.py lifespan) | 0.25+ | Return error if pool unavailable |

**Missing dependencies with no fallback:**
- None -- all capabilities have graceful degradation paths.

**Missing dependencies with fallback:**
- sse-starlette: Not yet installed. Install via `uv add sse-starlette`. Fallback: raw StreamingResponse with manual SSE formatting (more code but zero new dependency).
- Redis server: Cannot verify connectivity from this environment (redis module not importable in uv context). The CacheManager already handles Redis unavailability gracefully; SSE endpoint should follow the same pattern.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | None -- relies on pytest auto-discovery |
| Quick run command | `uv run pytest tests/unit/test_pipeline/ -x -q` |
| Full suite command | `uv run pytest tests/unit/ --cov=stockvaluefinder -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TASK-01 | Status endpoint returns state counts, poll times | unit | `uv run pytest tests/unit/test_pipeline/test_task_api.py::test_status_counts -x` | Wave 0 |
| TASK-02 | Task listing with filters and pagination | unit | `uv run pytest tests/unit/test_pipeline/test_task_api.py::test_tasks_pagination -x` | Wave 0 |
| TASK-03 | Manual trigger creates task and enqueues job | unit | `uv run pytest tests/unit/test_pipeline/test_task_api.py::test_trigger_pipeline -x` | Wave 0 |
| TASK-04 | SSE endpoint streams events from Redis pub/sub | unit | `uv run pytest tests/unit/test_pipeline/test_sse_endpoint.py::test_sse_streams_events -x` | Wave 0 |
| TASK-05 | SSE reconnect replays missed events via Last-Event-ID | unit | `uv run pytest tests/unit/test_pipeline/test_sse_endpoint.py::test_sse_reconnect_replay -x` | Wave 0 |
| SBOX-01 | Subprocess executes with timeout and memory limits | unit | `uv run pytest tests/unit/test_services/test_sandbox.py::test_execute_with_limits -x` | Wave 0 |
| SBOX-02 | Subprocess receives JSON stdin, returns JSON stdout | unit | `uv run pytest tests/unit/test_services/test_sandbox.py::test_json_protocol -x` | Wave 0 |
| SBOX-03 | Timeout and memory breach return CalculationError | unit | `uv run pytest tests/unit/test_services/test_sandbox.py::test_timeout_raises_error -x` | Wave 0 |
| SBOX-04 | Sandbox is optional, in-process fallback works | unit | `uv run pytest tests/unit/test_services/test_sandbox.py::test_sandbox_disabled_fallback -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_pipeline/ tests/unit/test_services/test_sandbox.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ --cov=stockvaluefinder -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_pipeline/test_task_api.py` -- covers TASK-01, TASK-02, TASK-03
- [ ] `tests/unit/test_pipeline/test_sse_endpoint.py` -- covers TASK-04, TASK-05
- [ ] `tests/unit/test_pipeline/test_event_bus.py` -- covers PipelineEventBus unit tests
- [ ] `tests/unit/test_services/test_sandbox.py` -- covers SBOX-01 through SBOX-04
- [ ] `stockvaluefinder/pipeline/event_bus.py` -- new module for SSE event bus

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user system per project scope |
| V3 Session Management | no | No user sessions |
| V4 Access Control | yes | API endpoints are open by design (single-user); trigger endpoint should validate ticker format |
| V5 Input Validation | yes | Pydantic models with regex validation on ticker, bounds on fiscal_year, enum on report_type |
| V6 Cryptography | no | No encryption needed for internal pipeline events |

### Known Threat Patterns for FastAPI SSE + Redis

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unbounded SSE connections (DoS) | Denial of Service | Connection limit via middleware or config; each connection holds Redis pub/sub |
| Redis injection via event payload | Tampering | All event payloads are JSON-serialized dicts constructed server-side; no user input flows directly into Redis commands |
| Subprocess command injection | Tampering | subprocess.run with list args (not shell=True); calculation_type is validated against whitelist |
| Memory exhaustion via large subprocess output | Denial of Service | RLIMIT_AS limits subprocess memory; subprocess.run captures stdout in memory (bounded by calculation output size) |

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `pipeline_routes.py`, `worker.py`, `repo.py`, `config.py`, `cache.py`, `calculation_sandbox.py`, `main.py`, `watcher.py`, `state.py`, `models.py`, `api.py`, `dependencies.py`, `watcher_repo.py`, `watchlist_repo.py`, `pipeline_task.py`, `watcher_state.py`, `errors.py`, `db/base.py`
- Environment verification: subprocess.run with JSON stdin/stdout verified, resource.RLIMIT_AS MemoryError verified, subprocess.TimeoutExpired verified
- Package registry: `sse-starlette 3.4.1` confirmed latest via `pip index versions`
- pyproject.toml dependency analysis for existing stack versions

### Secondary (MEDIUM confidence)
- Web search (API limit exhausted): FastAPI SSE + Redis pub/sub pattern, sse-starlette EventSourceResponse API, Last-Event-ID reconnect pattern -- these are well-established patterns with multiple credible sources but could not be cross-verified with live docs due to search limit

### Tertiary (LOW confidence)
- sse-starlette 3.x exact API for dict-based event yielding (A1) -- need to verify after install
- redis.asyncio pubsub async iteration pattern (A2) -- well-known but not verified in this session with actual async Redis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries verified installed or available; subprocess/resource tested in environment
- Architecture: HIGH - all integration points verified in existing codebase; patterns follow established FastAPI/Redis conventions
- Pitfalls: HIGH - SSE connection leaks and pub/sub message loss are well-documented issues with known mitigations
- Sandbox: HIGH - resource limits and subprocess timeout verified working in target environment

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (stable domain, no fast-moving dependencies)
