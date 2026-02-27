"""Common API response models."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataType = TypeVar("DataType")


class ApiResponse(BaseModel, Generic[DataType]):
    """Standard API response envelope."""

    success: bool = Field(..., description="Request success status")
    data: DataType | None = Field(None, description="Response data payload")
    error: str | None = Field(None, description="Error message if success=false")
    meta: dict[str, object] | None = Field(
        None, description="Metadata for pagination, etc."
    )

    model_config = {"frozen": True}


class ApiError(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, object] | None = Field(
        None, description="Additional error context"
    )

    model_config = {"frozen": True}


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, le=100, description="Items per page")

    model_config = {"frozen": True}
