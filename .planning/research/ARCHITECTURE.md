# Architecture Patterns: Smart Financial Report Pipeline

**Domain:** Event-driven financial report monitoring and processing pipeline for a brownfield FastAPI + async SQLAlchemy backend
**Researched:** 2026-05-01
**Overall confidence:** HIGH

## Recommended Architecture

The pipeline adds four new subsystems to the existing layered architecture. These are not new layers -- they are peer modules at the Service and Infrastructure levels that wire into the existing FastAPI lifecycle. The design keeps the scheduler, task queue, and state machine in-process with the FastAPI application, avoiding separate process management for the MVP scope.

```
                              FastAPI Application
                                      |
                    +-----------------+-----------------+
                    |                                  |
             +------+------+                    +------+------+
             |  API Routes  |                    |  Lifespan   |
             |  (new + old) |                    |  Manager    |
             +------+------+                    +------+------+
                    |                                  |
         +----------+----------+          +-----------+-----------+
         |                     |          |                       |
  +------+------+    +--------+------+   |  APScheduler 4        |
  | Pipeline    |    | Watcher       |   |  AsyncScheduler       |
  | Routes      |    | Service       |   |  (IntervalTrigger)    |
  | /pipeline/* |    | (polling)     |   |  + SQLAlchemyDataStore|
  +------+------+    +--------+------+   +-----------+-----------+
         |                     |                      |
         |              +------+------+                |
         |              | Notice     |                 |
         |              | Scraper    |                 |
         |              | (AKShare)  |                 |
         |              +------+-----+                 |
         |                     |                       |
  +------+------+    +--------+--------+               |
  | Pipeline    |    | PipelineJob     |<--------------+
  | Orchestrator|    | Repository      |
  | (state      |    +--------+--------+
  | machine)    |             |
  +------+------+             |
         |             +------+------+
         |             | PostgreSQL  |
         |             | pipeline_jobs
         |             | notices     |
         |             | documents   |
         |             +------+------+
         |                    |
  +------+------+    +--------+--------+
  | Downloader  |    | Existing        |
  | (httpx +    |    | DocumentService |
  | retry)      |    | (RAG pipeline)  |
  +------+------+    +--------+--------+
         |                    |
         |             +------+------+
         |             | RiskService  |
         +-----------> | ValuationSvc |
                       | YieldService |
                       | NarrativeSvc |
                       +------+------+
                              |
                       +------+------+
                       | External    |
                       | DataService |
                       | (cached)    |
                       +------+------+
                              |
                    +---------+---------+
                    |         |         |
               Redis Cache  Qdrant  PostgreSQL
```

### Why In-Process (Not Separate Workers)

The PROJECT.md key decisions already ruled out Celery + RabbitMQ in favor of Arq + Redis. However, for the CSI 300 scope (300 stocks, quarterly reports = ~1200 reports/year), the volume is so low that an in-process approach using APScheduler with SQLAlchemy data store is simpler and sufficient:

- **No separate worker process** to manage. APScheduler 4 runs tasks on the existing asyncio event loop.
- **No separate Redis-based task queue** needed at this scale. If volume grows beyond CSI 300, Arq can be added later without changing the state machine or pipeline logic.
- **APScheduler 4 with SQLAlchemyDataStore** uses the same PostgreSQL database the application already depends on, reusing the existing async engine. No new infrastructure.
- **Single process to deploy and monitor.** The lifespan context manager handles startup and shutdown cleanly.

If and when the pipeline needs to process reports for the full A-share universe (~5000 stocks), the orchestrator can be swapped from in-process APScheduler tasks to Arq-enqueued jobs, because the state machine and repository interfaces remain the same.

### Component Boundaries

