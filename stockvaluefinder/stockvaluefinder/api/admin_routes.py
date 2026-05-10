"""Admin user management API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.api.dependencies import require_admin
from stockvaluefinder.db.base import get_db
from stockvaluefinder.models.api import ApiResponse, PaginationMeta
from stockvaluefinder.models.user import (
    UserDetailResponse,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
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
