"""Unit tests for RateLimiter middleware.

Tests the Redis-backed per-user rate limiter using mocked Redis.
"""

import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set DATABASE_URL before importing any app modules
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy"
)

from stockvaluefinder.middleware.rate_limiter import RateLimiter, RateLimitResult


class _AsyncIterWrapper:
    """Wrap a sync iterable into an async iterable for mocking scan_iter."""

    def __init__(self, items: list[bytes]) -> None:
        self._items = items
        self._index = 0

    def __aiter__(self) -> "_AsyncIterWrapper":
        return self

    async def __anext__(self) -> bytes:
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis async client."""
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    redis.scan_iter = MagicMock(return_value=_AsyncIterWrapper([]))
    return redis


@pytest.fixture
def rate_limiter(mock_redis: AsyncMock) -> RateLimiter:
    """Create a RateLimiter with mock Redis."""
    return RateLimiter(redis=mock_redis, default_limit=100, window_seconds=3600)


class TestCheckRateLimit:
    """Tests for RateLimiter.check_rate_limit."""

    async def test_check_rate_limit_first_request(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """First request returns allowed=True, remaining=99, reset_at is future."""
        mock_redis.incr.return_value = 1

        result = await rate_limiter.check_rate_limit("user123")

        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert result.remaining == 99
        assert result.limit == 100
        assert result.reset_at > int(time.time())

    async def test_check_rate_limit_at_limit(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """When count equals limit (100), request is still allowed with remaining=0."""
        mock_redis.incr.return_value = 100

        result = await rate_limiter.check_rate_limit("user123")

        assert result.allowed is True
        assert result.remaining == 0
        assert result.limit == 100

    async def test_check_rate_limit_exceeds_limit(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """When count exceeds limit (101), request is rejected with allowed=False."""
        mock_redis.incr.return_value = 101

        result = await rate_limiter.check_rate_limit("user123")

        assert result.allowed is False
        assert result.remaining == 0
        assert result.limit == 100

    async def test_rate_limit_key_format(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """Key follows 'rate_limit:{user_id}:{window_start}' format."""
        mock_redis.incr.return_value = 1

        await rate_limiter.check_rate_limit("user123")

        # Verify the key passed to Redis INCR follows the expected format
        incr_call_args = mock_redis.incr.call_args
        key = incr_call_args[0][0]
        assert key.startswith("rate_limit:user123:")
        # The part after the user_id should be a numeric timestamp
        parts = key.split(":")
        assert len(parts) == 3
        assert parts[0] == "rate_limit"
        assert parts[1] == "user123"
        assert parts[2].isdigit()

    async def test_custom_limit_override(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """Using limit=200 allows 200 requests."""
        mock_redis.incr.return_value = 200

        result = await rate_limiter.check_rate_limit("user123", limit=200)

        assert result.allowed is True
        assert result.remaining == 0
        assert result.limit == 200

    async def test_redis_failure_allows_request(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """When Redis raises ConnectionError, rate limiter returns allowed=True."""
        mock_redis.incr.side_effect = ConnectionError("Redis connection refused")

        result = await rate_limiter.check_rate_limit("user123")

        assert result.allowed is True
        assert result.remaining == 100
        assert result.limit == 100

    async def test_window_seconds_parameter(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """RateLimiter respects window_seconds parameter for key and reset."""
        mock_redis.incr.return_value = 1
        current_time = int(time.time())
        window_seconds = 60  # 1-minute window

        result = await rate_limiter.check_rate_limit(
            "user123", window_seconds=window_seconds
        )

        # The reset_at should be within window_seconds of now
        assert result.reset_at <= current_time + window_seconds + 1
        assert result.reset_at > current_time

        # EXPIRE should be called with the custom window
        expire_call_args = mock_redis.expire.call_args
        assert expire_call_args[0][1] == window_seconds

    async def test_expire_set_on_first_request_only(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """EXPIRE is set only when count==1 (first request in window)."""
        # First request
        mock_redis.incr.return_value = 1
        await rate_limiter.check_rate_limit("user123")
        assert mock_redis.expire.call_count == 1

        # Second request (count=2)
        mock_redis.incr.return_value = 2
        await rate_limiter.check_rate_limit("user123")
        # EXPIRE should NOT have been called again
        assert mock_redis.expire.call_count == 1


class TestGetCurrentUsage:
    """Tests for RateLimiter.get_current_usage."""

    async def test_get_current_usage_without_increment(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """get_current_usage reads count without incrementing."""
        mock_redis.get.return_value = b"42"

        count, window_start = await rate_limiter.get_current_usage("user123")

        assert count == 42
        assert isinstance(window_start, int)
        # get should be called, NOT incr
        mock_redis.get.assert_called_once()
        mock_redis.incr.assert_not_called()

    async def test_get_current_usage_no_key(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """get_current_usage returns 0 when no key exists."""
        mock_redis.get.return_value = None

        count, window_start = await rate_limiter.get_current_usage("user123")

        assert count == 0
        assert isinstance(window_start, int)

    async def test_get_current_usage_redis_failure(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """get_current_usage returns (0, window_start) on Redis failure."""
        mock_redis.get.side_effect = ConnectionError("Redis down")

        count, window_start = await rate_limiter.get_current_usage("user123")

        assert count == 0
        assert isinstance(window_start, int)


class TestResetUserLimit:
    """Tests for RateLimiter.reset_user_limit."""

    async def test_reset_user_limit(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """reset_user_limit deletes matching keys."""
        mock_redis.scan_iter.return_value = _AsyncIterWrapper(
            [b"rate_limit:user123:1000", b"rate_limit:user123:2000"]
        )

        await rate_limiter.reset_user_limit("user123")

        # Should delete each key found
        assert mock_redis.delete.call_count == 2

    async def test_reset_user_limit_no_keys(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """reset_user_limit does nothing when no keys match."""
        mock_redis.scan_iter.return_value = iter([])

        await rate_limiter.reset_user_limit("user123")

        mock_redis.delete.assert_not_called()

    async def test_reset_user_limit_redis_failure(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """reset_user_limit handles Redis failure gracefully."""
        mock_redis.scan_iter.side_effect = ConnectionError("Redis down")

        # Should not raise
        await rate_limiter.reset_user_limit("user123")


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    def test_rate_limit_result_is_frozen(self) -> None:
        """RateLimitResult is immutable (frozen dataclass)."""
        result = RateLimitResult(
            allowed=True, remaining=99, limit=100, reset_at=1700000000
        )

        with pytest.raises(AttributeError):
            result.allowed = False  # type: ignore[misc]

    def test_rate_limit_result_fields(self) -> None:
        """RateLimitResult has expected fields."""
        result = RateLimitResult(
            allowed=False, remaining=0, limit=100, reset_at=1700000000
        )

        assert result.allowed is False
        assert result.remaining == 0
        assert result.limit == 100
        assert result.reset_at == 1700000000


class TestRateLimitDependency:
    """Tests for the rate_limit FastAPI dependency."""

    def _make_mock_request(self) -> MagicMock:
        """Create a mock FastAPI Request with state."""
        request = MagicMock()
        request.state = MagicMock()
        return request

    async def test_rate_limit_stores_result_in_request_state(
        self, mock_redis: AsyncMock
    ) -> None:
        """rate_limit dependency stores RateLimitResult in request.state."""
        from stockvaluefinder.api.dependencies import rate_limit

        mock_redis.incr.return_value = 1
        request = self._make_mock_request()
        user = {
            "user_id": "user123",
            "email": "test@test.com",
            "role": "user",
            "is_active": True,
        }

        with patch("stockvaluefinder.api.dependencies._rate_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=RateLimitResult(
                    allowed=True, remaining=99, limit=100, reset_at=1700003600
                )
            )
            result = await rate_limit(request=request, current_user=user)

        assert result == user
        assert hasattr(request.state, "rate_limit_result")
        assert request.state.rate_limit_result.remaining == 99

    async def test_rate_limit_returns_429_when_exceeded(self) -> None:
        """rate_limit dependency raises HTTPException 429 when rate limit exceeded."""
        from fastapi import HTTPException

        from stockvaluefinder.api.dependencies import rate_limit

        request = self._make_mock_request()
        user = {
            "user_id": "user123",
            "email": "test@test.com",
            "role": "user",
            "is_active": True,
        }

        with patch("stockvaluefinder.api.dependencies._rate_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=RateLimitResult(
                    allowed=False, remaining=0, limit=100, reset_at=1700003600
                )
            )
            with pytest.raises(HTTPException) as exc_info:
                await rate_limit(request=request, current_user=user)

        assert exc_info.value.status_code == 429
        headers = exc_info.value.headers
        assert headers is not None
        assert "Retry-After" in headers
        assert "X-RateLimit-Remaining" in headers
        assert headers["X-RateLimit-Remaining"] == "0"

    async def test_rate_limit_admin_bypass(self) -> None:
        """rate_limit dependency allows admin users without counting."""
        from stockvaluefinder.api.dependencies import rate_limit

        request = self._make_mock_request()
        admin_user = {
            "user_id": "admin1",
            "email": "admin@test.com",
            "role": "admin",
            "is_active": True,
        }

        with patch("stockvaluefinder.api.dependencies._rate_limiter") as mock_limiter:
            result = await rate_limit(request=request, current_user=admin_user)

        assert result == admin_user
        # check_rate_limit should NOT be called for admin
        mock_limiter.check_rate_limit.assert_not_called()

    async def test_rate_limit_no_limiter_initialized(self) -> None:
        """rate_limit dependency allows request when RateLimiter is not initialized."""
        from stockvaluefinder.api.dependencies import rate_limit

        request = self._make_mock_request()
        user = {
            "user_id": "user123",
            "email": "test@test.com",
            "role": "user",
            "is_active": True,
        }

        with patch("stockvaluefinder.api.dependencies._rate_limiter", None):
            result = await rate_limit(request=request, current_user=user)

        assert result == user

    async def test_rate_limit_no_user_id(self) -> None:
        """rate_limit dependency raises 401 when user_id is missing."""
        from fastapi import HTTPException

        from stockvaluefinder.api.dependencies import rate_limit

        request = self._make_mock_request()
        user = {"email": "test@test.com", "role": "user", "is_active": True}

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request=request, current_user=user)

        assert exc_info.value.status_code == 401
