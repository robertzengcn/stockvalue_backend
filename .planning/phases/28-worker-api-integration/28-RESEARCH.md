# Phase 28: Worker & API Integration - Research

**Researched:** 2026-06-04
**Domain:** arq cron workers, FastAPI REST endpoints, authentication/authorization, watchlist integration
**Confidence:** HIGH

## Summary

Phase 28 wraps the ScanOrchestrator from Phase 27 with two integration layers: (1) arq cron jobs that run scheduled daily and weekly scans as background worker tasks, and (2) FastAPI REST endpoints that let authenticated users query scan results, trigger manual scans, and add candidates to their watchlist. This is the final phase of v1.5 and does NOT introduce new calculation logic -- it wires existing components into the operational infrastructure.

The project already has a mature arq worker infrastructure from the disclosure watcher (Phase 6-8). The existing `WorkerSettings` class in `pipeline/worker.py` defines cron jobs, startup/shutdown hooks, and job functions. The new scanner cron jobs should be added to this existing worker (or to a separate `ScannerWorkerSettings` class) following the same patterns. The FastAPI routes should follow the established patterns in `admin_routes.py` (admin-only with `require_admin` dependency), `risk_routes.py` (domain analysis endpoints), and the existing `ApiResponse[T]` generic envelope.

The key architectural decision is that manual scan triggers enqueue an arq job asynchronously rather than running synchronously. The API returns immediately with the run_id, and users poll for status via the runs query endpoint. This prevents API timeouts on scans that can take 10-30 minutes for 800 stocks.

