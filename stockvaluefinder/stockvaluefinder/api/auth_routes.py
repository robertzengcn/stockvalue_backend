"""Authentication API endpoints."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.base import get_db
from stockvaluefinder.db.models.user import UserDB
from stockvaluefinder.models.api import ApiResponse
from stockvaluefinder.models.user import TokenResponse, UserCreate
from stockvaluefinder.repositories.user_repo import UserRepository
from stockvaluefinder.services.jwt_service import jwt_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Request model for login."""

    email: str = Field(
        ...,
        description="User email address",
    )
    password: str = Field(
        ...,
        description="User password",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"email": "user@example.com", "password": "securepassword123"},
            ]
        }


class RefreshRequest(BaseModel):
    """Request model for token refresh."""

    refresh_token: str = Field(
        ...,
        description="JWT refresh token",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"refresh_token": "eyJ..."},
            ]
        }


@router.post("/register", response_model=ApiResponse[TokenResponse])
async def register(
    request: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    """Register a new user.

    Creates a new user account. First registered user automatically becomes admin (ADMN-07).
    All subsequent users get the default 'user' role (RBAC-02).
    Email must be unique (AUTH-06). Password minimum 8 characters (AUTH-07).
    """
    try:
        user_repo = UserRepository(db)

        # Check if email already exists (AUTH-06)
        existing = await user_repo.get_by_email(request.email)
        if existing is not None:
            return ApiResponse(
                success=False,
                error="Email already registered",
            )

        # Determine role: first user becomes admin (ADMN-07), others get user role (RBAC-02)
        user_count = await user_repo.count_users()
        role = "admin" if user_count == 0 else "user"

        # Hash password with bcrypt (AUTH-05)
        password_hash = jwt_service.hash_password(request.password)

        # Create user record
        user = UserDB(
            id=uuid4(),
            email=request.email,
            password_hash=password_hash,
            role=role,
            is_active=True,
        )
        user = await user_repo.create(user)
        await db.commit()

        # Generate tokens (AUTH-02)
        user_id_str = str(user.id)
        access_token = jwt_service.create_access_token(user_id_str, role)
        refresh_token = jwt_service.create_refresh_token(user_id_str, role)

        logger.info(f"User registered: {user.email} with role {role}")

        return ApiResponse(
            success=True,
            data=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
            ),
        )

    except Exception:
        logger.exception(f"Registration failed for {request.email}")
        await db.rollback()
        return ApiResponse(
            success=False,
            error="Registration failed. Please try again.",
        )


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    """Authenticate user and return JWT tokens.

    Returns access + refresh tokens on success (AUTH-02).
    Returns 403 if user account is disabled (ADMN-06).
    """
    try:
        user_repo = UserRepository(db)

        user = await user_repo.get_by_email(request.email)
        if user is None:
            return ApiResponse(
                success=False,
                error="Invalid email or password",
            )

        # Check if user is active (ADMN-06)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        # Verify password (AUTH-05)
        if not jwt_service.verify_password(request.password, user.password_hash):
            return ApiResponse(
                success=False,
                error="Invalid email or password",
            )

        # Generate tokens
        user_id_str = str(user.id)
        access_token = jwt_service.create_access_token(user_id_str, user.role)
        refresh_token = jwt_service.create_refresh_token(user_id_str, user.role)

        logger.info(f"User logged in: {user.email}")

        return ApiResponse(
            success=True,
            data=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
            ),
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Login failed for {request.email}")
        return ApiResponse(
            success=False,
            error="Login failed. Please try again.",
        )


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    """Refresh access token using a valid refresh token (AUTH-03).

    Validates the refresh token, looks up the user in the database to verify
    they are still active and to get the current role (ADMN-06). Disabled or
    deleted users cannot refresh tokens.
    """
    import jwt as pyjwt

    try:
        payload = jwt_service.validate_refresh_token(request.refresh_token)
    except pyjwt.ExpiredSignatureError:
        return ApiResponse(
            success=False,
            error="Refresh token has expired. Please login again.",
        )
    except pyjwt.InvalidTokenError:
        return ApiResponse(
            success=False,
            error="Invalid refresh token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        return ApiResponse(
            success=False,
            error="Invalid refresh token payload",
        )

    # Look up user in DB to verify active status and get current role
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None or not user.is_active:
        return ApiResponse(
            success=False,
            error="User account is disabled or not found.",
        )

    # Issue new token pair with current role from DB (not from stale token)
    access_token = jwt_service.create_access_token(user_id, user.role)
    new_refresh_token = jwt_service.create_refresh_token(user_id, user.role)

    return ApiResponse(
        success=True,
        data=TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
        ),
    )


@router.post("/logout", response_model=ApiResponse[None])
async def logout() -> ApiResponse[None]:
    """Logout user by instructing client to discard tokens (AUTH-04).

    JWT is stateless, so logout is client-side token discard.
    The client should delete both access and refresh tokens.
    """
    return ApiResponse(
        success=True,
        data=None,
    )
