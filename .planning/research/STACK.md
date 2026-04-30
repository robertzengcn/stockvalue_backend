# Technology Stack: v1.1 Smart Financial Report Pipeline

**Project:** StockValueFinder v1.1
**Researched:** 2026-05-01
**Scope:** NEW dependencies only -- existing stack (FastAPI, SQLAlchemy, Redis, PostgreSQL, Qdrant, PyMuPDF, AKShare, efinance, DeepSeek LLM) is validated and not re-evaluated.

## Context

This document covers ONLY new technologies needed for the v1.1 milestone: an event-driven pipeline that monitors A-share financial report announcements, downloads PDFs, parses them, triggers AI analysis (M-Score, F-Score, DCF, yield gap), and updates the RAG vector store.

The pipeline requires five new capabilities:
1. **Task Queue** -- Async job processing for pipeline stages (download, parse, analyze, embed)
2. **Scheduler** -- Periodic polling of financial report announcement sources
3. **Notifications** -- SSE push when pipeline tasks complete
4. **Async File I/O** -- Non-blocking PDF download and storage
5. **Retry Logic** -- Resilient external call handling

---

## Recommended New Dependencies

### Task Queue + Scheduler (combined)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **arq** | >=0.28.0 | Async task queue AND cron scheduler | asyncio-native, uses existing Redis (zero new infrastructure), built-in cron_jobs in WorkerSettings eliminates need for separate scheduler, built by Pydantic creator Samuel Colvin. Native retry via `arq.Retry(defer=N)` with exponential backoff. Job uniqueness for dedup. Worker context shares HTTP clients and DB sessions. |

### Notifications

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **sse-starlette** | >=3.4.0 | Server-Sent Events for pipeline status push | Production-ready SSE for Starlette/FastAPI. Supports client disconnect detection (`await request.is_disconnected()`), broadcast pattern via per-client asyncio queues, ping/keepalive. Zero-config integration with our existing FastAPI async setup. |

### File Operations

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **aiofiles** | >=25.1.0 | Async file I/O for PDF download and temp storage | Non-blocking file writes during PDF download. stdlib `open()` blocks the asyncio event loop on multi-MB files. aiofiles wraps file I/O in thread pool executor. Simple API: `async with aiofiles.open(path, "wb") as f: await f.write(chunk)`. |

### Retry Logic

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **tenacity** | >=9.1.0 | Retry with exponential backoff for external HTTP calls | Declarative `@retry` decorators with async support. Used for announcement site polling and PDF download retries (network flakiness). Note: Arq has its own `Retry` for task-level retry (re-enqueue the whole task); tenacity is for finer-grained retry within a single task function call. |

---

## What NOT to Add (and Why)

### Task Queue Alternatives

| Alternative | Why Not |
|-------------|---------|
| **Celery** | Requires RabbitMQ or Redis broker, heavy operational footprint, poor async support (still mostly sync), massive config surface. Arq does everything we need with our existing Redis. Explicitly listed as "Out of Scope" in PROJECT.md. |
| **TaskIQ** | Newer (0.12.2), smaller community, requires separate broker packages (`taskiq-redis`, etc.). More moving parts. Arq is simpler and more mature for Redis-only use case. |
| **Dramatiq** | Sync-only, no native asyncio. Would need thread bridge for our entirely async codebase. |
| **Huey** | Sync-only, designed for simple/Django projects, no async support, too minimal. |
| **RQ (Redis Queue)** | Sync-only, predecessor to Arq. Arq is explicitly the async successor. |

### Scheduler Alternatives

| Alternative | Why Not |
|-------------|---------|
| **APScheduler 4.x** | Only available as alpha (4.0.0a6 on PyPI, verified 2026-05-01). Context7 docs show AsyncScheduler patterns that look production-ready, but PyPI ships alpha only. Not suitable for production. |
| **APScheduler 3.x** | Latest stable is 3.11.2. Would work, but redundant -- Arq's built-in `cron_jobs` in WorkerSettings handles periodic scheduling with no additional library. Two scheduling systems for one pipeline is unnecessary complexity. |

### State Machine Alternatives

