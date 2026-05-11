"""Per-user API usage tracking using Redis Hashes.

Tracks per-user per-endpoint call counts, error counts, and last-active
timestamps in Redis Hashes. Data is structured for periodic DB flush
to the api_usage_records table.
"""

import logging
import time

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Redis key TTL for usage hashes (24 hours)
_USAGE_TTL_SECONDS = 86400


class UsageTracker:
    """Per-user API usage tracker using Redis Hashes.

    Uses Redis HINCRBY for atomic counter increments and a separate
    string key for the last-active timestamp. All operations use
    Redis pipeline for batching.

    Args:
        redis: Redis async client instance
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _build_usage_key(self, user_id: str) -> str:
        """Build Redis key for the user usage hash.

        Args:
            user_id: User identifier

        Returns:
            Redis key string in format "usage:{user_id}"
        """
        return f"usage:{user_id}"

    def _build_last_active_key(self, user_id: str) -> str:
        """Build Redis key for the user last-active timestamp.

        Args:
            user_id: User identifier

        Returns:
            Redis key string in format "usage:last_active:{user_id}"
        """
        return f"usage:last_active:{user_id}"

    async def record_request(
        self, user_id: str, endpoint: str, status_code: int
    ) -> None:
        """Record an API request for a user.

        Atomically increments per-endpoint and total call counters,
        updates the last-active timestamp, and optionally tracks error
        counts when the status code indicates a failure.

        All operations are batched in a Redis pipeline for efficiency.

        Args:
            user_id: User identifier (from JWT, not user input)
            endpoint: API endpoint path (from request.url.path)
            status_code: HTTP response status code
        """
        usage_key = self._build_usage_key(user_id)
        last_active_key = self._build_last_active_key(user_id)
        timestamp = str(time.time())

        try:
            async with self._redis.pipeline() as pipe:
                # Increment per-endpoint call counter
                pipe.hincrby(usage_key, f"calls:{endpoint}", 1)
                # Increment total calls counter
                pipe.hincrby(usage_key, "total_calls", 1)

                # Track errors when status_code >= 400
                if status_code >= 400:
                    pipe.hincrby(usage_key, f"errors:{endpoint}", 1)
                    pipe.hincrby(usage_key, "total_errors", 1)

                # Update last-active timestamp
                pipe.set(last_active_key, timestamp)
                # Set TTL on usage hash (refreshed on each request)
                pipe.expire(usage_key, _USAGE_TTL_SECONDS)

                await pipe.execute()
        except Exception as e:
            logger.warning(
                f"Usage tracking failed for user {user_id}: {e}. "
                "Continuing without tracking."
            )

    async def get_user_usage(self, user_id: str) -> dict[str, str]:
        """Retrieve all usage counters for a user.

        Args:
            user_id: User identifier

        Returns:
            Dict mapping field names to string values from the Redis hash.
            Returns empty dict on error or when no data exists.
        """
        usage_key = self._build_usage_key(user_id)
        try:
            raw = await self._redis.hgetall(usage_key)  # type: ignore[misc]
            # Convert bytes keys/values to strings
            return {
                (k.decode() if isinstance(k, bytes) else k): (
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in raw.items()
            }
        except Exception as e:
            logger.warning(f"Failed to get usage for user {user_id}: {e}")
            return {}

    async def get_last_active(self, user_id: str) -> str | None:
        """Retrieve the last-active timestamp for a user.

        Args:
            user_id: User identifier

        Returns:
            Timestamp string or None if no activity recorded.
        """
        last_active_key = self._build_last_active_key(user_id)
        try:
            raw = await self._redis.get(last_active_key)
            if raw is None:
                return None
            return raw.decode() if isinstance(raw, bytes) else raw
        except Exception as e:
            logger.warning(f"Failed to get last_active for user {user_id}: {e}")
            return None
