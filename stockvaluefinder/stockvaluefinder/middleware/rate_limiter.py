"""Per-user rate limiting using Redis INCR + EXPIRE."""

import logging
import time
from dataclasses import dataclass

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    limit: int
    reset_at: int  # Unix timestamp when the window resets


@dataclass(frozen=True)
class RateLimitOverride:
    """Per-user rate limit override stored in Redis Hash."""

    limit: int
    window: int


class RateLimiter:
    """Per-user rate limiter using Redis sliding window (fixed window approach).

    Uses Redis INCR + EXPIRE for atomic counting. Each user gets a Redis key
    per time window. When the key does not exist, INCR creates it with value 1
    and we set EXPIRE. Subsequent requests increment the counter.

    Args:
        redis: Redis async client instance
        default_limit: Maximum requests per window (default 100)
        window_seconds: Window duration in seconds (default 3600 = 1 hour)
    """

    def __init__(
        self,
        redis: Redis,
        default_limit: int = 100,
        window_seconds: int = 3600,
    ) -> None:
        self._redis = redis
        self._default_limit = default_limit
        self._window_seconds = window_seconds

    def _build_key(self, user_id: str, window_start: int) -> str:
        """Build Redis key for rate limit counter.

        Args:
            user_id: User identifier
            window_start: Window start timestamp

        Returns:
            Redis key string
        """
        return f"rate_limit:{user_id}:{window_start}"

    async def check_rate_limit(
        self,
        user_id: str,
        limit: int | None = None,
        window_seconds: int | None = None,
    ) -> RateLimitResult:
        """Check and increment rate limit counter for a user.

        Checks for a per-user override in Redis before falling back to defaults.
        If a per-user override exists, it takes precedence over the limit and
        window_seconds parameters.

        Args:
            user_id: User identifier to rate limit
            limit: Override default limit (None uses default)
            window_seconds: Override default window (None uses default)

        Returns:
            RateLimitResult with allowed status, remaining count, and reset time
        """
        # Check for per-user override first
        override = await self._get_user_override(user_id)
        if override is not None:
            effective_limit = override.limit
            effective_window = override.window
        else:
            effective_limit = limit if limit is not None else self._default_limit
            effective_window = (
                window_seconds if window_seconds is not None else self._window_seconds
            )

        current_time = int(time.time())
        window_start = (current_time // effective_window) * effective_window
        reset_at = window_start + effective_window

        key = self._build_key(user_id, window_start)

        try:
            # Atomic increment
            count = await self._redis.incr(key)

            # Set expiry only on first request in this window
            if count == 1:
                await self._redis.expire(key, effective_window)

            remaining = max(0, effective_limit - count)
            allowed = count <= effective_limit

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                limit=effective_limit,
                reset_at=reset_at,
            )
        except Exception as e:
            # Graceful degradation: if Redis is down, allow the request
            logger.warning(
                f"Rate limit check failed for user {user_id}: {e}. Allowing request."
            )
            return RateLimitResult(
                allowed=True,
                remaining=effective_limit,
                limit=effective_limit,
                reset_at=current_time + effective_window,
            )

    async def get_current_usage(
        self,
        user_id: str,
        window_seconds: int | None = None,
    ) -> tuple[int, int]:
        """Get current usage for a user without incrementing.

        Args:
            user_id: User identifier
            window_seconds: Override default window

        Returns:
            Tuple of (current_count, window_start_timestamp)
        """
        effective_window = (
            window_seconds if window_seconds is not None else self._window_seconds
        )
        current_time = int(time.time())
        window_start = (current_time // effective_window) * effective_window
        key = self._build_key(user_id, window_start)

        try:
            count = await self._redis.get(key)
            return (int(count) if count else 0, window_start)
        except Exception:
            return (0, window_start)

    async def reset_user_limit(self, user_id: str) -> None:
        """Reset rate limit counter for a user (delete all their rate limit keys).

        Uses SCAN to find all matching keys and deletes them.

        Args:
            user_id: User identifier to reset
        """
        pattern = f"rate_limit:{user_id}:*"
        try:
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
        except Exception as e:
            logger.warning(f"Failed to reset rate limit for user {user_id}: {e}")

    def _build_override_key(self, user_id: str) -> str:
        """Build Redis key for per-user rate limit override.

        Args:
            user_id: User identifier

        Returns:
            Redis key string for the override hash
        """
        return f"rate_limit_override:{user_id}"

    async def _get_user_override(self, user_id: str) -> RateLimitOverride | None:
        """Look up per-user rate limit override from Redis Hash.

        Args:
            user_id: User identifier

        Returns:
            RateLimitOverride if found, None otherwise
        """
        key = self._build_override_key(user_id)
        try:
            data = await self._redis.hgetall(key)  # type: ignore[misc]
            if data and b"limit" in data:
                return RateLimitOverride(
                    limit=int(data[b"limit"]),
                    window=int(data[b"window"]),
                )
        except Exception:
            pass
        return None

    async def get_user_override(self, user_id: str) -> RateLimitOverride | None:
        """Public method to retrieve per-user rate limit override.

        Used by admin endpoints to inspect current overrides.

        Args:
            user_id: User identifier

        Returns:
            RateLimitOverride if found, None otherwise
        """
        return await self._get_user_override(user_id)

    async def set_user_override(self, user_id: str, limit: int, window: int) -> None:
        """Set a per-user rate limit override in Redis Hash.

        Args:
            user_id: User identifier
            limit: Maximum requests per window
            window: Window duration in seconds
        """
        key = self._build_override_key(user_id)
        try:
            await self._redis.hset(key, mapping={b"limit": limit, b"window": window})  # type: ignore[arg-type, misc]
        except Exception as e:
            logger.warning(f"Failed to set rate limit override for user {user_id}: {e}")

    async def remove_user_override(self, user_id: str) -> None:
        """Remove a per-user rate limit override from Redis.

        Args:
            user_id: User identifier
        """
        key = self._build_override_key(user_id)
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.warning(
                f"Failed to remove rate limit override for user {user_id}: {e}"
            )