| Alternative | Why Not |
|-------------|---------|
| **python-statemachine** (3.0.0) | Overkill for our 5-state linear FSM (PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE/FAILED). Library adds dependency, learning curve, and async integration complexity for what is fundamentally a simple enum + transition map. |
| **transitions** | Most popular Python state machine library but has no native async support. Async callbacks require wrapping with `asyncio.create_task()`. Not worth the coupling for a linear pipeline. |
| **Custom Enum + dict** (RECOMMENDED) | Zero dependencies, full async control, trivial to test. 5 states with linear progression do not warrant a library. See State Machine section below. |

### Other Rejected Options

| Alternative | Why Not |
|-------------|---------|
| **PaddleOCR** | Explicitly out of scope for this milestone. PyMuPDF text extraction handles digital PDFs. OCR deferred to future phase. Listed in PROJECT.md Out of Scope. |
| **Playwright** | Explicitly out of scope. API/HTTP fetching preferred over browser automation. Listed in PROJECT.md Out of Scope. |
| **Celery + RabbitMQ** | Explicitly listed in PROJECT.md Out of Scope: "Arq + Redis sufficient for current task volume." |
| **WebSocket** | SSE is simpler and sufficient for one-way status push. WebSocket would add bidirectional complexity we do not need. Listed in PROJECT.md Out of Scope: "SSE sufficient for status push." |

---

## Scheduling Strategy: Arq Cron (Not APScheduler)

The key architectural decision is that **Arq handles both task queue and scheduling**, eliminating the need for a separate scheduler library entirely.

**How it works:**

```python
from arq import cron
from arq.connections import RedisSettings

async def check_announcements(ctx):
    """Periodic: check for new financial report announcements."""
    watcher = ctx["watcher"]
    announcements = await watcher.poll()
    for ann in announcements:
        await ctx["redis"].enqueue_job("process_report", ann["url"], ann["ticker"])

class WorkerSettings:
    functions = [process_report]
    cron_jobs = [
        cron(
            check_announcements,
            hour={9, 12, 15, 18},  # Check at market-related times
            minute=30,
            run_at_startup=True,   # Check immediately when worker starts
            unique=True,           # Prevent duplicate cron runs
        )
    ]
    on_startup = startup   # Initialize HTTP client, DB pool, watcher
    on_shutdown = shutdown
    redis_settings = RedisSettings()
```

**Why this beats adding APScheduler:**
1. Single system to manage -- one worker process, one configuration
2. Cron jobs run inside the same async context as task workers, sharing the `ctx` dict with HTTP clients and DB sessions
3. No additional data store needed -- Arq cron state lives in Redis alongside queue data
4. Simpler operational model -- one `arq` worker process to monitor, not two systems
5. `unique=True` prevents duplicate cron execution across multiple workers

---

## State Machine Strategy: Custom Enum (No Library)

The pipeline has exactly 5 states with well-defined, linear transitions:

```python
from enum import StrEnum

class PipelineState(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    DONE = "done"
    FAILED = "failed"

# Valid transitions (immutable dict)
VALID_TRANSITIONS: dict[PipelineState, frozenset[PipelineState]] = {
    PipelineState.PENDING: frozenset({PipelineState.DOWNLOADING, PipelineState.FAILED}),
    PipelineState.DOWNLOADING: frozenset({PipelineState.PARSING, PipelineState.FAILED}),
    PipelineState.PARSING: frozenset({PipelineState.ANALYZING, PipelineState.FAILED}),
    PipelineState.ANALYZING: frozenset({PipelineState.DONE, PipelineState.FAILED}),
    PipelineState.DONE: frozenset(),       # Terminal state
    PipelineState.FAILED: frozenset(),     # Terminal state (retry restarts from PENDING)
}

def validate_transition(current: PipelineState, target: PipelineState) -> bool:
    """Check if transition from current to target state is valid."""
    return target in VALID_TRANSITIONS.get(current, frozenset())
```

**Why no library:**
- 5 states, linear progression, no hierarchical states, no guard conditions, no parallel branches
- Custom solution is ~30 lines, zero dependencies, fully typed, trivially testable
- Libraries like `transitions` or `python-statemachine` would add 200+ lines of abstraction for a state graph that fits on a single line: `PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE` (with `-> FAILED` from any step)

