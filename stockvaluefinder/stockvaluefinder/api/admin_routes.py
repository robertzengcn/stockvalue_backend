"""Admin user management API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import get_rate_limiter, require_admin
from stockvaluefinder.db.base import get_db
from stockvaluefinder.models.api import ApiResponse, PaginationMeta
from stockvaluefinder.models.rate_limit_config import (
    RateLimitOverrideRequest,
    RateLimitOverrideResponse,
)
from stockvaluefinder.models.user import (
    UserDetailResponse,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
)
from stockvaluefinder.models.user_stock_access import (
    StockAccessAddRequest,
    StockAccessListResponse,
    StockAccessRemoveRequest,
    StockAccessUpdateRequest,
)
from stockvaluefinder.repositories.user_stock_access_repo import (
    UserStockAccessRepository,
)
from stockvaluefinder.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class UserStatusUpdate(BaseModel):
    """Request model for enabling/disabling user."""

    is_active: bool = Field(..., description="New active status")

    class Config:
        json_schema_extra = {
            "examples": [
                {"is_active": True},
                {"is_active": False},
            ]
        }


@router.get("/users", response_model=ApiResponse[UserListResponse])
async def list_users(
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[UserListResponse]:
    """List all users with pagination (ADMN-01). Admin-only."""
    try:
        user_repo = UserRepository(db)
        users, total = await user_repo.list_users(page=page, limit=limit)

        user_responses = [
            UserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]

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
    except Exception:
        logger.exception("Failed to list users")
        return ApiResponse(success=False, error="Failed to list users")


@router.get("/users/{user_id}", response_model=ApiResponse[UserDetailResponse])
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[UserDetailResponse]:
    """View single user details (ADMN-02). Admin-only."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return ApiResponse(
        success=True,
        data=UserDetailResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            deleted_at=user.deleted_at,
        ),
    )


