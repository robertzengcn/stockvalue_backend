"""Pipeline API routes.

Provides health-check endpoint for verifying pipeline subsystem
connectivity (Redis, PostgreSQL, worker queue), and watchlist
CRUD endpoints for user-configured stock monitoring.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.base import async_session_maker, get_db
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.pipeline.models import WatchlistItemCreate, WatchlistItemResponse
from stockvaluefinder.pipeline.watchlist_repo import WatchlistRepository

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
