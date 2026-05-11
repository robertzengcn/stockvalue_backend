"""Pydantic schemas for API usage tracking data."""

from pydantic import BaseModel, Field


class EndpointUsage(BaseModel):
    """Usage statistics for a single API endpoint.

    Attributes:
        endpoint: API endpoint path (e.g., /api/v1/analyze/risk)
        call_count: Total number of calls to this endpoint
        error_count: Number of calls resulting in errors (status >= 400)
    """

    endpoint: str = Field(..., description="API endpoint path")
    call_count: int = Field(..., ge=0, description="Total calls to this endpoint")
    error_count: int = Field(0, ge=0, description="Number of error responses")


class UsageSummary(BaseModel):
    """Aggregate usage summary for a single user.

    Attributes:
        user_id: User identifier
        total_calls: Total API calls across all endpoints
        total_errors: Total error responses across all endpoints
        last_active: ISO-format timestamp of last API activity
        endpoints: Per-endpoint usage breakdown
    """

    user_id: str = Field(..., description="User identifier")
    total_calls: int = Field(0, ge=0, description="Total API calls")
    total_errors: int = Field(0, ge=0, description="Total error responses")
    last_active: str | None = Field(None, description="Last activity timestamp")
    endpoints: list[EndpointUsage] = Field(
        default_factory=list, description="Per-endpoint usage breakdown"
    )
