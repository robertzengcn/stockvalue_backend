"""FastAPI dependencies for dependency injection."""

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.config import rag_config
from stockvaluefinder.db.base import get_db
from stockvaluefinder.external.data_service import ExternalDataService
from stockvaluefinder.middleware.rate_limiter import RateLimiter
from stockvaluefinder.rag.embeddings import BGEEmbeddingClient
from stockvaluefinder.rag.vector_store import QdrantVectorStore
from stockvaluefinder.services.jwt_service import jwt_service
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


# JWT Bearer token scheme
_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Extract and validate user identity from JWT bearer token.

    This dependency extracts the Bearer token from the Authorization header,
    validates it using JWTService, and looks up the user in the database.
    Returns a dict with user identity information.

    Raises:
        HTTPException 401: If token is missing, invalid, or expired.
        HTTPException 403: If user account is disabled.

    Returns:
        Dict with keys: user_id (str), email (str), role (str), is_active (bool)
    """
    import jwt as pyjwt

    from stockvaluefinder.db.models.user import UserDB

    try:
        payload = jwt_service.validate_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Look up user in database to verify they still exist and are active
    stmt = select(UserDB).where(UserDB.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return {
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


async def require_admin(
    current_user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    """Require that the current user has admin role.

    Builds on get_current_user by additionally checking the role field.

    Raises:
        HTTPException 403: If user is not an admin.

    Returns:
        Same user dict as get_current_user (guaranteed admin role)
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Module-level RateLimiter instance, initialized during lifespan
_rate_limiter: RateLimiter | None = None


def init_rate_limiter(redis: "redis.asyncio.Redis") -> RateLimiter:  # type: ignore[name-defined]  # noqa: F821
    """Initialize the module-level RateLimiter instance.

    Called from application lifespan during startup after Redis is connected.

    Args:
        redis: Connected Redis async client

    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    _rate_limiter = RateLimiter(redis=redis, default_limit=100, window_seconds=3600)
    return _rate_limiter


async def rate_limit(
    request: Request,
    current_user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    """Rate limit dependency for analysis endpoints.

    Checks per-user rate limit using Redis sliding window. Adds rate limit
    headers to the response. Admin users bypass rate limiting entirely.

    Args:
        request: FastAPI Request object (used to access response state)
        current_user: Current user dict from get_current_user

    Returns:
        Current user dict if rate limit not exceeded

    Raises:
        HTTPException 429: If rate limit exceeded, with Retry-After header
    """
    # Admin bypasses rate limiting
    if current_user.get("role") == "admin":
        return current_user

    user_id = current_user.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity",
        )

    # If rate limiter not initialized (Redis unavailable), allow request
    if _rate_limiter is None:
        return current_user

    result = await _rate_limiter.check_rate_limit(str(user_id))

    # Store result in request state so response middleware can add headers
    request.state.rate_limit_result = result

    if not result.allowed:
        retry_after = result.reset_at - int(time.time())
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_at),
            },
        )

    return current_user


__all__ = [
    "get_db",
    "get_cache",
    "init_cache",
    "get_data_service",
    "get_initialized_data_service",
    "get_qdrant_client",
    "check_qdrant_health",
    "get_current_user",
    "require_admin",
    "rate_limit",
    "init_rate_limiter",
]