**Primary recommendation:** Create three new files: (1) `market_scanner/worker.py` with a `ScannerWorkerSettings` class containing daily and weekly cron jobs plus a `run_market_scan` job function, (2) `api/scanner_routes.py` with REST endpoints for runs, candidates, candidate detail, manual trigger, and watchlist integration, and (3) add Pydantic response models for API output in `models/market_scanner.py`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXE-01 | Scheduled daily light scan (sync constituents, fetch prices, coarse screen, DCF top N, generate candidates) via arq cron | Existing `WorkerSettings` pattern with `cron()` function; new cron job fires at post-market-close (09:30 UTC = 17:30 CST); calls `ScanOrchestrator.run_scan()` with `ScanType.DAILY` for each configured index code |
| EXE-02 | Scheduled weekly deep scan (refresh financials, full risk, Alpha scores, recalculate composites) via arq cron | Same pattern as daily but `ScanType.WEEKLY`; runs on a specific weekday (e.g., Saturday 02:00 UTC); supplementary logic that may extend `ScanOrchestrator` or call additional services |
| EXE-03 | Manual scan trigger API (admin only, configurable params, enqueues arq job async) | FastAPI POST endpoint with `require_admin` dependency; validates params via Pydantic; enqueues via `arq_pool.enqueue_job()`; returns `{success: True, data: {run_id, status: "pending"}}` immediately |
| EXE-05 | Scan results API - runs (pagination, filter by status/scan type, latest run per index) | FastAPI GET endpoint with query params for pagination/filtering; reuses `MarketScanRunRepository.get_by_status()` and `get_latest_run()`; may need new `list_runs()` method with pagination |
| EXE-06 | Scan results API - candidates (pagination, filter by index code, sort by rank/score/safety margin/yield gap) | FastAPI GET endpoint; new repository method with dynamic ORDER BY based on sort param; extracts sortable fields from `screening_snapshot` JSONB or adds dedicated columns |
| EXE-07 | Scan results API - candidate detail (reasons, risk flags, screening snapshot, analysis references, audit trail) | FastAPI GET endpoint; returns full `screening_snapshot` JSONB from `MarketScanCandidateDB`; may need Pydantic response model for structured output |
| EXE-08 | Candidate-to-watchlist integration (add candidate to watchlist, duplicate handling with already_exists flag) | Calls existing `WatchlistRepository.add()`; checks for existing via `WatchlistRepository.get_by_ticker()` first; returns `{success: True, data: {ticker, already_exists: bool}}` |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scheduled scan triggering | Worker (arq cron) | Redis (job queue) | Cron jobs run in arq worker process, not in FastAPI |
| Manual scan trigger | API / Backend (FastAPI) | Worker (arq job) | API enqueues, worker executes |
| Scan run execution | Worker (arq job) | Database (repositories) | Heavy processing belongs in worker, not API |
| Scan run history queries | API / Backend (FastAPI) | Database (repositories) | Read-only query via repository pattern |
| Candidate list queries | API / Backend (FastAPI) | Database (repositories) | Paginated reads with dynamic sorting |
| Candidate detail queries | API / Backend (FastAPI) | Database (repositories) | Single-record JSONB retrieval |
| Watchlist integration | API / Backend (FastAPI) | Database (WatchlistRepository) | Reuses existing watchlist infrastructure |
| Auth/authorization | API / Backend (FastAPI middleware) | -- | Existing JWT + require_admin pattern |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| arq | 0.25.0 | Background job queue with cron support | Already installed, existing worker infrastructure [VERIFIED: installed] |
| FastAPI | 0.133+ | REST API endpoints | Existing project standard [VERIFIED: pyproject.toml] |
| Pydantic 2.12+ | 2.12+ | Request/response validation | Existing project standard [VERIFIED: pyproject.toml] |
| SQLAlchemy 2.0+ | 2.0+ | Async ORM queries | Existing project standard [VERIFIED: pyproject.toml] |
| pytest 9.0+ | 9.0+ | Testing with async support | Existing project standard [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| redis (via arq) | bundled | Job queue backend for arq | Required for all worker operations |
| PyJWT | installed | Token validation for auth middleware | Required for authenticated endpoints |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate `ScannerWorkerSettings` | Add scan jobs to existing `WorkerSettings` | Separate class allows independent worker scaling but requires running a second arq process; adding to existing is simpler for MVP |
| New scanner routes file | Extend existing admin_routes | Scanner is a distinct domain; separate routes file follows project convention of one file per domain |

**Installation:**
No new packages required -- all dependencies already in pyproject.toml.

**Version verification:**
```
arq: 0.25.0 (verified via uv run)
fastapi: >=0.133.1 (in pyproject.toml)
pydantic: >=2.12.5 (in pyproject.toml)
sqlalchemy: >=2.0.47 (in pyproject.toml)
```

## Architecture Patterns

### System Architecture Diagram

```
Phase 28 Worker & API Integration -- Data Flow

                         +-------------------------+
                         |   FastAPI Application    |
                         |   (main.py lifespan)     |
                         +------------+------------+
                                      |
                  +-------------------+-------------------+
                  |                   |                   |
                  v                   v                   v
    +-------------------+ +-------------------+ +-------------------+
    | scanner_routes.py | | auth middleware    | | arq_pool          |
    | (REST endpoints)  | | (get_current_user | | (enqueue_job)     |
    |                   | |  require_admin)   | |                   |
    | POST /runs        | +-------------------+ | Enqueue:          |
    | GET  /runs        |                       | run_market_scan   |
    | GET  /candidates  |                       +--------+----------+
    | GET  /candidate/  |                                |
    | POST /watchlist   |                                v
    +--------+----------+                 +------------------------------+
             |                            |  arq Worker Process           |
             |                            |  (ScannerWorkerSettings)      |
             |                            |                               |
             |                            |  Cron Jobs:                   |
             |                            |  - daily_scan (17:30 CST)     |
             |                            |  - weekly_scan (Sat 10:00 CST)|
             |                            |                               |
             |                            |  Job Function:                |
             |                            |  - run_market_scan(ctx, ...)  |
             |                            |    -> ScanOrchestrator        |
             |                            |       .run_scan(index, type)  |
             |                            +-------+------+----------------+
             |                                    |      |
             v                                    v      v
    +-------------------+          +---------------------------+
    | Phase 25 Repos    |          | Phase 27 Orchestrator     |
    | - ScanRunRepo     |<---------| - ScanOrchestrator        |
    | - CandidateRepo   |          | - BatchDataFetcher        |
    | - ConstituentRepo |          | - coarse_screener         |
    +-------------------+          | - composite_scorer        |
                                   | - reason_generator        |
    +-------------------+          +---------------------------+
    | WatchlistRepo     |
    | (pipeline/)       |
    | - add(ticker,name)|
    | - get_by_ticker() |
    +-------------------+
```

### Recommended Project Structure
```
stockvaluefinder/
+-- api/
|   +-- scanner_routes.py       # NEW: REST endpoints for scans, candidates, watchlist
|   +-- dependencies.py         # EXISTING: add scanner-specific deps if needed
+-- market_scanner/
|   +-- worker.py               # NEW: ScannerWorkerSettings + run_market_scan job
|   +-- scan_orchestrator.py    # EXISTING (Phase 27): no changes needed
|   +-- ...                     # EXISTING (Phase 25-27): no changes needed
+-- models/
|   +-- market_scanner.py       # EXISTING: add API response Pydantic models
+-- main.py                     # EXISTING: include scanner_router
+-- pipeline/
    +-- worker.py               # EXISTING: optionally add scanner cron jobs here

tests/unit/test_market_scanner/
+-- test_worker.py              # NEW: worker job function tests with mocked deps
+-- test_scanner_routes.py      # NEW: API endpoint tests with mocked deps
```

### Pattern 1: arq Cron Job for Daily Light Scan (EXE-01)
**What:** A cron job that fires after A-share market close and runs `ScanOrchestrator.run_scan()` for each configured index.
**When to use:** Scheduled daily scan.
**Example:**
```python
# Source: [CITED: existing pipeline/worker.py WorkerSettings pattern]
from arq import cron

async def daily_light_scan(ctx: dict[str, Any]) -> dict[str, str]:
    """Run daily post-market-close light scan for all configured indices.

    Called by arq cron at 09:30 UTC (17:30 CST) on weekdays.
    Checks for already-running scans before starting (PITFALLS Pitfall 5).
    """
    config = MarketScannerConfig()
    async with async_session_maker() as session:
        run_repo = MarketScanRunRepository(session)
        for index_code in config.index_codes:
            latest = await run_repo.get_latest_run(index_code)
            if latest is not None and latest.status in ("pending", "running"):
                logger.warning(
                    f"Skipping daily scan for {index_code}: "
                    f"run {latest.run_id} is {latest.status}"
                )
                continue
            orchestrator = _build_orchestrator(session, config)
            run_id = await orchestrator.run_scan(index_code, ScanType.DAILY)
            await session.commit()
            logger.info(f"Daily scan completed: {index_code} run_id={run_id}")
    return {"status": "completed"}

# In WorkerSettings:
cron_jobs = [
    cron(
        daily_light_scan,
        hour=9, minute=30,                # 09:30 UTC = 17:30 CST
        weekday={0, 1, 2, 3, 4},          # Mon-Fri only
        unique=True,
        max_tries=1,
        timeout=1800,                      # 30 min timeout
    ),
]
```

### Pattern 2: Manual Scan Trigger via arq Enqueue (EXE-03)
**What:** Admin user triggers a scan via POST endpoint. The API validates params, enqueues an arq job, and returns immediately with the run_id.
**When to use:** Manual scan trigger from admin UI.
**Example:**
```python
# Source: [CITED: existing pipeline_routes.py + main.py arq_pool pattern]
from fastapi import APIRouter, Depends, Request
from stockvaluefinder.api.dependencies import require_admin

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])

class ManualScanRequest(BaseModel):
    """Request body for manual scan trigger."""
    index_codes: list[str] = Field(
        default=["CSI300", "CSI500"],
        description="Index codes to scan",
    )
    scan_type: ScanType = Field(
        default=ScanType.DAILY,
        description="Scan type (daily or weekly)",
    )
    top_n: int | None = Field(
        default=None,
        description="Override top N (None = use config default)",
    )

@router.post("/runs", response_model=ApiResponse[dict])
async def trigger_manual_scan(
    request: ManualScanRequest,
    admin: dict = Depends(require_admin),
    req: Request = None,
) -> ApiResponse[dict]:
    """Trigger manual scan (admin only). Enqueues arq job, returns run_id."""
    arq_pool = req.app.state.arq_pool
    if arq_pool is None:
        return ApiResponse(success=False, error="Worker not available")

    job = await arq_pool.enqueue_job(
        "run_market_scan",
        index_codes=request.index_codes,
        scan_type=request.scan_type.value,
        top_n=request.top_n,
    )
    if job is None:
        return ApiResponse(success=False, error="Scan already queued")

    return ApiResponse(
        success=True,
        data={"job_id": job.job_id, "status": "queued"},
    )
```

### Pattern 3: Paginated Candidate List with Dynamic Sort (EXE-06)
**What:** GET endpoint returning candidates for a run with pagination, filtering, and dynamic sorting.
**When to use:** Candidate list queries from frontend.
**Example:**
```python
# Source: [CITED: admin_routes.py pagination pattern]
@router.get("/runs/{run_id}/candidates", response_model=ApiResponse[dict])
async def list_candidates(
    run_id: UUID,
    index_code: str | None = None,
    sort_by: str = "composite_score",
    sort_order: str = "desc",
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict]:
    """List candidates for a scan run with pagination and sorting."""
    candidate_repo = MarketScanCandidateRepository(db)
    candidates, total = await candidate_repo.get_candidates_paginated(
        run_id=run_id,
        index_code=index_code,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=min(limit, 100),
    )
    # Map ORM to response models...
    return ApiResponse(success=True, data={...})
```

### Pattern 4: Candidate-to-Watchlist Integration (EXE-08)
**What:** Add a scan candidate to the user's watchlist. Uses existing WatchlistRepository.
**When to use:** User clicks "Add to Watchlist" on a candidate.
**Example:**
```python
# Source: [CITED: WatchlistRepository.add() and .get_by_ticker() methods]
@router.post("/candidates/{candidate_id}/watchlist", response_model=ApiResponse[dict])
async def add_candidate_to_watchlist(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict]:
    """Add a scan candidate to user's watchlist."""
    candidate_repo = MarketScanCandidateRepository(db)
    candidate = await candidate_repo.get_by_id(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    watchlist_repo = WatchlistRepository(db)
    existing = await watchlist_repo.get_by_ticker(candidate.ticker)

    if existing is not None:
        return ApiResponse(
            success=True,
            data={"ticker": candidate.ticker, "already_exists": True},
        )

    await watchlist_repo.add(candidate.ticker, candidate.screening_snapshot.get("name", ""))
    await db.commit()

    return ApiResponse(
        success=True,
        data={"ticker": candidate.ticker, "already_exists": False},
    )
```

### Anti-Patterns to Avoid
- **Anti-pattern: Running scan synchronously in API handler.** `POST /runs` must enqueue an arq job and return immediately. Running scan inline causes API timeouts (30 min scans exceed typical HTTP timeouts). [CITED: PITFALLS.md Phase 4 Warning]
- **Anti-pattern: Using arq cron with CST timezone.** arq cron uses UTC. 17:30 CST = 09:30 UTC. Getting this wrong means scans fire at wrong time. [CITED: PITFALLS.md Phase 4 Warning]
- **Anti-pattern: Not checking for concurrent scans before starting.** Two cron jobs or manual triggers can create overlapping scans. Always check `get_latest_run()` status before starting. [CITED: PITFALLS.md Pitfall 5]
- **Anti-pattern: Exposing raw AKShare error messages in API responses.** Internal infrastructure details leak to users. Sanitize all errors. [CITED: PITFALLS.md Security Mistakes]
- **Anti-pattern: Missing rate limiting on scan endpoints.** Even admin-only endpoints need rate limits to prevent accidental DDoS of AKShare. [CITED: PITFALLS.md Security Mistakes]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Background job scheduling | Custom scheduler with asyncio.sleep | `arq.cron()` + `WorkerSettings` | Existing infrastructure, Redis-backed persistence, retries, unique jobs |
| Job enqueuing from API | Custom Redis pub/sub | `arq_pool.enqueue_job()` | Already in main.py lifespan, handles serialization |
| Auth/authorization for admin endpoints | Custom role-checking middleware | `require_admin` from `api/dependencies.py` | Existing pattern, validated across all admin routes |
| JWT token validation | Custom header parsing | `get_current_user` from `api/dependencies.py` | Handles expiry, blacklist, DB lookup, disabled accounts |
| Watchlist operations | Custom watchlist logic | `WatchlistRepository.add()` + `get_by_ticker()` | Already handles DB persistence, session management |
| API response envelope | Custom response formatting | `ApiResponse[T]` generic model | Frozen, consistent, all existing routes use it |
| Pagination | Custom offset/limit logic | `PaginationMeta` model + repository pagination | Standard pattern across admin/analytics routes |
| Candidate duplicate check | Custom query | `WatchlistRepository.get_by_ticker()` | Already handles PK-based lookup |

**Key insight:** This phase is pure integration. Every piece of business logic (scanning, scoring, risk review, reason generation) was built in Phases 25-27. Phase 28 only wires those components into arq workers and FastAPI routes.

## Common Pitfalls

### Pitfall 1: arq Cron Timezone Confusion (UTC vs CST)
**What goes wrong:** A-share market closes at 15:00 CST. Setting cron `hour=17, minute=30` runs at 17:30 UTC (01:30 CST next day), missing the post-market window entirely. The scan runs at the wrong time, fetching stale data or conflicting with the next trading day.
**Why it happens:** arq cron uses UTC by default. There is no timezone parameter. Developers in CST naturally think "17:30" without converting.
**How to avoid:** Convert explicitly: 17:30 CST = 09:30 UTC. Use `hour=9, minute=30` in the cron definition. Add a comment in the code documenting the conversion. Write a test that verifies the cron fires at the expected UTC time.
**Warning signs:** Scan runs showing `created_at` timestamps at 01:30 CST; scan data appearing stale because it was fetched before market close.

### Pitfall 2: API Returns Before arq Job Starts
**What goes wrong:** The manual scan trigger endpoint enqueues a job and returns `{status: "queued", run_id: "..."}`. But the run_id returned is the arq job_id, not the scan run_id. The user tries to query `GET /runs/{run_id}` with the arq job_id, gets 404, and thinks the scan failed.
**Why it happens:** arq job_id and market_scan_runs.run_id are different UUIDs. The arq job runs asynchronously; the scan run is created inside the job. The API cannot return the scan run_id because it does not exist yet when the API responds.
**How to avoid:** Return the arq `job_id` as `job_id` (not `run_id`). Document that users should poll `GET /runs?status=running` to find the newly created run. Alternatively, create the scan run in the API handler (with status `pending`), then pass the run_id to the arq job which transitions it to `running`.
**Warning signs:** Frontend showing "scan not found" after triggering manual scan; users confused about job_id vs run_id.

### Pitfall 3: Watchlist Has No User Ownership
**What goes wrong:** The existing `WatchlistDB` model uses `ticker` as the sole primary key -- there is no `user_id` column. The watchlist is global, not per-user. If the API endpoint adds a candidate to "the watchlist," it adds it for ALL users, not just the requesting user.
**Why it happens:** The original watchlist was designed for a single-user MVP (Phase 6-8). Multi-user auth was added later (Phase 13-14) but the watchlist model was never updated to be per-user.
**How to avoid:** For EXE-08, the requirement says "add a candidate stock to their existing watchlist." The current schema only supports a single global watchlist. Options: (a) add to the global watchlist (all users see it), (b) use `UserStockAccessRepository` instead of `WatchlistRepository` for per-user tracking, or (c) accept the limitation and document it. The safest approach is to add the ticker to the global `WatchlistDB` table since that is what the existing watcher infrastructure reads from. The `already_exists` flag handles duplicates.
**Warning signs:** User A adding a stock to watchlist makes it visible in User B's watchlist; or user-specific watchlist expectations not matching the global schema.

### Pitfall 4: Candidate Sorting on JSONB Fields
**What goes wrong:** The requirement asks for sorting by `safety_margin` and `yield_gap`, but these are stored inside the `screening_snapshot` JSONB column, not as dedicated table columns. Sorting by JSONB fields requires PostgreSQL-specific syntax (`screening_snapshot->>'margin_of_safety'`) which SQLAlchemy does not generate cleanly.
**Why it happens:** Phase 25 stored all analysis results in a single JSONB column for flexibility. Only `composite_score` has a dedicated column.
**How to avoid:** For the MVP, support sorting only on `composite_score` (dedicated column). For JSONB-based sorts, use `text()` expressions with `screening_snapshot->>'key'` and cast to float. Alternatively, add a dedicated `safety_margin` column to `market_scan_candidates` in a migration, populated during candidate creation.
**Warning signs:** Sort by safety_margin returning wrong order or throwing SQL errors; slow queries due to full-table scan on JSONB extraction.

### Pitfall 5: Concurrent Cron + Manual Scan Collision
**What goes wrong:** The daily cron fires at 17:30 CST. An admin also triggers a manual scan at 17:31 CST. Two scans run simultaneously on the same index, creating duplicate candidates and consuming double the AKShare API quota (risking IP block).
**Why it happens:** arq cron `unique=True` prevents the same cron from firing twice, but it does not prevent a manual job from running concurrently with a cron job.
**How to avoid:** The `run_market_scan` job function should check for an already-running scan before starting. Use `MarketScanRunRepository` to query for status='running' scans for the same index_code. If found, log a warning and exit without error. [CITED: PITFALLS.md Pitfall 5]
**Warning signs:** Two `market_scan_runs` with status='running' for the same index_code; duplicate candidates in the same time window.

### Pitfall 6: Missing Repository Methods for Pagination
**What goes wrong:** The existing `MarketScanRunRepository` has `get_by_status()` and `get_latest_run()` but no paginated list method. The existing `MarketScanCandidateRepository` has `get_by_run_id()` but no paginated method with dynamic sorting or filtering.
**Why it happens:** Phase 25 built basic repository methods. Pagination and dynamic sorting were deferred to the API phase (Phase 28).
**How to avoid:** Add new repository methods: `list_runs_paginated(page, limit, status, scan_type)`, `list_candidates_paginated(run_id, page, limit, index_code, sort_by, sort_order)`. These are straightforward extensions of the existing query patterns.
**Warning signs:** API endpoints loading entire tables into memory before paginating; OOM errors on large candidate sets.

## Code Examples

Verified patterns from existing codebase:

### Existing arq Worker Startup/Shutdown (from pipeline/worker.py)
```python
# Source: stockvaluefinder/pipeline/worker.py lines ~530-580
async def on_startup(ctx: dict[str, Any]) -> None:
    """Initialize resources on worker startup."""
    ctx["akshare"] = AKShareClient()
    ctx["session_factory"] = async_session_maker
    logger.info("Worker started with AKShare client and session factory")

async def on_shutdown(ctx: dict[str, Any]) -> None:
    """Clean up resources on worker shutdown."""
    if "akshare" in ctx:
        await ctx["akshare"].close()
    logger.info("Worker shut down")
```

### Existing arq Pool in FastAPI (from main.py)
```python
# Source: stockvaluefinder/main.py lines 136-143
# Startup: Initialize Arq connection pool (for enqueuing from FastAPI)
arq_pool = None
try:
    arq_pool = await create_pool(get_arq_redis_settings())
    app.state.arq_pool = arq_pool
    logger.info("Arq pool initialized successfully")
except Exception as e:
    logger.warning(f"Arq pool unavailable, pipeline enqueuing disabled: {e}")
    app.state.arq_pool = None
```

### Existing Enqueue Pattern (from pipeline/worker.py)
```python
# Source: stockvaluefinder/pipeline/worker.py lines 195-210
async def _enqueue_parse(task_id: str) -> None:
    """Enqueue parse_report job for the given task."""
    from arq import create_pool as arq_create_pool

    pool = await arq_create_pool(get_arq_redis_settings())
    try:
        await pool.enqueue_job("parse_report", task_id, _job_id=f"parse:{task_id}")
    finally:
        await pool.close()
```

### Existing Admin Authorization (from admin_routes.py)
```python
# Source: stockvaluefinder/api/admin_routes.py lines 52-58
@router.get("/users", response_model=ApiResponse[UserListResponse])
async def list_users(
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[UserListResponse]:
```

### Existing Pagination Response Pattern (from admin_routes.py)
```python
# Source: stockvaluefinder/api/admin_routes.py lines 76-86
return ApiResponse(
    success=True,
    data=UserListResponse(
        users=user_responses,
        pagination=PaginationMeta(
            total=total,
            page=page,
            limit=limit,
        ),
    ),
)
```

### Existing Watchlist Duplicate Handling
```python
# Source: stockvaluefinder/pipeline/watchlist_repo.py
# get_by_ticker() returns None if not in watchlist
# add() creates new entry; PK constraint on ticker prevents duplicates
async def get_by_ticker(self, ticker: str) -> WatchlistDB | None:
    stmt = select(WatchlistDB).where(WatchlistDB.ticker == ticker)
    result = await self._session.execute(stmt)
    return result.scalar_one_or_none()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Scan runs only via manual API call | arq cron for scheduled + API for manual | Phase 28 | Hands-off daily operation |
| No scan result visibility | REST API with pagination and filtering | Phase 28 | Users can browse and compare scan results |
| Watchlist is manual entry only | Candidate-to-watchlist one-click add | Phase 28 | Reduces friction for acting on scan results |
| Single global watchlist | Per-user stock access (UserStockAccess) | Phase 13-14 | Existing per-user system can be leveraged |

**Deprecated/outdated:**
- Running scans synchronously from API (replaced by async arq job enqueue)
- Hardcoded scan schedules in config (replaced by configurable arq cron)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | arq `cron()` uses UTC timezone with no CST override; 17:30 CST = 09:30 UTC | Worker Cron | If arq supports timezone, the conversion is wrong |
| A2 | The existing `WatchlistDB` global watchlist is acceptable for EXE-08; per-user watchlist would require schema changes | Watchlist Integration | If per-user watchlist is required, Phase 28 needs a migration |
| A3 | The `app.state.arq_pool` in main.py is accessible from route handlers via `Request.app.state` | Manual Scan Trigger | If the pool is not reliably available, manual triggers fail |
| A4 | The existing `ScanOrchestrator.run_scan()` can be called from an arq worker context with a fresh database session | Worker Integration | If the orchestrator has context-specific dependencies, worker calls may fail |
| A5 | Weekly deep scan (EXE-02) extends the daily scan with additional services (Alpha, financial refresh). The `ScanOrchestrator` currently only supports DAILY/WEEKLY via `ScanType` enum, but the weekly-specific logic (Alpha scores, financial refresh) may need to be added | Weekly Deep Scan | If weekly logic differs significantly from daily, the orchestrator needs extension |

## Open Questions

1. **Watchlist model ownership**
   - What we know: `WatchlistDB` has no `user_id` column; it is a global watchlist. `UserStockAccessDB` has per-user access but is for authorization, not watchlisting.
   - What's unclear: Whether EXE-08 "add to their existing watchlist" means the global watchlist or requires a per-user watchlist model.
   - Recommendation: For MVP, add to the global `WatchlistDB` table. The `already_exists` flag naturally handles duplicates. Document the global scope limitation.

2. **Weekly deep scan additional logic**
   - What we know: EXE-02 says weekly scans should "refresh financial reports, run full risk analysis, compute Alpha scores, and recalculate composite rankings." The current `ScanOrchestrator` does not differentiate daily vs weekly logic internally -- it just uses different `top_n` values.
   - What's unclear: Whether the weekly scan needs new code paths in the orchestrator (e.g., calling Alpha service, refreshing financials from AKShare) or if it reuses the existing pipeline with larger `top_n`.
   - Recommendation: For Phase 28, the weekly scan uses `ScanOrchestrator.run_scan()` with `ScanType.WEEKLY` and `weekly_top_n=100`. The deeper analysis (Alpha, full risk) can be handled by passing additional flags or extending the orchestrator in a minimal way. If the orchestrator already handles all cases via `ScanType`, no changes are needed.

3. **Scanner worker deployment model**
   - What we know: The existing `WorkerSettings` runs as `arq stockvaluefinder.pipeline.worker.WorkerSettings`. Adding scanner cron jobs to this class means the single arq process handles both disclosure watching and market scanning.
   - What's unclear: Whether to add scanner cron jobs to the existing `WorkerSettings` or create a separate `ScannerWorkerSettings`.
   - Recommendation: Add to the existing `WorkerSettings` for simplicity. The scanner cron jobs are infrequent (daily + weekly) and do not conflict with disclosure watching. A separate worker would require running two arq processes.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All code | Yes | 3.12.11 | -- |
| arq | Worker cron jobs | Yes | 0.25.0 | -- |
| Redis | arq job queue | Not verified | -- | Tests use mocks |
| PostgreSQL | Repositories | Not verified | -- | Tests use AsyncMock |
| FastAPI | REST endpoints | Yes | 0.133+ | -- |
| pytest | Testing | Yes | 9.0+ | -- |

**Missing dependencies with no fallback:**
- None -- all declared dependencies are installed or mocked in tests

**Missing dependencies with fallback:**
- Redis/PostgreSQL: Tests mock external connections; runtime requires both services

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0+ with pytest-asyncio |
| Config file | stockvaluefinder/pytest.ini |
| Quick run command | `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/test_worker.py tests/unit/test_market_scanner/test_scanner_routes.py -q --no-cov` |
| Full suite command | `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXE-01 | Daily cron fires at correct UTC time for post-market-close | unit | `uv run pytest tests/unit/test_market_scanner/test_worker.py::test_daily_cron_schedule -q --no-cov` | No, Wave 0 |
| EXE-01 | Daily scan calls orchestrator.run_scan with DAILY type | unit | `uv run pytest tests/unit/test_market_scanner/test_worker.py::test_daily_scan_orchestrator -q --no-cov` | No, Wave 0 |
| EXE-01 | Daily scan skips if already-running scan exists | unit | `uv run pytest tests/unit/test_market_scanner/test_worker.py::test_daily_skip_concurrent -q --no-cov` | No, Wave 0 |
| EXE-02 | Weekly cron fires on correct weekday | unit | `uv run pytest tests/unit/test_market_scanner/test_worker.py::test_weekly_cron_schedule -q --no-cov` | No, Wave 0 |
| EXE-02 | Weekly scan uses WEEKLY type and weekly_top_n | unit | `uv run pytest tests/unit/test_market_scanner/test_worker.py::test_weekly_scan_params -q --no-cov` | No, Wave 0 |
| EXE-03 | Manual trigger enqueues arq job and returns job_id | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_trigger_manual_scan -q --no-cov` | No, Wave 0 |
| EXE-03 | Manual trigger requires admin role | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_trigger_requires_admin -q --no-cov` | No, Wave 0 |
| EXE-03 | Manual trigger validates request params | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_trigger_validates_params -q --no-cov` | No, Wave 0 |
| EXE-05 | List runs with pagination and status filter | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_list_runs_paginated -q --no-cov` | No, Wave 0 |
| EXE-05 | Get latest run for an index code | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_get_latest_run -q --no-cov` | No, Wave 0 |
| EXE-06 | List candidates with pagination and sort | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_list_candidates_sorted -q --no-cov` | No, Wave 0 |
| EXE-06 | Filter candidates by index code | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_candidates_filter_index -q --no-cov` | No, Wave 0 |
| EXE-07 | Get candidate detail with full snapshot | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_candidate_detail -q --no-cov` | No, Wave 0 |
| EXE-08 | Add candidate to watchlist | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_add_to_watchlist -q --no-cov` | No, Wave 0 |
| EXE-08 | Duplicate add returns already_exists flag | unit | `uv run pytest tests/unit/test_market_scanner/test_scanner_routes.py::test_watchlist_duplicate -q --no-cov` | No, Wave 0 |

### Sampling Rate
- **Per task commit:** `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/test_worker.py -q --no-cov` (or relevant test file)
- **Per wave merge:** `cd stockvaluefinder && uv run pytest tests/unit/test_market_scanner/ -v`
- **Phase gate:** Full market scanner test suite green before phase complete

### Wave 0 Gaps
- [ ] `tests/unit/test_market_scanner/test_worker.py` -- covers EXE-01, EXE-02
- [ ] `tests/unit/test_market_scanner/test_scanner_routes.py` -- covers EXE-03, EXE-05, EXE-06, EXE-07, EXE-08

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | `get_current_user` dependency (JWT validation, DB lookup, active check) |
| V3 Session Management | No | Stateless JWT, no sessions |
| V4 Access Control | Yes | `require_admin` for scan trigger; `get_current_user` for read endpoints |
| V5 Input Validation | Yes | Pydantic models for ManualScanRequest, pagination params |
| V6 Cryptography | No | No crypto operations in this phase |

### Known Threat Patterns for Worker & API Integration

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized scan trigger (EXE-03) | Elevation of Privilege | `require_admin` dependency enforces admin role check |
| AKShare DDoS via rapid manual scans | Denial of Service | Rate limiting on scan trigger endpoint; arq `unique=True` prevents concurrent cron |
| Error message leaking AKShare URLs | Information Disclosure | Sanitize errors in API responses; log full errors server-side only |
| Scraping candidate data via unthrottled API | Information Disclosure | Per-user rate limiting via existing middleware; pagination limits (max 100) |
| Watchlist injection via candidate_id tampering | Tampering | UUID validation via Pydantic; candidate existence check before add |

## Sources

### Primary (HIGH confidence)
- Codebase: `stockvaluefinder/pipeline/worker.py` -- WorkerSettings, cron patterns, on_startup/on_shutdown, enqueue patterns
- Codebase: `stockvaluefinder/main.py` -- FastAPI lifespan, arq_pool initialization, router registration
- Codebase: `stockvaluefinder/api/dependencies.py` -- get_current_user, require_admin, rate_limit patterns
- Codebase: `stockvaluefinder/api/admin_routes.py` -- admin-only endpoint patterns, pagination with PaginationMeta
- Codebase: `stockvaluefinder/api/auth_routes.py` -- auth flow patterns
- Codebase: `stockvaluefinder/pipeline/watchlist_repo.py` -- WatchlistRepository.add(), get_by_ticker()
- Codebase: `stockvaluefinder/db/models/watchlist.py` -- WatchlistDB schema (global, ticker PK, no user_id)
- Codebase: `stockvaluefinder/market_scanner/scan_orchestrator.py` -- ScanOrchestrator.run_scan() interface
- Codebase: `stockvaluefinder/repositories/market_scan_repo.py` -- Run and Candidate repository methods
- Codebase: `stockvaluefinder/models/api.py` -- ApiResponse[T], PaginationMeta
- Codebase: `stockvaluefinder/config.py` -- get_arq_redis_settings(), get_redis_url()
- Codebase: `.planning/REQUIREMENTS.md` -- EXE-01 through EXE-08 definitions
- Codebase: `.planning/research/PITFALLS.md` -- Phase 4 specific pitfalls

### Secondary (MEDIUM confidence)
- Codebase: `stockvaluefinder/models/market_scanner.py` -- Pydantic models for scan runs/candidates
- Codebase: `stockvaluefinder/market_scanner/config.py` -- MarketScannerConfig with index_codes, top_n values
- Codebase: `stockvaluefinder/models/enums.py` -- ScanStatus, ScanType enums
- Phase summaries: 25-01, 25-02, 26-01, 26-02, 26-03, 27-01, 27-02, 27-03

### Tertiary (LOW confidence)
- A1: arq cron uses UTC without timezone override -- verified by reading arq source signature but not tested with live cron execution [ASSUMED]
- A5: Weekly deep scan may need orchestrator extension -- based on requirement reading, not verified against orchestrator implementation [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all infrastructure already exists in codebase (arq worker, FastAPI routes, auth middleware, watchlist)
- Architecture: HIGH -- follows established patterns from Phase 6-8 (worker) and Phase 13-14 (auth/admin API)
- Pitfalls: HIGH -- PITFALLS.md provides verified Phase 4 warnings; additional pitfalls derived from codebase inspection

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable patterns, no external dependency changes expected)
