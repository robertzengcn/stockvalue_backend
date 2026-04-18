"""FastAPI dependencies for dependency injection."""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from functools import lru_cache

from stockvaluefinder.config import rag_config
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.rag.vector_store import QdrantVectorStore
from stockvaluefinder.utils.cache import CacheManager

logger = logging.getLogger(__name__)

# Lock for thread-safe singleton initialization
_init_lock = asyncio.Lock()

# Module-level cache instance, set by init_cache during lifespan
_cache_instance: CacheManager | None = None


def init_cache(redis_url: str) -> CacheManager:
    """Initialize the module-level CacheManager instance.

    Called from application lifespan during startup. Creates a CacheManager
    and stores it at module level for the get_cache dependency to yield.

    Args:
        redis_url: Redis connection URL

    Returns:
        CacheManager instance (not yet connected)
    """
    global _cache_instance
    _cache_instance = CacheManager(redis_url=redis_url)
    return _cache_instance


async def get_cache() -> AsyncGenerator[CacheManager | None, None]:
    """Dependency to get cache client.

    Yields the module-level CacheManager instance if initialized,
    or None if cache is not available (graceful degradation).

    Yields:
        CacheManager instance or None
    """
    yield _cache_instance


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

    The module-level CacheManager (if available) is injected into the service
    before initialization so all data-fetching methods benefit from caching.

    Yields:
        Initialized ExternalDataService instance with optional cache
    """
    service = get_data_service()

    # Inject cache into the service instance (cache=None means no caching)
    service._cache = _cache_instance

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


@lru_cache
def get_qdrant_client() -> QdrantVectorStore:
    """Get or create singleton QdrantVectorStore instance.

    Initializes a QdrantVectorStore with url, collection, and api_key
    from the RAGConfig singleton. Creates the collection and payload
    indexes on first access if they do not exist.

    Returns:
        QdrantVectorStore instance configured for the application.
    """
    embedding_client = BGEEmbeddingClient()
    vector_store = QdrantVectorStore(
        url=rag_config.QDRANT_URL,
        collection=rag_config.QDRANT_COLLECTION,
        api_key=rag_config.QDRANT_API_KEY,
        embedding_client=embedding_client,
    )
    return vector_store


def check_qdrant_health() -> bool:
    """Check if Qdrant is reachable and the collection exists.

    Attempts to connect to the Qdrant server and retrieve collection
    info. Returns True if the connection succeeds, False otherwise.

    Returns:
        True if Qdrant is reachable, False otherwise.
    """
    try:
        vector_store = get_qdrant_client()
        vector_store.ensure_collection_exists()
        logger.info(
            "Qdrant health check passed: url=%s collection=%s",
            rag_config.QDRANT_URL,
            rag_config.QDRANT_COLLECTION,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Qdrant health check failed: url=%s error=%s",
            rag_config.QDRANT_URL,
            exc,
        )
        return False


__all__ = [
    "get_db",
    "get_cache",
    "init_cache",
    "get_data_service",
    "get_initialized_data_service",
    "get_qdrant_client",
    "check_qdrant_health",
]
