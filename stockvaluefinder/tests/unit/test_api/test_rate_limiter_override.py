"""Unit tests for rate limit override schemas, ORM model, and RateLimiter override behavior.

Tests:
1. RateLimitOverrideRequest validates limit (positive int) and window_seconds (positive int)
2. RateLimitOverrideRequest rejects limit=0 or negative values
3. RateLimitOverrideResponse serializes user_id, limit, window_seconds correctly
4. RateLimitOverrideDB ORM model has correct columns
5. check_rate_limit uses per-user override when Redis Hash exists for user
6. check_rate_limit falls back to defaults when no override exists
7. set_user_override writes limit and window to Redis Hash
8. remove_user_override deletes the Redis Hash for a user
9. get_user_override returns None when no override exists
10. get_user_override returns parsed override data when exists
"""

import os
from unittest.mock import AsyncMock

import pytest

# Set DATABASE_URL before importing any app modules
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy"
)

from stockvaluefinder.middleware.rate_limiter import RateLimiter


class TestRateLimitOverrideRequest:
    """Tests for RateLimitOverrideRequest Pydantic schema."""

    def test_valid_override_request(self) -> None:
        """RateLimitOverrideRequest accepts valid limit and window_seconds."""
        from stockvaluefinder.models.rate_limit_config import RateLimitOverrideRequest

        req = RateLimitOverrideRequest(limit=200, window_seconds=7200)
        assert req.limit == 200
        assert req.window_seconds == 7200

    def test_rejects_zero_limit(self) -> None:
        """RateLimitOverrideRequest rejects limit=0."""
        from pydantic import ValidationError

        from stockvaluefinder.models.rate_limit_config import RateLimitOverrideRequest

        with pytest.raises(ValidationError) as exc_info:
            RateLimitOverrideRequest(limit=0, window_seconds=7200)
        # Check that limit field has the error
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "limit" in field_names

    def test_rejects_negative_limit(self) -> None:
        """RateLimitOverrideRequest rejects negative limit."""
        from pydantic import ValidationError

        from stockvaluefinder.models.rate_limit_config import RateLimitOverrideRequest

        with pytest.raises(ValidationError) as exc_info:
            RateLimitOverrideRequest(limit=-5, window_seconds=3600)
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "limit" in field_names

    def test_rejects_zero_window_seconds(self) -> None:
        """RateLimitOverrideRequest rejects window_seconds=0."""
        from pydantic import ValidationError

        from stockvaluefinder.models.rate_limit_config import RateLimitOverrideRequest

        with pytest.raises(ValidationError) as exc_info:
            RateLimitOverrideRequest(limit=100, window_seconds=0)
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "window_seconds" in field_names

    def test_rejects_negative_window_seconds(self) -> None:
        """RateLimitOverrideRequest rejects negative window_seconds."""
        from pydantic import ValidationError

        from stockvaluefinder.models.rate_limit_config import RateLimitOverrideRequest

        with pytest.raises(ValidationError) as exc_info:
            RateLimitOverrideRequest(limit=100, window_seconds=-60)
        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "window_seconds" in field_names


class TestRateLimitOverrideResponse:
    """Tests for RateLimitOverrideResponse Pydantic schema."""

    def test_serializes_all_fields(self) -> None:
        """RateLimitOverrideResponse serializes user_id, limit, window_seconds."""
        from stockvaluefinder.models.rate_limit_config import RateLimitOverrideResponse

        resp = RateLimitOverrideResponse(
            user_id="abc-123",
            limit=200,
            window_seconds=7200,
        )
        assert resp.user_id == "abc-123"
        assert resp.limit == 200
        assert resp.window_seconds == 7200

    def test_serializes_to_json(self) -> None:
        """RateLimitOverrideResponse can be serialized to JSON."""
        from stockvaluefinder.models.rate_limit_config import RateLimitOverrideResponse

        resp = RateLimitOverrideResponse(
            user_id="user-456",
            limit=50,
            window_seconds=1800,
        )
        data = resp.model_dump()
        assert data == {
            "user_id": "user-456",
            "limit": 50,
            "window_seconds": 1800,
        }


