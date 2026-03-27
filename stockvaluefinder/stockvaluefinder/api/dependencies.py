"""FastAPI dependencies for dependency injection."""

import asyncio
import os
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService

# Lock for thread-safe singleton initialization
_init_lock = asyncio.Lock()


async def get_cache() -> AsyncGenerator[Any, None]:
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
        ExternalDataService instance initialized with settings from environment
    """
    # Get Tushare token (optional, for premium data only)
    tushare_token = os.getenv("TUSHARE_TOKEN", "")

    # Enable AKShare as primary source (free, recommended)
    enable_akshare = os.getenv("ENABLE_AKSHARE", "true").lower() == "true"

    # Enable efinance as secondary source (free, recommended)
    enable_efinance = os.getenv("ENABLE_EFINANCE", "true").lower() == "true"

    # At least one data source must be enabled
    if not enable_akshare and not enable_efinance and not tushare_token:
        raise ValueError(
            "At least one data source must be enabled. "
            "Set ENABLE_AKSHARE=true, ENABLE_EFINANCE=true, or add TUSHARE_TOKEN. "
            "For development, use the default settings (AKShare and efinance enabled)."
        )

    return ExternalDataService(
        tushare_token=tushare_token,
        enable_akshare=enable_akshare,
        enable_efinance=enable_efinance,
    )


async def get_initialized_data_service() -> AsyncGenerator[ExternalDataService, None]:
    """Get initialized ExternalDataService instance for dependency injection.

    This dependency ensures the service is initialized before use and properly
    shut down after the request completes. Uses async lock for thread-safe
    initialization to prevent race conditions during concurrent requests.

    Yields:
        Initialized ExternalDataService instance
    """
    service = get_data_service()

    # Thread-safe initialization with async lock
    if not service._initialized:
        async with _init_lock:
            # Double-check pattern to avoid redundant initialization
            if not service._initialized:
                await service.initialize()

    try:
        yield service
    finally:
        # Note: Don't shutdown here as it's a singleton
        # Shutdown should happen during application shutdown
        pass


__all__ = ["get_db", "get_cache", "get_data_service", "get_initialized_data_service"]
