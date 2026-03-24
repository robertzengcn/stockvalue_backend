"""FastAPI dependencies for dependency injection."""

import os
from functools import lru_cache

from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService


async def get_cache():
    """Dependency to get cache client (TODO: implement Redis cache).

    Yields:
        Cache client instance
    """
    # TODO: Implement Redis cache client
    yield None


@lru_cache
def get_data_service() -> ExternalDataService:
    """Get or create singleton ExternalDataService instance.

    Returns:
        ExternalDataService instance initialized with Tushare token from environment
    """
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token:
        raise ValueError(
            "TUSHARE_TOKEN environment variable not set. "
            "Please set it in your .env file."
        )

    enable_akshare = os.getenv("ENABLE_AKSHARE", "true").lower() == "true"

    return ExternalDataService(
        tushare_token=tushare_token,
        enable_akshare=enable_akshare,
    )


async def get_initialized_data_service() -> ExternalDataService:
    """Get initialized ExternalDataService instance for dependency injection.

    This dependency ensures the service is initialized before use and properly
    shut down after the request completes.

    Yields:
        Initialized ExternalDataService instance
    """
    service = get_data_service()

    # Initialize on first use
    if service._tushare is None:
        await service.initialize()

    try:
        yield service
    finally:
        # Note: Don't shutdown here as it's a singleton
        # Shutdown should happen during application shutdown
        pass


__all__ = ["get_db", "get_cache", "get_data_service", "get_initialized_data_service"]