| Component | Responsibility | Communicates With | New or Existing |
|-----------|---------------|-------------------|-----------------|
| **PipelineRoutes** | HTTP I/O for pipeline status, manual triggers, job listing | PipelineOrchestrator, PipelineJobRepository | NEW |
| **WatcherService** | Periodic polling of A-share announcement sources (巨潮/交易所 via AKShare) | NoticeScraper, PipelineJobRepository | NEW |
| **NoticeScraper** | Fetch new financial report announcements, normalize to common schema | AKShare (via existing ExternalDataService) | NEW |
| **PipelineOrchestrator** | State machine driving each job through PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE/FAILED | Downloader, DocumentService, RiskService, ValuationService, YieldService, NarrativeService, PipelineJobRepository | NEW |
| **Downloader** | HTTP download of PDF files with retry, checksum verification, deduplication | httpx, filesystem | NEW |
| **PipelineJobRepository** | CRUD for pipeline_jobs and notices tables | PostgreSQL via async SQLAlchemy | NEW |
| **APScheduler AsyncScheduler** | Triggers WatcherService polling at configurable intervals | WatcherService (via scheduled task) | NEW |
| **SSE EventSource** | Push pipeline job status updates to connected clients | PipelineOrchestrator (via asyncio.Queue fan-out) | NEW |
| **DocumentService** | PDF parsing, chunking, embedding, Qdrant storage | EXISTING -- called by PipelineOrchestrator | EXISTING |
| **RiskService, ValuationService, YieldService** | Deterministic financial calculations | EXISTING -- called by PipelineOrchestrator | EXISTING |
| **NarrativeService** | LLM narrative generation | EXISTING -- called by PipelineOrchestrator | EXISTING |

### Data Flow

**Flow 1: Automatic Pipeline (scheduler-triggered)**

```
APScheduler (every 30 min during market hours)
  -> WatcherService.check_new_announcements()
    -> NoticeScraper.fetch_recent_notices()
      -> AKShare API (announcement list)
    -> For each new notice:
      -> PipelineJobRepository.create(notice_id, ticker, url, sha256)
        -> Dedup check: sha256 + source_id unique constraint
      -> PipelineOrchestrator.enqueue_job(job_id)
        -> Update state: PENDING -> DOWNLOADING
        -> Downloader.download_pdf(url)
          -> Retry: exponential backoff, 3 attempts
          -> Verify: sha256 checksum
          -> Save to: ./downloads/{ticker}/{year}/{report_type}.pdf
        -> Update state: DOWNLOADING -> PARSING
        -> DocumentService.process_upload(pdf_bytes, ticker, metadata)
          -> Extract, chunk, embed, store in Qdrant
        -> Update state: PARSING -> ANALYZING
        -> ExternalDataService.get_financial_report(ticker, year)  [cached]
        -> RiskService.analyze_financial_risk(data)  [pure]
        -> ValuationService.calculate_dcf(data)  [pure]
        -> YieldService.analyze_yield_gap(data)  [pure]
        -> NarrativeService.generate_narrative(results)  [LLM]
        -> Persist analysis results via existing repositories
        -> Update state: ANALYZING -> DONE
        -> SSE broadcast: job completed
```

**Flow 2: Manual Trigger (API)**

```
POST /api/v1/pipeline/trigger
  Body: { "ticker": "600519.SH", "year": 2024, "report_type": "annual" }
  -> PipelineOrchestrator.create_and_run(ticker, year, report_type)
  -> Same state machine as Flow 1, but starting from a manual notice
  -> Returns: ApiResponse[PipelineJob] with job_id and initial state
```

**Flow 3: Status Monitoring (SSE)**

```
GET /api/v1/pipeline/events (SSE endpoint)
  -> EventSourceResponse with async generator
  -> Listens to asyncio.Queue fed by PipelineOrchestrator on state transitions
  -> Yields: { "job_id": "...", "state": "ANALYZING", "progress": 60 }
  -> Client disconnect detection via request.is_disconnected()
```

**Flow 4: Status Polling (REST)**