---

## Integration Points with Existing Stack

### Redis (existing -- used for caching)

Arq reuses the same Redis instance for task queue. No new infrastructure.

**Recommended DB isolation:**

```
Redis DB 0: Arq task queue (job data, cron state, results)
Redis DB 1: Application cache (existing CacheManager)
```

Or use the same DB with Arq's namespaced keys (`arq:queue:*`). The existing CacheManager uses custom key prefixes (`v1:financial_report:*`), so there is no collision risk on the same DB. Either approach works; DB isolation is cleaner for monitoring.

**Arq pool configuration in FastAPI lifespan:**

```python
from arq import create_pool
from arq.connections import RedisSettings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing Redis cache init ...

    # New: Initialize Arq connection pool (for enqueuing from FastAPI)
    arq_pool = await create_pool(RedisSettings())
    app.state.arq_pool = arq_pool

    yield

    # New: Close Arq pool
    await arq_pool.close()
```

**Note:** The Arq **worker** runs as a separate process (`arq stockvaluefinder.pipeline.worker.WorkerSettings`), not inside FastAPI. The pool in FastAPI is only for enqueueing jobs via `await arq_pool.enqueue_job("process_report", ...)`.

### FastAPI Lifespan (existing pattern in main.py)

The current lifespan initializes Redis cache and checks Qdrant health. Extend it to also create the Arq connection pool. The pattern is identical -- initialize in startup, store on `app.state`, close in shutdown.

### SQLAlchemy / PostgreSQL (existing)

One new ORM model `pipeline_tasks` for task state persistence:

```sql
CREATE TABLE pipeline_tasks (
    task_id UUID PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL,         -- Announcement source identifier
    content_hash VARCHAR(64) NOT NULL,        -- SHA256 for content dedup
    business_key VARCHAR(255) NOT NULL,       -- ticker:fiscal_year:report_type
    state VARCHAR(20) NOT NULL DEFAULT 'pending',
    ticker VARCHAR(20) REFERENCES stocks(ticker),
    pdf_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    result_summary JSONB,

    CONSTRAINT uq_source_content UNIQUE (source_id, content_hash),
    CONSTRAINT uq_business_key UNIQUE (business_key)
);
```

This uses the same SQLAlchemy async session pattern as existing models. Add via Alembic migration.

### PyMuPDF (existing pdf_processor.py)

Current `pdf_processor.py` handles extraction (`extract_pdf_content`), parent/child chunking, and table preservation. The pipeline adds:

1. **Download step**: Uses `httpx` (already in deps) to fetch PDF, `aiofiles` to write to temp storage
2. **Parse step**: Calls existing `extract_pdf_content()` -> `chunk_into_parents()` -> `chunk_parents_into_children()`
3. **Embed step**: Calls existing `rag/embeddings.py` and `rag/vector_store.py` (Qdrant upsert)

No changes to PyMuPDF usage or PDF processing logic. The pipeline orchestrates existing functions.

### httpx (existing)

Already in pyproject.toml (>=0.27.0). Used for downloading PDFs from announcement sources. No version change needed.

---

## Installation

```bash
# New dependencies for v1.1 pipeline
uv add "arq>=0.28.0"
uv add "sse-starlette>=3.4.0"
uv add "aiofiles>=25.1.0"
uv add "tenacity>=9.1.0"
```

**No new infrastructure services.** All new capabilities run on existing Redis + PostgreSQL + FastAPI.

---

## Dependency Summary

| New Package | Version | New Infrastructure? | Purpose |
|-------------|---------|---------------------|---------|
| arq | 0.28.0 | No (uses existing Redis) | Task queue + cron scheduling |
| sse-starlette | 3.4.0 | No | SSE push notifications |
| aiofiles | 25.1.0 | No | Async file I/O for PDF download |
| tenacity | 9.1.0 | No | Retry decorators for external calls |

**Total new infrastructure services: ZERO.**

---

## Architecture: Worker Deployment

