"""Pipeline API routes.

Provides health-check endpoint for verifying pipeline subsystem
connectivity (Redis, PostgreSQL, worker queue), watchlist CRUD
endpoints for user-configured stock monitoring, and task management
endpoints for status, listing, and manual triggering.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.base import async_session_maker, get_db
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.pipeline.config import PipelineConfig
from stockvaluefinder.pipeline.models import (
    TaskListItemResponse,
    TriggerRequest,
    WatchlistItemCreate,
    WatchlistItemResponse,
)
from stockvaluefinder.pipeline.repo import PipelineTaskRepository
from stockvaluefinder.pipeline.state import PipelineState
from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository
from stockvaluefinder.pipeline.watcher_repo import WatcherStateRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/pipeline",
    tags=["pipeline"],
)


@router.get("/health")
async def pipeline_health(request: Request) -> ApiResponse:
    """Check pipeline subsystem health.

    Tests connectivity to Redis (via arq pool PING), PostgreSQL (SELECT 1),
    and reports worker and watcher status. Returns overall status as
    "healthy" when all components are operational or not yet configured,
    "degraded" when any component reports unhealthy.

    Args:
        request: FastAPI request with app.state containing arq_pool.

    Returns:
        ApiResponse with health status data including per-component
        status and checked_at timestamp.
    """
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
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["postgresql"] = "healthy"
    except Exception:
        checks["postgresql"] = "unhealthy"

    # Worker health (indirect: Redis queue reachable)
    checks["worker"] = "healthy" if checks["redis"] == "healthy" else "unreachable"

    # Watcher (Phase 6 future)
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


# ---------------------------------------------------------------------------
# Watchlist CRUD endpoints (D-15)
# ---------------------------------------------------------------------------


@router.post("/watchlist", status_code=200, response_model=None)
async def add_to_watchlist(
    body: WatchlistItemCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[WatchlistItemResponse] | JSONResponse:
    """Add a stock to the watchlist.

    Creates a new watchlist entry for the given ticker. Returns 400 if
    the ticker is already in the active watchlist.

    Args:
        body: Request body with ticker and name.
        db: Async database session.

    Returns:
        ApiResponse containing the created watchlist item.
    """
    repo = WatchlistRepository(db)

    # Check if ticker already exists in watchlist (D-15)
    existing = await repo.get_by_ticker(body.ticker)
    if existing is not None and existing.is_active:
        return JSONResponse(
            status_code=400,
            content=ApiResponse(
                success=False,
                error="Stock already in watchlist",
            ).model_dump(),
        )

    try:
        entry = await repo.add(body.ticker, body.name)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to add stock to watchlist", extra={"ticker": body.ticker})
        return ApiResponse(
            success=False,
            error=f"Failed to add stock: {exc}",
        )

    response_data = WatchlistItemResponse(
        ticker=entry.ticker,
        name=entry.name,
        added_at=entry.added_at,
        is_active=entry.is_active,
    )
    return ApiResponse(success=True, data=response_data)


@router.get("/watchlist")
async def list_watchlist(
    active_only: bool = Query(default=True, description="Return only active stocks"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[WatchlistItemResponse]]:
    """List watchlist stocks.

    Returns all watchlist entries, optionally filtered to active stocks only.

    Args:
        active_only: If True, return only active stocks.
        db: Async database session.

    Returns:
        ApiResponse containing a list of watchlist items.
    """
    repo = WatchlistRepository(db)

    try:
        entries = await repo.get_all(active_only=active_only)
    except Exception as exc:
        logger.error("Failed to list watchlist")
        return ApiResponse(
            success=False,
            error=f"Failed to list watchlist: {exc}",
        )

    items = [
        WatchlistItemResponse(
            ticker=entry.ticker,
            name=entry.name,
            added_at=entry.added_at,
            is_active=entry.is_active,
        )
        for entry in entries
    ]
    return ApiResponse(success=True, data=items)


@router.delete("/watchlist/{ticker}", response_model=None)
async def remove_from_watchlist(
    ticker: str = Path(
        ...,
        pattern=r"^\d{4,6}\.(SH|SZ|HK)$",
        description="Stock ticker to remove",
    ),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None] | JSONResponse:
    """Remove a stock from the watchlist.

    Soft-removes the stock by setting is_active=False. Returns 404-style
    error if the ticker is not found in the watchlist.

    Args:
        ticker: Stock ticker to remove (path parameter).
        db: Async database session.

    Returns:
        ApiResponse with success status and meta containing removed ticker.
    """
    repo = WatchlistRepository(db)

    try:
        removed = await repo.remove(ticker)
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to remove stock from watchlist", extra={"ticker": ticker})
        return ApiResponse(
            success=False,
            error=f"Failed to remove stock: {exc}",
        )

    if removed is None:
        return JSONResponse(
            status_code=404,
            content=ApiResponse(
                success=False,
                error=f"Stock {ticker} not found in watchlist",
            ).model_dump(),
        )

    await db.commit()
    return ApiResponse(
        success=True,
        data=None,
        meta={"removed_ticker": ticker},
    )


# ---------------------------------------------------------------------------
# Pipeline status, tasks listing, and trigger endpoints (D-03, D-04, D-05, D-08)
# ---------------------------------------------------------------------------


def _compute_next_poll_time(
    last_poll_time: datetime | None,
    config: PipelineConfig,
) -> str | None:
    """Compute the next scheduled poll time from cron config (per D-08).

    Selects high_season_cron or off_season_cron based on the current month,
    then uses croniter to compute the next occurrence after last_poll_time.

    Args:
        last_poll_time: The timestamp of the last poll, or None if never polled.
        config: Pipeline config with cron schedule definitions.

    Returns:
        ISO format string of the next scheduled poll time, or None if never polled.
    """
    if last_poll_time is None:
        return None

    from croniter import croniter

    now = datetime.now(timezone.utc)
    current_month = now.month
    cron_expr = (
        config.high_season_cron
        if current_month in config.high_season_months
        else config.off_season_cron
    )
    # Use a timezone-aware base for croniter; if last_poll_time is naive, assume UTC
    base = last_poll_time
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    next_time = croniter(cron_expr, base).get_next(datetime)
    return next_time.isoformat()


@router.get("/status")
async def pipeline_status(
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Get pipeline status with aggregate counts per state (per D-08).

    Returns counts for all 6 pipeline states, last watcher poll time,
    next scheduled poll time computed from cron config, and total task count.

    Args:
        db: Async database session.

    Returns:
        ApiResponse with pipeline status data.
    """
    config = PipelineConfig()
    repo = PipelineTaskRepository(db)
    counts = await repo.count_by_state()

    watcher_repo = WatcherStateRepository(db)
    watcher_state = await watcher_repo.get_state()
    last_poll = watcher_state.last_poll_time

    next_poll = _compute_next_poll_time(last_poll, config)
    total = sum(counts.values())

    return ApiResponse(
        success=True,
        data={
            "counts": counts,
            "last_poll_time": last_poll.isoformat() if last_poll else None,
            "next_poll_time": next_poll,
            "total_tasks": total,
        },
    )