```
GET /api/v1/pipeline/jobs/{job_id}
  -> PipelineJobRepository.get_by_id(job_id)
  -> Returns: ApiResponse[PipelineJob] with full state, timestamps, error info

GET /api/v1/pipeline/jobs?ticker=600519.SH&state=DONE
  -> PipelineJobRepository.list_jobs(filters)
  -> Returns: ApiResponse[list[PipelineJob]] with pagination
```

## New Database Tables

### pipeline_jobs

```sql
CREATE TABLE pipeline_jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL REFERENCES stocks(ticker),
    notice_id       UUID REFERENCES notices(notice_id),
    source_url      TEXT NOT NULL,
    source_sha256   VARCHAR(64),               -- SHA256 of downloaded PDF
    state           VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    report_type     VARCHAR(20) NOT NULL,       -- 'annual', 'quarterly', 'semi'
    fiscal_year     INT NOT NULL,
    document_id     UUID REFERENCES documents(document_id),
    error_message   TEXT,
    retry_count     INT NOT NULL DEFAULT 0,
    max_retries     INT NOT NULL DEFAULT 3,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    CONSTRAINT uq_source_dedup UNIQUE (source_url, source_sha256)
);

CREATE INDEX idx_pipeline_jobs_ticker ON pipeline_jobs(ticker);
CREATE INDEX idx_pipeline_jobs_state ON pipeline_jobs(state);
CREATE INDEX idx_pipeline_jobs_created ON pipeline_jobs(created_at DESC);
```

### notices

```sql
CREATE TABLE notices (
    notice_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       VARCHAR(200) NOT NULL,      -- External ID from 巨潮/交易所
    ticker          VARCHAR(20) NOT NULL,
    title           TEXT NOT NULL,
    announcement_url TEXT NOT NULL,
    pdf_download_url TEXT,
    notice_date     DATE NOT NULL,
    report_type     VARCHAR(20),                 -- 'annual', 'quarterly', 'semi'
    fiscal_year     INT,
    is_processed    BOOLEAN NOT NULL DEFAULT FALSE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_source_id UNIQUE (source_id)
);

CREATE INDEX idx_notices_ticker_date ON notices(ticker, notice_date DESC);
CREATE INDEX idx_notices_unprocessed ON notices(is_processed) WHERE is_processed = FALSE;
```

### Why Two Tables Instead of One

The separation between `notices` and `pipeline_jobs` serves a clear purpose:

1. **Notices** represent raw announcement data from external sources. A single notice might be fetched multiple times before it is processed (e.g., the watcher polls every 30 minutes and sees the same announcement). The `source_id` unique constraint prevents duplicate ingestion.

2. **Pipeline jobs** represent processing attempts. A single notice can have multiple pipeline job attempts (if the first attempt fails and is retried). The `notice_id` foreign key links the job back to its source announcement.

3. **Deduplication** happens at two levels: `notices.source_id` prevents re-ingesting the same announcement, and `pipeline_jobs.source_url + source_sha256` prevents re-downloading the same PDF file.

## Patterns to Follow

### Pattern 1: APScheduler 4 + FastAPI Lifespan Integration

**What:** APScheduler 4's `AsyncScheduler` runs in-process, managed by FastAPI's lifespan context manager. Uses `SQLAlchemyDataStore` backed by the existing PostgreSQL database for schedule persistence.

**When:** Any periodic task (announcement polling, stale job cleanup) that needs to survive process restarts.

**Why APScheduler 4 over APScheduler 3:** APScheduler 4 is fully async-native, uses the same SQLAlchemy async engine the project already has, and integrates cleanly with FastAPI lifespan. No need for a separate thread or event loop bridging.

**Why SQLAlchemyDataStore over memory:** Schedule persistence means the watcher resumes after a process restart without missing polling cycles. Uses the existing asyncpg engine.