```
[FastAPI App Process]                    [Arq Worker Process (separate)]
     |                                          |
     |-- lifespan():                            |-- on_startup():
     |     - Redis cache (existing)             |     - HTTP client pool (httpx)
     |     - Arq pool (enqueue only)            |     - DB session factory
     |     - Qdrant health check (existing)     |     - Redis connection
     |                                          |     - Watcher instance
     |-- POST /api/v1/pipeline/trigger          |
     |     -> arq_pool.enqueue_job()            |-- cron_jobs:
     |                                          |     check_announcements()
     |-- GET /api/v1/pipeline/events (SSE)      |       -> enqueue_job("process_report")
     |     -> EventSourceResponse               |
     |     -> subscribes to Redis pub/sub       |-- process_report():
     |                                          |     1. DOWNLOADING: httpx GET -> aiofiles write
     |                                          |     2. PARSING: PyMuPDF extract -> chunk
     |                                          |     3. ANALYZING: M-Score/DCF/yield calc
     |                                          |     4. EMBEDDING: bge-m3 -> Qdrant upsert
     |                                          |     5. DONE: Redis PUBLISH notification
```

Communication between FastAPI and Arq worker:
- **Job submission**: FastAPI enqueues via Arq pool -> Redis
- **Status queries**: FastAPI reads `pipeline_tasks` table in PostgreSQL
- **Notifications**: Worker publishes to Redis channel -> FastAPI SSE endpoint subscribes

---

## Confidence Assessment

| Dependency | Confidence | Reason |
|------------|------------|--------|
| arq | HIGH | Verified via Context7 docs (177 code snippets, HIGH reputation source). PyPI stable 0.28.0. Built-in cron_jobs eliminates APScheduler. asyncio-native fits our stack. Same author as Pydantic. Redis-only, no new infra. |
| sse-starlette | HIGH | Verified via Context7 docs (50 snippets, HIGH reputation). PyPI stable 3.4.1. Production-ready, designed for FastAPI/Starlette. Broadcast and disconnect patterns well-documented. |
| aiofiles | HIGH | PyPI stable 25.1.0. Widely used. Simple API, no architectural risk. |
| tenacity | HIGH | PyPI stable 9.1.4. Industry standard Python retry library. Async-native `@retry` decorator. |
| No APScheduler | MEDIUM | Arq cron_jobs cover our periodic scheduling needs (hourly announcement checks). Risk: if future milestones need complex scheduling (e.g., "every 3rd Thursday of the quarter"), Arq cron is limited to standard cron expressions. Acceptable tradeoff for MVP -- can add APScheduler later if needed. |
| Custom state machine | HIGH | 5-state linear FSM is trivially implementable. No library warranted. Enum + frozenset pattern is Pythonic, immutable, and testable. |
| No new infrastructure | HIGH | All four new packages use existing Redis/PostgreSQL. No new Docker containers, no new services to deploy or monitor. |

---

## Sources

- Arq documentation: https://arq-docs.helpmanual.io/ (Context7 verified, 177 code snippets, HIGH source reputation)
- Arq PyPI: https://pypi.org/project/arq/ -- latest stable 0.28.0
- Arq Context7 ID: /websites/arq-docs_helpmanual_io (benchmark 81.47)
- APScheduler Context7: https://context7.com/agronholm/apscheduler/ -- shows v4 AsyncScheduler but v4 is alpha-only (4.0.0a6)
- APScheduler PyPI: https://pypi.org/project/APScheduler/ -- latest stable 3.11.2, latest pre-release 4.0.0a6
- sse-starlette Context7: https://context7.com/sysid/sse-starlette/ -- 50 code snippets, FastAPI integration examples
- sse-starlette PyPI: https://pypi.org/project/sse-starlette/ -- latest stable 3.4.1
- aiofiles PyPI: https://pypi.org/project/aiofiles/ -- latest stable 25.1.0
- tenacity PyPI: https://pypi.org/project/tenacity/ -- latest stable 9.1.4
- python-statemachine PyPI: https://pypi.org/project/python-statemachine/ -- latest 3.0.0 (considered, rejected)
- taskiq PyPI: https://pypi.org/project/taskiq/ -- latest 0.12.2 (considered, rejected)
- Existing codebase files: pyproject.toml, main.py, utils/cache.py, rag/pdf_processor.py
