"""Custom error classes for StockValueFinder."""

from typing import Any


class StockValueFinderError(Exception):
    """Base exception for all StockValueFinder errors."""

    message: str
    details: dict[str, Any]

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DataValidationError(StockValueFinderError):
    """Raised when input data validation fails."""

    def __init__(
        self, message: str, field: str | None = None, value: Any = None
    ) -> None:
        details: dict[str, Any] = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, details)


class CalculationError(StockValueFinderError):
    """Raised when a financial calculation fails."""

    def __init__(
        self,
        message: str,
        calculation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if calculation:
            details["calculation"] = calculation
        if context:
            details["context"] = context
        super().__init__(message, details)


class ExternalAPIError(StockValueFinderError):
    """Raised when external API calls fail."""

    def __init__(
        self, message: str, service: str | None = None, status_code: int | None = None
    ) -> None:
        details: dict[str, Any] = {}
        if service:
            details["service"] = service
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details)


class CacheError(StockValueFinderError):
    """Raised when cache operations fail."""

    def __init__(self, message: str, operation: str | None = None) -> None:
        details: dict[str, Any] = {}
        if operation:
            details["operation"] = operation
        super().__init__(message, details)