**Example:**
```python
# In main.py lifespan
from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker
from apscheduler.triggers.interval import IntervalTrigger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing cache/qdrant init ...

    # Initialize APScheduler with existing PostgreSQL
    from stockvaluefinder.db.base import engine as async_engine

    data_store = SQLAlchemyDataStore(async_engine)
    event_broker = AsyncpgEventBroker.from_async_sqla_engine(async_engine)
    scheduler = AsyncScheduler(data_store, event_broker)

    async with scheduler:
        # Register the watcher task
        await scheduler.add_schedule(
            watcher_service.check_new_announcements,
            IntervalTrigger(minutes=30),
            id="watcher_poll",
            conflict_policy=ConflictPolicy.replace,
        )
        await scheduler.start_in_background()
        app.state.scheduler = scheduler
        yield

    # Scheduler cleanup handled by async with exit
```

**Key detail:** `AsyncpgEventBroker.from_async_sqla_engine` reuses the existing SQLAlchemy async engine, so no additional database connection pool is needed. The APScheduler tables are created automatically by the data store on first run.

**Confidence:** HIGH -- verified against APScheduler 4 official Context7 documentation showing exact FastAPI lifespan integration pattern.

### Pattern 2: Python State Machine for Pipeline Jobs

**What:** Each pipeline job progresses through a defined state machine: PENDING -> DOWNLOADING -> PARSING -> ANALYZING -> DONE (or FAILED at any transition). The state is persisted in `pipeline_jobs.state` column and transitions are validated.

**When:** Any long-running multi-step process with observable intermediate states.

**Why not python-statemachine library:** The state machine for pipeline jobs is simple (5 states, linear transitions, one failure path from each). Using a library adds a dependency for minimal benefit. A lightweight enum + transition validator is more appropriate and easier to test.

**Example:**
```python
from enum import StrEnum

class PipelineState(StrEnum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    PARSING = "PARSING"
    ANALYZING = "ANALYZING"
    DONE = "DONE"
    FAILED = "FAILED"

# Valid transitions (from_state -> set of valid to_states)
VALID_TRANSITIONS: dict[PipelineState, set[PipelineState]] = {
    PipelineState.PENDING: {PipelineState.DOWNLOADING, PipelineState.FAILED},
    PipelineState.DOWNLOADING: {PipelineState.PARSING, PipelineState.FAILED},
    PipelineState.PARSING: {PipelineState.ANALYZING, PipelineState.FAILED},
    PipelineState.ANALYZING: {PipelineState.DONE, PipelineState.FAILED},
    PipelineState.DONE: set(),   # terminal
    PipelineState.FAILED: set(), # terminal (unless retry resets to PENDING)
}

class InvalidStateTransition(StockValueFinderError):
    """Raised when a pipeline job state transition is invalid."""

def validate_transition(
    current: PipelineState,
    target: PipelineState,
) -> None:
    """Validate that a state transition is allowed.

    Args:
        current: Current pipeline state.
        target: Target pipeline state.

    Raises:
        InvalidStateTransition: If the transition is not valid.
    """
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise InvalidStateTransition(
            f"Invalid transition: {current} -> {target}",
            details={"current": current, "target": target},
        )
```

**Retry handling:** When a job fails, `state` is set to `FAILED` and `retry_count` is incremented. If `retry_count < max_retries`, a separate retry mechanism resets the state to `PENDING` and the job is re-queued. This avoids infinite retry loops while allowing transient failures (network, API rate limits) to self-heal.

**Confidence:** HIGH -- straightforward enum-based state machine, well-proven pattern.

### Pattern 3: Downloader with Exponential Backoff Retry

**What:** HTTP client that downloads PDF files with configurable retry, checksum verification, and idempotency.

**When:** Downloading financial report PDFs from 巨潮/交易所 or other external sources.

**Why httpx over requests:** The project already depends on `httpx>=0.27.0` for async HTTP. httpx supports async natively, has connection pooling, and integrates with FastAPI's async model.

