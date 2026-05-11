"""Background service for flushing Redis usage counters to PostgreSQL.

Periodically scans usage:* keys in Redis, reads their hash data, and
upserts aggregated counts into the api_usage_records table. Uses atomic
RENAME to avoid race conditions between reading and writing.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from redis.asyncio import Redis

from stockvaluefinder.repositories.usage_repo import ApiUsageRepository

logger = logging.getLogger(__name__)


class UsageFlushService:
    """Service for flushing Redis usage counters to PostgreSQL.

    Uses atomic RENAME to swap usage keys to flush keys before reading,
    preventing race conditions with concurrent writes from the
    UsageTracker.

    Args:
        redis: Redis async client instance
        session_factory: Callable that returns an async context manager
            yielding an AsyncSession
    """

    def __init__(
        self,
        redis: Redis,
        session_factory: Callable[..., Any],
    ) -> None:
        self._redis = redis
        self._session_factory = session_factory

    async def flush_redis_to_db(self) -> int:
        """Flush all usage:* keys from Redis to PostgreSQL.

        Uses atomic RENAME to swap keys before reading to avoid race
        conditions with concurrent HINCRBY operations.

        Returns:
            Number of user keys flushed successfully
        """
        flushed = 0
        async for key in self._redis.scan_iter(match="usage:*"):
            key_str = key.decode() if isinstance(key, bytes) else str(key)

            # Skip last_active keys (they are timestamp strings, not hashes)
            if "last_active" in key_str:
                continue

            try:
                # Extract user_id from key: "usage:{user_id}"
                user_id = key_str.split(":")[-1]
                flush_key = f"usage_flush:{user_id}"

                # Atomic rename: swap current key to flush key
                await self._redis.rename(key, flush_key)

                # Read data from the renamed flush key
                data = await self._redis.hgetall(flush_key)  # type: ignore[misc]
                if data:
                    # Convert bytes to strings
                    parsed = {
                        (k.decode() if isinstance(k, bytes) else k): (
                            v.decode() if isinstance(v, bytes) else v
                        )
                        for k, v in data.items()
                    }
                    await self._upsert_hash_data(user_id, parsed)
                    # Delete flush key after successful upsert
                    await self._redis.delete(flush_key)
                    flushed += 1
            except Exception as e:
                logger.warning(f"Failed to flush key {key_str}: {e}")

        return flushed

    async def _upsert_hash_data(self, user_id: str, data: dict[str, str]) -> None:
        """Parse Redis hash data and upsert to DB.

        Extracts per-endpoint call/error counts from hash fields and
        groups them by endpoint prefix (calls:X and errors:X pairs).

        Args:
            user_id: User identifier
            data: Dict of field->value from Redis HGETALL
        """
        # Group data by endpoint
        endpoint_calls: dict[str, int] = defaultdict(int)
        endpoint_errors: dict[str, int] = defaultdict(int)

        for field, value in data.items():
            if field.startswith("calls:"):
                endpoint = field[len("calls:") :]
                endpoint_calls[endpoint] += int(value)
            elif field.startswith("errors:"):
                endpoint = field[len("errors:") :]
                endpoint_errors[endpoint] += int(value)

        now = datetime.now(tz=timezone.utc)

        # Use the session factory to get a session
        async with self._session_factory() as session:
            repo = ApiUsageRepository(session)
            for endpoint, calls in endpoint_calls.items():
                errors = endpoint_errors.get(endpoint, 0)
                await repo.upsert_usage(
                    user_id=user_id,
                    endpoint=endpoint,
                    call_count=calls,
                    error_count=errors,
                    period_start=now,
                    period_end=now,
                )
            await session.commit()
