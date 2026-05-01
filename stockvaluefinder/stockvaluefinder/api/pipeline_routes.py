"""Pipeline API routes.

Provides health-check endpoint for verifying pipeline subsystem
connectivity (Redis, PostgreSQL, worker queue).
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sqlalchemy import text

from stockvaluefinder.db.base import async_session_maker
from stockvaluefinder.models.api import ApiResponse

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