**Example:**
```python
import hashlib
import asyncio
from pathlib import Path

import httpx

from stockvaluefinder.utils.errors import ExternalAPIError


class ReportDownloader:
    """Download financial report PDFs with retry and verification."""

    def __init__(
        self,
        download_dir: str = "./downloads",
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: float = 60.0,
    ) -> None:
        self._download_dir = Path(download_dir)
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
                headers={"User-Agent": "StockValueFinder/1.1"},
            )
        return self._client

    async def download(
        self,
        url: str,
        ticker: str,
        year: int,
        report_type: str,
        expected_sha256: str | None = None,
    ) -> tuple[Path, str]:
        """Download a PDF with retry and return (file_path, actual_sha256).

        Args:
            url: Direct download URL for the PDF.
            ticker: Stock ticker for directory structure.
            year: Fiscal year for directory structure.
            report_type: Report type for filename.
            expected_sha256: Optional SHA256 to verify against.

        Returns:
            Tuple of (file_path, sha256_hex).

        Raises:
            ExternalAPIError: If download fails after all retries.
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                client = await self._ensure_client()
                response = await client.get(url)
                response.raise_for_status()

                pdf_bytes = response.content
                actual_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

                if expected_sha256 and actual_sha256 != expected_sha256:
                    raise ExternalAPIError(
                        f"SHA256 mismatch: expected {expected_sha256}, "
                        f"got {actual_sha256}",
                        service="report_downloader",
                    )

                # Save to disk
                save_dir = self._download_dir / ticker / str(year)
                save_dir.mkdir(parents=True, exist_ok=True)
                file_path = save_dir / f"{report_type}.pdf"
                file_path.write_bytes(pdf_bytes)

                return file_path, actual_sha256

            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = self._base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        raise ExternalAPIError(
            f"Download failed after {self._max_retries} attempts: {last_error}",
            service="report_downloader",
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

**Confidence:** HIGH -- standard httpx + retry pattern, directly uses existing project dependency.

### Pattern 4: SSE for Pipeline Status Push

**What:** Server-Sent Events endpoint that pushes pipeline job state transitions to connected clients in real time.

**When:** Users need to know when a pipeline job completes without polling.

**Why SSE over WebSocket:** PROJECT.md explicitly states "Real-time WebSocket updates -- SSE sufficient for status push" in Out of Scope. SSE is simpler (one direction, server to client), works with standard HTTP, and `sse-starlette` provides production-ready handling.

**Example:**
```python
import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from stockvaluefinder.services.pipeline_events import PipelineEventBus

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


async def _event_generator(
    request: Request,
    event_bus: PipelineEventBus,
) -> AsyncGenerator[dict, None]:
    """Yield SSE events for pipeline state transitions."""
    queue = event_bus.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
                yield {
                    "event": event["state"].lower(),
                    "data": json.dumps(event),
                    "id": event["job_id"],
                }
            except asyncio.TimeoutError:
                # Keepalive ping to prevent proxy timeout
                yield {"event": "ping", "data": ""}
    finally:
        event_bus.unsubscribe(queue)


@router.get("/events")
async def pipeline_events(request: Request) -> EventSourceResponse:
    """SSE endpoint for real-time pipeline status updates."""
    event_bus = request.app.state.pipeline_event_bus
    return EventSourceResponse(
        _event_generator(request, event_bus),
        ping=15,
        send_timeout=30,
    )