@router.patch("/users/{user_id}/status", response_model=ApiResponse[UserResponse])
async def update_user_status(
    user_id: UUID,
    request: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[UserResponse]:
    """Enable or disable user account (ADMN-03). Admin-only."""
    user_repo = UserRepository(db)
    user = await user_repo.set_active(user_id, request.is_active)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await db.commit()

    logger.info(
        f"Admin {admin.get('email')} {'enabled' if request.is_active else 'disabled'} user {user.email}"
    )

    return ApiResponse(
        success=True,
        data=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@router.patch("/users/{user_id}/role", response_model=ApiResponse[UserResponse])
async def update_user_role(
    user_id: UUID,
    request: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[UserResponse]:
    """Change user role between admin and user (ADMN-05, RBAC-03). Admin-only."""
    # Prevent admin from demoting themselves
    if str(user_id) == admin.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    user_repo = UserRepository(db)
    user = await user_repo.update_role(user_id, request.role.value)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await db.commit()

    logger.info(
        f"Admin {admin.get('email')} changed user {user.email} role to {user.role}"
    )

    return ApiResponse(
        success=True,
        data=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@router.delete("/users/{user_id}", response_model=ApiResponse[UserResponse])
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[UserResponse]:
    """Soft-delete user account (ADMN-04). Admin-only."""
    # Prevent admin from deleting themselves
    if str(user_id) == admin.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    user_repo = UserRepository(db)

    # Get user info before soft delete for response
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Store response data before deletion
    response_data = UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    deleted_user = await user_repo.soft_delete(user_id)
    if deleted_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or already deleted",
        )
    await db.commit()

    logger.info(f"Admin {admin.get('email')} soft-deleted user {response_data.email}")

    return ApiResponse(success=True, data=response_data)


@router.get(
    "/users/{user_id}/stock-access",
    response_model=ApiResponse[StockAccessListResponse],
)
async def get_user_stock_access(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[StockAccessListResponse]:
    """Get all stock tickers a user has access to (ACCL-02). Admin-only."""
    from stockvaluefinder.models.user_stock_access import StockAccessEntry

    repo = UserStockAccessRepository(db)
    entries = await repo.get_all_for_user(str(user_id))

    access_entries = [
        StockAccessEntry(ticker=e.ticker, created_at=e.created_at) for e in entries
    ]

    return ApiResponse(
        success=True,
        data=StockAccessListResponse(user_id=user_id, tickers=access_entries),
    )


@router.post(
    "/users/{user_id}/stock-access",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[StockAccessListResponse],
)
async def add_user_stock_access(
    user_id: UUID,
    request: StockAccessAddRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[StockAccessListResponse]:
    """Add a stock ticker to user's access list (ACCL-02). Admin-only."""
    from stockvaluefinder.models.user_stock_access import StockAccessEntry

    repo = UserStockAccessRepository(db)
    user_repo = UserRepository(db)

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await repo.add_access(str(user_id), request.ticker)
    await db.commit()

    entries = await repo.get_all_for_user(str(user_id))
    access_entries = [
        StockAccessEntry(ticker=e.ticker, created_at=e.created_at) for e in entries
    ]

    logger.info(
        f"Admin {admin.get('email')} added {request.ticker} "
        f"to user {user.email} access list"
    )

    return ApiResponse(
        success=True,
        data=StockAccessListResponse(user_id=user_id, tickers=access_entries),
    )


@router.delete(
    "/users/{user_id}/stock-access",
    response_model=ApiResponse[StockAccessListResponse],
)
async def remove_user_stock_access(
    user_id: UUID,
    request: StockAccessRemoveRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[StockAccessListResponse]:
    """Remove a stock ticker from user's access list (ACCL-02). Admin-only."""
    from stockvaluefinder.models.user_stock_access import StockAccessEntry

    repo = UserStockAccessRepository(db)

    removed = await repo.remove_access(str(user_id), request.ticker)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker {request.ticker} not found in user's access list",
        )
    await db.commit()

    entries = await repo.get_all_for_user(str(user_id))
    access_entries = [
        StockAccessEntry(ticker=e.ticker, created_at=e.created_at) for e in entries
    ]

    logger.info(
        f"Admin {admin.get('email')} removed {request.ticker} "
        f"from user {user_id} access list"
    )

    return ApiResponse(
        success=True,
        data=StockAccessListResponse(user_id=user_id, tickers=access_entries),
    )


@router.put(
    "/users/{user_id}/stock-access",
    response_model=ApiResponse[StockAccessListResponse],
)
async def set_user_stock_access(
    user_id: UUID,
    request: StockAccessUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApiResponse[StockAccessListResponse]:
    """Replace all stock tickers for a user's access list (ACCL-02). Admin-only."""
    from stockvaluefinder.models.user_stock_access import StockAccessEntry

    repo = UserStockAccessRepository(db)
    user_repo = UserRepository(db)

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await repo.set_access(str(user_id), request.tickers)
    await db.commit()

    entries = await repo.get_all_for_user(str(user_id))
    access_entries = [
        StockAccessEntry(ticker=e.ticker, created_at=e.created_at) for e in entries
    ]

    logger.info(
        f"Admin {admin.get('email')} set access list for user {user.email} "
        f"to {len(request.tickers)} tickers"
    )

    return ApiResponse(
        success=True,
        data=StockAccessListResponse(user_id=user_id, tickers=access_entries),
    )


@router.get(
    "/users/{user_id}/rate-limit",
    response_model=ApiResponse[RateLimitOverrideResponse],
)
async def get_user_rate_limit(
    user_id: UUID,
    admin: dict = Depends(require_admin),
) -> ApiResponse[RateLimitOverrideResponse]:
    """Get per-user rate limit override (RATE-04). Admin-only.

    Returns the override if set, otherwise returns the system defaults.
    """
    limiter = get_rate_limiter()
    if limiter is None:
        return ApiResponse(
            success=True,
            data=RateLimitOverrideResponse(
                user_id=str(user_id), limit=100, window_seconds=3600
            ),
        )

    override = await limiter.get_user_override(str(user_id))
    if override:
        return ApiResponse(
            success=True,
            data=RateLimitOverrideResponse(
                user_id=str(user_id),
                limit=override.limit,
                window_seconds=override.window,
            ),
        )

    return ApiResponse(
        success=True,
        data=RateLimitOverrideResponse(
            user_id=str(user_id), limit=100, window_seconds=3600
        ),
    )


@router.put(
    "/users/{user_id}/rate-limit",
    response_model=ApiResponse[RateLimitOverrideResponse],
)
async def set_user_rate_limit(
    user_id: UUID,
    request: RateLimitOverrideRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RateLimitOverrideResponse]:
    """Set per-user rate limit override (RATE-04). Admin-only.

    Writes override to Redis for fast lookup and DB for persistence.
    """
    # Verify user exists
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Set override in Redis
    limiter = get_rate_limiter()
    if limiter is not None:
        await limiter.set_user_override(
            str(user_id), request.limit, request.window_seconds
        )

    # Upsert override in DB for persistence
    from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

    from sqlalchemy import select

    stmt = select(RateLimitOverrideDB).where(
        RateLimitOverrideDB.user_id == str(user_id)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is None:
        import uuid

        db_obj = RateLimitOverrideDB(
            id=str(uuid.uuid4()),
            user_id=str(user_id),
            limit=request.limit,
            window_seconds=request.window_seconds,
        )
        db.add(db_obj)
    else:
        existing.limit = request.limit
        existing.window_seconds = request.window_seconds

    await db.commit()

    logger.info(
        f"Admin {admin.get('email')} set rate limit override for user "
        f"{user.email}: {request.limit}/{request.window_seconds}s"
    )

    return ApiResponse(
        success=True,
        data=RateLimitOverrideResponse(
            user_id=str(user_id),
            limit=request.limit,
            window_seconds=request.window_seconds,
        ),
    )


@router.delete(
    "/users/{user_id}/rate-limit",
    response_model=ApiResponse[dict],
)
async def delete_user_rate_limit(
    user_id: UUID,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    """Remove per-user rate limit override (RATE-04). Admin-only.

    Removes override from Redis and DB, reverting to system defaults.
    """
    # Remove override from Redis
    limiter = get_rate_limiter()
    if limiter is not None:
        await limiter.remove_user_override(str(user_id))

    # Delete from DB
    from sqlalchemy import delete as sql_delete

    from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

    stmt = sql_delete(RateLimitOverrideDB).where(
        RateLimitOverrideDB.user_id == str(user_id)
    )
    await db.execute(stmt)
    await db.commit()

    logger.info(
        f"Admin {admin.get('email')} removed rate limit override for user {user_id}"
    )

    return ApiResponse(
        success=True,
        data={"message": f"Rate limit override removed for user {user_id}"},
    )