@router.get("/tasks")
async def list_tasks_endpoint(
    state: str | None = Query(None, description="Filter by state"),
    ticker: str | None = Query(None, description="Filter by ticker"),
    created_after: datetime | None = Query(
        None, description="Filter tasks created after"
    ),
    created_before: datetime | None = Query(
        None, description="Filter tasks created before"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List pipeline tasks with filtering and pagination (per TASK-02).

    Returns tasks ordered by created_at descending with optional filters
    for state, ticker, and date range.

    Args:
        state: Filter by pipeline state.
        ticker: Filter by stock ticker.
        created_after: Include tasks created at or after this datetime.
        created_before: Include tasks created at or before this datetime.
        page: Page number (1-based).
        limit: Items per page (max 100).
        db: Async database session.

    Returns:
        ApiResponse with task list and pagination metadata.
    """
    offset = (page - 1) * limit
    repo = PipelineTaskRepository(db)
    tasks, total = await repo.list_tasks(
        state=state,
        ticker=ticker,
        created_after=created_after,
        created_before=created_before,
        offset=offset,
        limit=limit,
    )
    items = [
        TaskListItemResponse(
            task_id=str(t.task_id),
            ticker=t.ticker,
            business_key=t.business_key,
            state=t.state,
            current_stage=t.current_stage,
            error_message=t.error_message,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tasks
    ]
    return ApiResponse(
        success=True,
        data=items,
        meta={"total": total, "page": page, "limit": limit},
    )


@router.post("/trigger", status_code=200, response_model=None)
async def trigger_pipeline(
    body: TriggerRequest,
    force: bool = Query(default=False),
    request: Request = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
) -> ApiResponse | JSONResponse:
    """Manually trigger pipeline processing for a ticker (per D-03, D-04, D-05).

    Creates a new pipeline task and enqueues download_report via arq.
    Auto-adds the ticker to the watchlist if not present. Deduplicates
    DONE tasks unless force=true.

    Args:
        body: Request body with ticker and optional fiscal_year/report_type.
        force: If true, bypass dedup for already-completed tasks.
        request: FastAPI request with app.state containing arq_pool.
        db: Async database session.

    Returns:
        ApiResponse with the created task_id, or error if dedup blocks.
    """
    ticker = body.ticker
    fiscal_year = body.fiscal_year or datetime.now().year
    report_type = body.report_type or "annual"
    business_key = f"{ticker}:{fiscal_year}:{report_type}"

    # D-05: Auto-add to watchlist if not present
    watchlist_repo = WatchlistRepository(db)
    existing = await watchlist_repo.get_by_ticker(ticker)
    if existing is None:
        await watchlist_repo.add(ticker, ticker)

    # D-04: Dedup check (skip if force=true)
    task_repo = PipelineTaskRepository(db)
    if not force:
        existing_task = await task_repo.get_by_business_key(business_key)
        if existing_task is not None and existing_task.state == PipelineState.DONE:
            return JSONResponse(
                status_code=200,
                content=ApiResponse(
                    success=False,
                    error=(
                        f"Task already completed for {business_key}. "
                        "Use force=true to reprocess."
                    ),
                ).model_dump(),
            )

    # Create task and enqueue download_report (D-05)
    task = await task_repo.create_task(ticker, business_key)
    await db.commit()

    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is not None:
        await arq_pool.enqueue_job("download_report", str(task.task_id))
    else:
        logger.warning(
            "arq_pool not available, task created but not enqueued",
            extra={"task_id": str(task.task_id)},
        )

    return ApiResponse(success=True, data={"task_id": str(task.task_id)})