```

**PipelineEventBus (fan-out pattern):**
```python
class PipelineEventBus:
    """Fan-out event bus for pipeline state transitions."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.remove(queue)

    async def publish(self, event: dict) -> None:
        for queue in self._subscribers:
            await queue.put(event)
```

**Confidence:** HIGH -- verified sse-starlette Context7 documentation for EventSourceResponse pattern.

### Pattern 5: PipelineOrchestrator (State Machine Driver)

**What:** A service class that drives pipeline jobs through the state machine, calling appropriate handlers at each state.

**When:** Any multi-step processing pipeline with observable intermediate states.

**Example:**
```python
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.models.pipeline import PipelineJob, PipelineState
from stockvaluefinder.repositories.pipeline_repo import PipelineJobRepository
from stockvaluefinder.services.downloader import ReportDownloader
from stockvaluefinder.services.document_service import DocumentService
from stockvaluefinder.services.pipeline_events import PipelineEventBus

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Drive pipeline jobs through the PENDING -> DONE state machine."""

    def __init__(
        self,
        session: AsyncSession,
        downloader: ReportDownloader,
        event_bus: PipelineEventBus,
    ) -> None:
        self._session = session
        self._repo = PipelineJobRepository(session)
        self._downloader = downloader
        self._event_bus = event_bus

    async def execute_job(self, job_id: str) -> PipelineJob:
        """Execute a single pipeline job to completion or failure.

        Args:
            job_id: UUID of the pipeline job to execute.

        Returns:
            Updated PipelineJob with final state.
        """
        job = await self._repo.get_by_id(job_id)
        if job is None:
            raise DataValidationError(f"Job {job_id} not found")

        try:
            # State: PENDING -> DOWNLOADING
            job = await self._transition(job, PipelineState.DOWNLOADING)

            # Download PDF
            file_path, sha256 = await self._downloader.download(
                url=job.source_url,
                ticker=job.ticker,
                year=job.fiscal_year,
                report_type=job.report_type,
            )
            pdf_bytes = file_path.read_bytes()

            # State: DOWNLOADING -> PARSING
            job = await self._transition(job, PipelineState.PARSING)

            # Process through RAG pipeline (existing DocumentService)
            doc_service = DocumentService(self._session)
            upload_result = await doc_service.process_upload(
                document_id=str(uuid4()),
                ticker=job.ticker,
                file_name=file_path.name,
                file_path=str(file_path),
                pdf_bytes=pdf_bytes,
            )

            # State: PARSING -> ANALYZING
            job = await self._transition(job, PipelineState.ANALYZING)

            # Trigger analysis (existing services)
            await self._run_analysis(job)

            # State: ANALYZING -> DONE
            job = await self._transition(job, PipelineState.DONE)
            return job

        except Exception as exc:
            logger.exception("Pipeline job %s failed: %s", job_id, exc)
            job = await self._transition(
                job,
                PipelineState.FAILED,
                error_message=str(exc),
            )
            return job

    async def _transition(
        self,
        job: PipelineJob,
        target: PipelineState,
        error_message: str | None = None,
    ) -> PipelineJob:
        """Transition job to new state, persist, and publish event."""
        validate_transition(job.state, target)
        updated = await self._repo.update_state(
            job_id=job.job_id,
            new_state=target,
            error_message=error_message,
        )
        await self._session.commit()

        await self._event_bus.publish({
            "job_id": job.job_id,
            "ticker": job.ticker,
            "state": target,
            "error_message": error_message,
        })
        return updated
