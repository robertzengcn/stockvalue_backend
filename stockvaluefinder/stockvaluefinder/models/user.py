"""User domain models (Pydantic)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from stockvaluefinder.models.enums import UserRole


class UserCreate(BaseModel):
    """Model for user registration request."""

    email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="User email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        description="User password (minimum 8 characters)",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {"email": "user@example.com", "password": "securepassword123"},
            ]
        }


class UserResponse(BaseModel):
    """Model for user data returned in API responses (no password)."""

    model_config = {"frozen": True}

    id: UUID = Field(..., description="User unique identifier")
    email: str = Field(..., description="User email address")
    role: UserRole = Field(..., description="User role (admin/user)")
    is_active: bool = Field(..., description="Whether user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class TokenResponse(BaseModel):
    """Model for JWT token response."""

    model_config = {"frozen": True}

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class UserInDB(BaseModel):
    """Full user model as stored in database (includes password_hash)."""

    model_config = {"frozen": True}

    id: UUID
    email: str
    password_hash: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
