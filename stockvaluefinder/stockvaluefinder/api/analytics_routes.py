"""Admin analytics API endpoints for usage visibility."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import require_admin
from stockvaluefinder.db.base import get_db
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.usage import EndpointUsage, UsageSummary
from stockvaluefinder.repositories.usage_repo import ApiUsageRepository
from stockvaluefinder.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/analytics", tags=["analytics"])


@router.get("/users/{user_id}", response_model=ApiResponse[UsageSummary])
async def get_user_usage_summary(
    user_id: UUID,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[UsageSummary]:
    """Get usage summary for a specific user (ANLY-03). Admin-only.

    Reads hot data from Redis via UsageTracker, returns structured summary
    with per-endpoint call counts and last active timestamp.
    """
    from stockvaluefinder.api.dependencies import _usage_tracker

    # Verify user exists
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    uid = str(user_id)

    # Get usage data from Redis
    usage_data: dict[str, str] = {}
    last_active: str | None = None

    if _usage_tracker is not None:
        usage_data = await _usage_tracker.get_user_usage(uid)
        last_active = await _usage_tracker.get_last_active(uid)

    # Parse Redis hash data into structured fields
    total_calls = int(usage_data.get("total_calls", "0"))
    total_errors = int(usage_data.get("total_errors", "0"))
    endpoints = [
        EndpointUsage(
            endpoint=key[len("calls:") :],
            call_count=int(value),
        )
        for key, value in usage_data.items()
        if key.startswith("calls:")
    ]

    return ApiResponse(
        success=True,
        data=UsageSummary(
            user_id=uid,
            total_calls=total_calls,
            total_errors=total_errors,
            last_active=last_active,
            endpoints=endpoints,
        ),
    )


@router.get("/aggregate", response_model=ApiResponse[dict])
async def get_aggregate_stats(
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    """Get aggregate usage statistics (ANLY-04). Admin-only.

    Returns total calls, total errors, top users by usage, and error rates.
    Queries PostgreSQL for historical data.
    """
    repo = ApiUsageRepository(db)
    stats = await repo.get_aggregate_stats(limit=10)

    return ApiResponse(
        success=True,
        data=stats,
    )