```

**Confidence:** HIGH -- standard state machine driver pattern.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Scheduler Tasks with DB Sessions Across Yield Points

**What:** Holding a SQLAlchemy async session open across `await` points in a scheduled task.

**Why bad:** APScheduler tasks run on the event loop. If a task holds a session open and another task or request tries to use the same connection from the pool, you get deadlocks or session leaks.

**Instead:** Create a new session for each scheduled task invocation, using the existing `async_session_maker` from `db/base.py`. Close it when the task completes.

### Anti-Pattern 2: Using BackgroundTasks for Pipeline Processing

**What:** Using FastAPI's `BackgroundTasks` (as currently done in `documents_routes.py`) for pipeline jobs.

**Why bad:** `BackgroundTasks` runs in the same process but has no state tracking, no retry, no deduplication, and no observability. If the process restarts, in-flight background tasks are lost with no record. The new pipeline needs persistent state.

**Instead:** Use the PipelineOrchestrator with database-backed state. APScheduler handles the scheduling. The `BackgroundTasks` pattern remains valid for the existing manual upload endpoint (which is a different use case -- user-triggered, single-shot).

### Anti-Pattern 3: Monolithic Pipeline Service

**What:** A single `PipelineService` class that handles watching, downloading, parsing, analyzing, and notification.

**Why bad:** Violates single responsibility, makes testing impossible without mocking everything, and makes it hard to retry individual steps.

**Instead:** Separate components: `WatcherService` (polling), `ReportDownloader` (download), `PipelineOrchestrator` (state machine driver), `PipelineEventBus` (notification). Each can be tested independently.

### Anti-Pattern 4: Blocking Downloads in the Event Loop

**What:** Using `requests.get()` or synchronous file I/O in the pipeline orchestrator.

**Why bad:** Blocks the asyncio event loop. A 50MB PDF download taking 30 seconds would freeze all other request handling.

**Instead:** Use `httpx.AsyncClient` for downloads and `aiofiles` or `asyncio.to_thread()` for file I/O. The existing codebase already uses httpx for async HTTP.

### Anti-Pattern 5: Polling Without Deduplication

**What:** The watcher fetches announcements every 30 minutes and creates pipeline jobs without checking if they already exist.

**Why bad:** Duplicate pipeline jobs waste download bandwidth, re-process the same PDF, and create confusing duplicate analysis results.

**Instead:** Two-level deduplication: (1) `notices.source_id` unique constraint prevents re-ingesting the same announcement, (2) `pipeline_jobs.source_url + source_sha256` prevents re-downloading the same file. The WatcherService queries for existing notices before creating new ones.

## Scalability Considerations

| Concern | CSI 300 Scope | Full A-Share (~5000 stocks) |
|---------|---------------|---------------------------|
| Announcement polling | ~1200 notices/year, trivial | ~20,000 notices/year, still manageable |
| Concurrent downloads | 1-2 at a time, in-process | Need queue (Arq) with worker pool |
| PDF storage | ~1200 files, ~60GB total | ~20,000 files, ~1TB -- need S3/MinIO |
| Qdrant vectors | ~24,000 chunks/year | ~400,000 chunks/year -- still fine for single Qdrant |
| APScheduler | In-process, interval trigger | Need distributed scheduler or Arq cron |
| SSE connections | <10 concurrent users | Need proper fan-out with Redis pub/sub |

**Key insight for MVP:** CSI 300 means at most 300 annual reports per year (one per stock). Even with quarterly reports, that is ~1200 documents total. The in-process approach with APScheduler is more than sufficient. The architecture is designed to swap APScheduler for Arq when scale demands it, without changing the orchestrator or state machine.

## Component Integration Details

### New Files to Create

```
stockvaluefinder/
  api/
    pipeline_routes.py        # GET /events (SSE), GET /jobs, GET /jobs/{id}, POST /trigger
  services/
    pipeline_orchestrator.py  # State machine driver (execute_job, _transition)
    watcher_service.py        # Periodic announcement polling
    downloader.py             # PDF download with retry
    pipeline_events.py        # PipelineEventBus (asyncio.Queue fan-out)
  models/
    pipeline.py               # PipelineState enum, PipelineJob Pydantic, NoticeCreate
  db/models/
    pipeline_job.py           # PipelineJobDB ORM model
    notice.py                 # NoticeDB ORM model
  repositories/
    pipeline_repo.py          # PipelineJobRepository (CRUD, state queries)
    notice_repo.py            # NoticeRepository (upsert by source_id, find unprocessed)
  alembic/versions/
    009_pipeline_tables.py    # Migration: notices + pipeline_jobs tables
