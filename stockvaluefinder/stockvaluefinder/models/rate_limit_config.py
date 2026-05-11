"""Pydantic schemas for rate limit override requests and responses."""

from pydantic import BaseModel, Field


class RateLimitOverrideRequest(BaseModel):
    """Request body for setting a per-user rate limit override.

    Attributes:
        limit: Maximum requests per window (must be positive)
        window_seconds: Window duration in seconds (must be positive)
    """

    limit: int = Field(..., gt=0, description="Maximum requests per window")
    window_seconds: int = Field(..., gt=0, description="Window duration in seconds")

    model_config = {
        "json_schema_extra": {"examples": [{"limit": 200, "window_seconds": 7200}]}
    }


class RateLimitOverrideResponse(BaseModel):
    """Response body for a rate limit override.

    Attributes:
        user_id: User identifier the override applies to
        limit: Maximum requests per window
        window_seconds: Window duration in seconds
    """

    user_id: str
    limit: int
    window_seconds: int