class TestRateLimitOverrideDB:
    """Tests for RateLimitOverrideDB ORM model."""

    def test_orm_model_has_correct_tablename(self) -> None:
        """RateLimitOverrideDB uses 'rate_limit_overrides' tablename."""
        from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

        assert RateLimitOverrideDB.__tablename__ == "rate_limit_overrides"

    def test_orm_model_has_user_id_column(self) -> None:
        """RateLimitOverrideDB has user_id column with ForeignKey to users.id."""
        from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

        # Check that user_id column exists
        assert hasattr(RateLimitOverrideDB, "user_id")
        # Check that it is a mapped column
        mapper = RateLimitOverrideDB.__table__
        assert "user_id" in mapper.columns

    def test_orm_model_has_limit_column(self) -> None:
        """RateLimitOverrideDB has limit column."""
        from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

        mapper = RateLimitOverrideDB.__table__
        assert "limit" in mapper.columns

    def test_orm_model_has_window_seconds_column(self) -> None:
        """RateLimitOverrideDB has window_seconds column."""
        from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

        mapper = RateLimitOverrideDB.__table__
        assert "window_seconds" in mapper.columns

    def test_orm_model_has_timestamps(self) -> None:
        """RateLimitOverrideDB has created_at and updated_at columns."""
        from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

        mapper = RateLimitOverrideDB.__table__
        assert "created_at" in mapper.columns
        assert "updated_at" in mapper.columns

    def test_user_id_has_unique_constraint(self) -> None:
        """RateLimitOverrideDB.user_id has unique=True."""
        from stockvaluefinder.db.models.rate_limit_override import RateLimitOverrideDB

        user_id_col = RateLimitOverrideDB.__table__.columns["user_id"]
        assert user_id_col.unique is True


class TestRateLimiterOverrideBehavior:
    """Tests for RateLimiter per-user override lookup and management."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis async client."""
        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        redis.hgetall = AsyncMock(return_value={})
        redis.hset = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def rate_limiter(self, mock_redis: AsyncMock) -> RateLimiter:
        """Create a RateLimiter with mock Redis."""
        return RateLimiter(redis=mock_redis, default_limit=100, window_seconds=3600)

    async def test_check_rate_limit_uses_override_when_present(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """check_rate_limit uses per-user override when Redis Hash exists for user."""
        from stockvaluefinder.middleware.rate_limiter import RateLimitResult

        # Set up Redis to return override data
        mock_redis.hgetall.return_value = {
            b"limit": b"200",
            b"window": b"7200",
        }
        mock_redis.incr.return_value = 1

        result = await rate_limiter.check_rate_limit("user123")

        assert isinstance(result, RateLimitResult)
        # Override says limit=200, window=7200
        assert result.limit == 200
        # Verify override key was checked
        mock_redis.hgetall.assert_called()

    async def test_check_rate_limit_falls_back_to_defaults(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """check_rate_limit falls back to defaults when no override exists."""
        from stockvaluefinder.middleware.rate_limiter import RateLimitResult

        # No override in Redis
        mock_redis.hgetall.return_value = {}
        mock_redis.incr.return_value = 1

        result = await rate_limiter.check_rate_limit("user123")

        assert isinstance(result, RateLimitResult)
        # Default limit=100, window=3600
        assert result.limit == 100

    async def test_set_user_override_writes_to_redis(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """set_user_override writes limit and window to Redis Hash."""
        await rate_limiter.set_user_override("user123", limit=200, window=7200)

        # Verify hset was called with the correct key
        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        key = call_args[0][0]
        assert key == "rate_limit_override:user123"

        # Verify the mapping contains the expected values
        mapping = call_args[1].get("mapping") or call_args[0][1]
        assert mapping[b"limit"] == 200 or mapping["limit"] == 200
        assert mapping[b"window"] == 7200 or mapping["window"] == 7200

    async def test_remove_user_override_deletes_redis_key(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """remove_user_override deletes the Redis Hash for a user."""
        await rate_limiter.remove_user_override("user123")

        mock_redis.delete.assert_called_once_with("rate_limit_override:user123")

    async def test_get_user_override_returns_none_when_absent(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """get_user_override returns None when no override exists."""
        mock_redis.hgetall.return_value = {}

        result = await rate_limiter.get_user_override("user123")

        assert result is None

    async def test_get_user_override_returns_data_when_present(
        self, rate_limiter: RateLimiter, mock_redis: AsyncMock
    ) -> None:
        """get_user_override returns parsed override data when exists."""
        mock_redis.hgetall.return_value = {
            b"limit": b"200",
            b"window": b"7200",
        }

        result = await rate_limiter.get_user_override("user123")

        assert result is not None
        assert result.limit == 200
        assert result.window == 7200