```

### Existing Files to Modify

| File | Change | Risk |
|------|--------|------|
| `main.py` | Add APScheduler init/shutdown to lifespan, store scheduler + event bus on app.state | LOW (additive, existing lifespan preserved) |
| `config.py` | Add `PipelineConfig` frozen dataclass (polling interval, retry settings, download dir) | LOW (additive) |
| `dependencies.py` | Add `get_pipeline_orchestrator()` and `get_event_bus()` DI functions | LOW (additive) |
| `pyproject.toml` | Add `apscheduler>=4.0.0`, `sse-starlette>=2.0.0` | LOW (new dependencies) |
| `db/base.py` | Export engine for APScheduler SQLAlchemyDataStore reuse | LOW (already exported) |
| `db/models/__init__.py` | Import new ORM models | LOW (additive) |
| `models/enums.py` | (No change -- PipelineState in its own file per domain separation) | N/A |

### Dependency on Existing Components

```
PipelineOrchestrator
  DEPENDS ON (runtime):
    - ReportDownloader (new)
    - DocumentService (existing: process_upload)
    - PipelineJobRepository (new)
    - PipelineEventBus (new)
    - risk_service.analyze_financial_risk (existing: pure function)
    - valuation_service.calculate_dcf (existing: pure function)
    - yield_service.analyze_yield_gap (existing: pure function)
    - narrative_service.generate_narrative (existing: LLM call)
    - ExternalDataService (existing: get_financial_report, cached)

WatcherService
  DEPENDS ON (runtime):
    - NoticeScraper (new, uses AKShare)
    - NoticeRepository (new)
    - PipelineJobRepository (new)
    - PipelineOrchestrator (new: enqueue_job)

APScheduler
  DEPENDS ON (runtime):
    - SQLAlchemy async engine (existing: db.base.engine)
    - asyncpg event broker (existing: same engine)
    - WatcherService (new)
```

## Build Order (Dependency Analysis)

The components have a clear dependency chain that dictates build order:

```
Phase A: Database Schema + State Machine
  (no runtime dependencies on other new components)
  |
  v
Phase B: Downloader + File Storage
  (depends on: state machine for error handling)
  |
  v
Phase C: Pipeline Orchestrator (integrate with existing services)
  (depends on: state machine, downloader, existing DocumentService)
  |
  v
Phase D: Watcher Service + APScheduler Integration
  (depends on: orchestrator to enqueue jobs, config)
  |
  v
Phase E: API Routes + SSE Notification
  (depends on: orchestrator, event bus)
```

**Rationale:**

1. **Database schema first** because everything else needs the `pipeline_jobs` and `notices` tables. The state machine enum and validation logic are pure functions with no external dependencies. This phase also includes the Alembic migration.

2. **Downloader second** because it is self-contained (httpx + retry + file I/O) and can be tested in isolation with mocked HTTP responses. It depends on the state machine for error reporting but not on the orchestrator.

3. **Pipeline orchestrator third** because it wires together the state machine, downloader, and existing services (DocumentService, RiskService, etc.). It cannot be tested without the state machine and downloader, but does not need the watcher or API routes.

4. **Watcher + scheduler fourth** because the watcher depends on the orchestrator to create and execute jobs. The APScheduler integration touches the lifespan in `main.py`, which is a single additive change.

5. **API routes + SSE last** because they are the thinnest layer -- just HTTP I/O delegating to the orchestrator and event bus. They depend on everything above but are themselves simple.

## Sources

- APScheduler 4 FastAPI integration pattern -- HIGH confidence: Context7 documentation, official GitHub examples
- APScheduler 4 SQLAlchemyDataStore + AsyncpgEventBroker -- HIGH confidence: Context7 documentation showing exact async engine reuse pattern
- Arq job deduplication via `_job_id` parameter -- HIGH confidence: Context7 documentation from arq-docs.helpmanual.io
- sse-starlette EventSourceResponse pattern -- HIGH confidence: Context7 documentation showing async generator + disconnect detection
- python-statemachine async support -- HIGH confidence: Context7 documentation (evaluated but decided against using the library for simplicity)
- Existing codebase analysis (main.py, config.py, db/base.py, dependencies.py, documents_routes.py, document_service.py) -- HIGH confidence: direct observation of patterns, lifespans, DI, and service layer
- APScheduler 4 CronTrigger and IntervalTrigger -- HIGH confidence: Context7 documentation
