"""Redis cache management with decorators."""

import json
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from functools import wraps
from typing import Any, ParamSpec

from redis.asyncio import Redis, ConnectionPool
from typing_extensions import Concatenate

from stockvaluefinder.utils.errors import CacheError

logger = logging.getLogger(__name__)

P = ParamSpec("P")


class CacheManager:
    """Async Redis cache manager with serialization support."""

    def __init__(self, redis_url: str) -> None:
        """Initialize CacheManager with Redis connection pool.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
        """
        self._pool: ConnectionPool | None = None
        self._redis: Redis | None = None
        self._redis_url = redis_url
        self._connected = False

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._connected:
            return

        try:
            self._pool = ConnectionPool.from_url(self._redis_url)
            self._redis = Redis(connection_pool=self._pool)
            assert self._redis is not None  # for type checker
            result = self._redis.ping()
            await result  # type: ignore[misc]
            self._connected = True
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise CacheError(f"Redis connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.disconnect()
        self._connected = False
        logger.info("Disconnected from Redis cache")

    @property
    def redis(self) -> Redis:
        """Get Redis client, raising error if not connected."""
        if not self._connected or self._redis is None:
            raise CacheError("Redis cache is not connected. Call connect() first.")
        return self._redis

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Deserialized value or None if not found
        """
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get failed for key '{key}': {e}")
            raise CacheError(f"Failed to get cache key '{key}': {e}") from e

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds (None for no expiration)
        """
        try:
            serialized = json.dumps(value)
            if ttl:
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)
            logger.debug(f"Cached key '{key}' with TTL={ttl}")
        except Exception as e:
            logger.error(f"Cache set failed for key '{key}': {e}")
            raise CacheError(f"Failed to set cache key '{key}': {e}") from e

    async def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if key didn't exist
        """
        try:
            result = await self.redis.delete(key)
            deleted = result > 0
            if deleted:
                logger.debug(f"Deleted cache key '{key}'")
            return deleted  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Cache delete failed for key '{key}': {e}")
            raise CacheError(f"Failed to delete cache key '{key}': {e}") from e

    async def delete_by_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "stock:*")

        Returns:
            Number of keys deleted
        """
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await self.redis.delete(*keys)  # type: ignore[no-any-return]
            return 0
        except Exception as e:
            logger.error(f"Cache pattern delete failed for '{pattern}': {e}")
            raise CacheError(f"Failed to delete cache pattern '{pattern}': {e}") from e

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists, False otherwise
        """
        try:
            return await self.redis.exists(key) > 0  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Cache exists check failed for key '{key}': {e}")
            return False

    async def clear(self) -> None:
        """Clear all keys in the current database."""
        try:
            await self.redis.flushdb()
            logger.warning("Cleared all cache keys")
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            raise CacheError("Failed to clear cache") from e


def build_cache_key(version: str, prefix: str, *parts: str) -> str:
    """Build a versioned cache key from components.

    Args:
        version: Cache key version for invalidation control (e.g., "v1")
        prefix: Key prefix describing the data type (e.g., "financial_report")
        *parts: Additional key parts (e.g., ticker, year)

    Returns:
        Colon-separated cache key string

    Example:
        >>> build_cache_key("v1", "financial_report", "600519.SH")
        'v1:financial_report:600519.SH'
        >>> build_cache_key("v1", "price", "600519.SH", "2024")
        'v1:price:600519.SH:2024'
    """
    components = [version, prefix, *parts]
    return ":".join(components)


async def cacheable(
    cache: CacheManager | None,
    prefix: str,
    ttl: int,
    version: str,
    identifier: str,
    fn: Callable[..., Coroutine[Any, Any, Any]],
    **fn_kwargs: Any,
) -> Any:
    """Cache wrapper that adds cached_at metadata to results.

    Checks cache for a hit; on miss calls the provided async function,
    stores the result with a cached_at ISO timestamp, and returns
    the result annotated with _cache metadata.

    If cache is None (graceful degradation), calls fn directly without
    cache metadata.

    Args:
        cache: CacheManager instance or None for no-cache mode
        prefix: Cache key prefix (e.g., "financial_report")
        ttl: Time to live in seconds
        version: Cache key version string
        identifier: Primary identifier for the cache key (e.g., ticker)
        fn: Async function to call on cache miss
        **fn_kwargs: Keyword arguments to pass to fn

    Returns:
        Result with _cache metadata dict containing hit and cached_at fields
    """
    # No cache available - call function directly
    if cache is None:
        return await fn(**fn_kwargs)

    cache_key = build_cache_key(version, prefix, identifier)

    # Try cache hit
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for key '{cache_key}'")
            # Mark as hit, preserve existing cached_at
            if isinstance(cached, dict):
                cache_meta = cached.get("_cache", {})
                return {**cached, "_cache": {**cache_meta, "hit": True}}
            return cached
    except CacheError:
        logger.warning(f"Cache get failed for '{cache_key}', calling fn directly")

    # Cache miss - call function
    result = await fn(**fn_kwargs)
    now = datetime.now(timezone.utc).isoformat()

    # Build result with cache metadata
    if isinstance(result, dict):
        result_with_meta = {**result, "_cache": {"hit": False, "cached_at": now}}
    elif result is None:
        result_with_meta = {"_cache": {"hit": False, "cached_at": now}}
    else:
        result_with_meta = result

    # Store in cache
    try:
        await cache.set(cache_key, result_with_meta, ttl=ttl)
        logger.debug(f"Cached result for key '{cache_key}' with TTL={ttl}")
    except CacheError:
        logger.warning(f"Failed to cache result for '{cache_key}'")

    return result_with_meta


def cache_result(
    key_prefix: str,
    ttl: int = 3600,
    key_builder: Callable[P, str] | None = None,
) -> Callable[
    [Callable[Concatenate[CacheManager, P], Any]],
    Callable[Concatenate[CacheManager, P], Any],
]:
    """Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache keys
        ttl: Time to live in seconds (default: 1 hour)
        key_builder: Optional function to build cache key from args.
                    If None, uses key_prefix + args hash.

    Example:
        ```python
        @cache_result("stock:", ttl=600)
        async def get_stock(self, ticker: str) -> Stock:
            return await self.repo.get_by_ticker(ticker)
        ```
    """

    def decorator(
        func: Callable[Concatenate[CacheManager, P], Any],
    ) -> Callable[Concatenate[CacheManager, P], Any]:  # type: ignore[return-value]
        @wraps(func)
        async def wrapper(
            self: CacheManager,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> Any:
            # Build cache key
            if key_builder:
                cache_key = f"{key_prefix}{key_builder(*args, **kwargs)}"
            else:
                # Use function args as part of key
                args_str = "_".join(str(arg) for arg in args)
                kwargs_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{args_str}:{kwargs_str}"

            # Try to get from cache
            try:
                cached = await self.get(cache_key)
                if cached is not None:
                    logger.debug(f"Cache hit for key '{cache_key}'")
                    return cached
            except CacheError:
                logger.warning(
                    f"Cache get failed for '{cache_key}', proceeding with function call"
                )

            # Call function and cache result
            result = await func(self, *args, **kwargs)
            try:
                await self.set(cache_key, result, ttl=ttl)
                logger.debug(f"Cached result for key '{cache_key}'")
            except CacheError:
                logger.warning(f"Failed to cache result for '{cache_key}'")

            return result

        return wrapper

    return decorator


def invalidate_cache(
    *key_patterns: str,
) -> Callable[
    [Callable[P, Any]],
    Callable[P, Any],
]:
    """Decorator to invalidate cache patterns after function execution.

    Args:
        *key_patterns: Cache key patterns to invalidate (e.g., "stock:*")

    Example:
        ```python
        @invalidate_cache("stock:*", "stock:600519.SH:*")
        async def update_stock(self, ticker: str, data: StockUpdate) -> Stock:
            return await self.repo.update(ticker, data)
        ```
    """

    def decorator(
        func: Callable[P, Any],
    ) -> Callable[P, Any]:
        @wraps(func)
        async def wrapper(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> Any:
            result = await func(*args, **kwargs)

            # Invalidate cache patterns
            # Note: This assumes 'self' has a 'cache' attribute of type CacheManager
            self_arg = args[0] if args else None
            if hasattr(self_arg, "cache"):
                cache = getattr(self_arg, "cache")
                if isinstance(cache, CacheManager):
                    for pattern in key_patterns:
                        try:
                            count = await cache.delete_by_pattern(pattern)
                            if count > 0:
                                logger.info(
                                    f"Invalidated {count} keys matching pattern '{pattern}'"
                                )
                        except CacheError as e:
                            logger.warning(
                                f"Failed to invalidate pattern '{pattern}': {e}"
                            )

            return result

        return wrapper

    return decorator
