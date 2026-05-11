"""Unit tests for UsageTracker middleware and related components.

Tests the Redis-backed per-user usage tracker, Pydantic schemas,
ORM model, usage middleware, and dependencies.
"""

import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set DATABASE_URL before importing any app modules
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy"
)

from stockvaluefinder.middleware.usage_tracker import UsageTracker
from stockvaluefinder.models.usage import EndpointUsage, UsageSummary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pipeline() -> MagicMock:
    """Create a mock Redis pipeline with sync methods and async execute.

    Redis async pipeline's hincrby/set/expire are synchronous (they queue
    commands). Only execute() is async.
    """
    pipeline = MagicMock()
    pipeline.hincrby = MagicMock(return_value=pipeline)
    pipeline.set = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[True])
    # Support async context manager: async with redis.pipeline() as pipe
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock(return_value=False)
    return pipeline


@pytest.fixture
def mock_redis(mock_pipeline: MagicMock) -> AsyncMock:
    """Create a mock Redis async client."""
    redis = AsyncMock()
    redis.pipeline = MagicMock(return_value=mock_pipeline)
    redis.hgetall = AsyncMock(return_value={})
    redis.get = AsyncMock(return_value=None)
    return redis


@pytest.fixture
def usage_tracker(mock_redis: AsyncMock, mock_pipeline: MagicMock) -> UsageTracker:
    """Create a UsageTracker with mock Redis."""
    return UsageTracker(redis=mock_redis)


# ---------------------------------------------------------------------------
# Task 1 Tests: UsageTracker + Pydantic schemas + ORM model
# ---------------------------------------------------------------------------


class TestRecordRequest:
    """Tests for UsageTracker.record_request."""

    async def test_record_request_increments_endpoint_counter(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request increments per-endpoint counter via HINCRBY."""
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )

        # Verify hincrby called with correct key, field, and amount
        hincrby_calls = mock_pipeline.hincrby.call_args_list
        keys_used = [(call[0][0], call[0][1]) for call in hincrby_calls]
        assert ("usage:user123", "calls:/api/v1/analyze/risk") in keys_used

    async def test_record_request_increments_total_calls(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request increments total_calls counter."""
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )

        hincrby_calls = mock_pipeline.hincrby.call_args_list
        keys_used = [(call[0][0], call[0][1]) for call in hincrby_calls]
        assert ("usage:user123", "total_calls") in keys_used

    async def test_record_request_updates_last_active(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request updates last_active timestamp."""
        before = time.time()
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )
        after = time.time()

        # Verify pipeline.set called for last_active
        set_calls = mock_pipeline.set.call_args_list
        assert len(set_calls) >= 1
        # Find the last_active set call
        last_active_call = None
        for call in set_calls:
            if "last_active" in call[0][0]:
                last_active_call = call
                break
        assert last_active_call is not None
        key = last_active_call[0][0]
        assert key == "usage:last_active:user123"
        # Verify the timestamp is a string of a number close to now
        timestamp_str = last_active_call[0][1]
        timestamp = float(timestamp_str)
        assert before <= timestamp <= after

    async def test_record_request_tracks_errors_when_status_ge_400(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request tracks error counts when status_code >= 400."""
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=500,
        )

        hincrby_calls = mock_pipeline.hincrby.call_args_list
        keys_used = [(call[0][0], call[0][1]) for call in hincrby_calls]
        assert ("usage:user123", "errors:/api/v1/analyze/risk") in keys_used
        assert ("usage:user123", "total_errors") in keys_used

    async def test_record_request_no_errors_when_status_lt_400(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request does NOT track errors when status_code < 400."""
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )

        hincrby_calls = mock_pipeline.hincrby.call_args_list
        keys_used = [(call[0][0], call[0][1]) for call in hincrby_calls]
        assert ("usage:user123", "errors:/api/v1/analyze/risk") not in keys_used
        assert ("usage:user123", "total_errors") not in keys_used

    async def test_record_request_executes_pipeline(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request executes the Redis pipeline."""
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )

        mock_pipeline.execute.assert_awaited_once()

    async def test_record_request_sets_expiry(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request sets 86400s expiry on usage hash."""
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )

        expire_calls = mock_pipeline.expire.call_args_list
        assert len(expire_calls) >= 1
        # Check that "usage:user123" key gets 86400 TTL
        expire_keys = [(call[0][0], call[0][1]) for call in expire_calls]
        assert ("usage:user123", 86400) in expire_keys

    async def test_record_request_redis_failure_graceful(
        self,
        usage_tracker: UsageTracker,
        mock_redis: AsyncMock,
        mock_pipeline: MagicMock,
    ) -> None:
        """record_request handles Redis failures gracefully without raising."""
        mock_pipeline.execute.side_effect = ConnectionError("Redis down")

        # Should NOT raise
        await usage_tracker.record_request(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )


class TestGetUserUsage:
    """Tests for UsageTracker.get_user_usage."""

    async def test_get_user_usage_returns_hash_data(
        self, usage_tracker: UsageTracker, mock_redis: AsyncMock
    ) -> None:
        """get_user_usage returns parsed hash data from Redis HGETALL."""
        mock_redis.hgetall.return_value = {
            b"total_calls": b"42",
            b"calls:/api/v1/analyze/risk": b"10",
        }

        result = await usage_tracker.get_user_usage("user123")

        assert result == {"total_calls": "42", "calls:/api/v1/analyze/risk": "10"}
        mock_redis.hgetall.assert_called_once_with("usage:user123")

    async def test_get_user_usage_empty(
        self, usage_tracker: UsageTracker, mock_redis: AsyncMock
    ) -> None:
        """get_user_usage returns empty dict when no data exists."""
        mock_redis.hgetall.return_value = {}

        result = await usage_tracker.get_user_usage("user123")

        assert result == {}

    async def test_get_user_usage_redis_failure(
        self, usage_tracker: UsageTracker, mock_redis: AsyncMock
    ) -> None:
        """get_user_usage handles Redis failure gracefully."""
        mock_redis.hgetall.side_effect = ConnectionError("Redis down")

        result = await usage_tracker.get_user_usage("user123")

        assert result == {}


class TestGetLastActive:
    """Tests for UsageTracker.get_last_active."""

    async def test_get_last_active_returns_timestamp(
        self, usage_tracker: UsageTracker, mock_redis: AsyncMock
    ) -> None:
        """get_last_active returns timestamp string from Redis GET."""
        mock_redis.get.return_value = b"1700000000.123"

        result = await usage_tracker.get_last_active("user123")

        assert result == "1700000000.123"
        mock_redis.get.assert_called_once_with("usage:last_active:user123")

    async def test_get_last_active_returns_none(
        self, usage_tracker: UsageTracker, mock_redis: AsyncMock
    ) -> None:
        """get_last_active returns None when no key exists."""
        mock_redis.get.return_value = None

        result = await usage_tracker.get_last_active("user123")

        assert result is None

    async def test_get_last_active_redis_failure(
        self, usage_tracker: UsageTracker, mock_redis: AsyncMock
    ) -> None:
        """get_last_active handles Redis failure gracefully."""
        mock_redis.get.side_effect = ConnectionError("Redis down")

        result = await usage_tracker.get_last_active("user123")

        assert result is None


class TestEndpointUsage:
    """Tests for EndpointUsage Pydantic schema."""

    def test_endpoint_usage_defaults(self) -> None:
        """EndpointUsage has sensible defaults."""
        usage = EndpointUsage(endpoint="/api/v1/analyze/risk", call_count=10)

        assert usage.endpoint == "/api/v1/analyze/risk"
        assert usage.call_count == 10
        assert usage.error_count == 0

    def test_endpoint_usage_with_errors(self) -> None:
        """EndpointUsage accepts error_count."""
        usage = EndpointUsage(
            endpoint="/api/v1/analyze/risk",
            call_count=10,
            error_count=2,
        )

        assert usage.error_count == 2

    def test_endpoint_usage_serialization(self) -> None:
        """EndpointUsage serializes to JSON correctly."""
        usage = EndpointUsage(
            endpoint="/api/v1/analyze/risk",
            call_count=10,
            error_count=1,
        )
        data = usage.model_dump()

        assert data == {
            "endpoint": "/api/v1/analyze/risk",
            "call_count": 10,
            "error_count": 1,
        }


class TestUsageSummary:
    """Tests for UsageSummary Pydantic schema."""

    def test_usage_summary_defaults(self) -> None:
        """UsageSummary has sensible defaults."""
        summary = UsageSummary(user_id="user123")

        assert summary.user_id == "user123"
        assert summary.total_calls == 0
        assert summary.total_errors == 0
        assert summary.last_active is None
        assert summary.endpoints == []

    def test_usage_summary_full(self) -> None:
        """UsageSummary accepts all fields."""
        summary = UsageSummary(
            user_id="user123",
            total_calls=42,
            total_errors=3,
            last_active="1700000000.0",
            endpoints=[
                EndpointUsage(
                    endpoint="/api/v1/analyze/risk",
                    call_count=30,
                    error_count=2,
                ),
            ],
        )

        assert summary.total_calls == 42
        assert summary.total_errors == 3
        assert summary.last_active == "1700000000.0"
        assert len(summary.endpoints) == 1

    def test_usage_summary_serialization(self) -> None:
        """UsageSummary serializes to JSON correctly."""
        summary = UsageSummary(
            user_id="user123",
            total_calls=5,
            endpoints=[
                EndpointUsage(endpoint="/api/v1/analyze/dcf", call_count=5),
            ],
        )
        data = summary.model_dump()

        assert data["user_id"] == "user123"
        assert data["total_calls"] == 5
        assert len(data["endpoints"]) == 1


# ---------------------------------------------------------------------------
# Task 2 Tests: Middleware + Dependencies
# ---------------------------------------------------------------------------


class TestUsageTrackingMiddleware:
    """Tests for usage_tracking_middleware."""

    def _make_mock_request(self, path: str = "/api/v1/analyze/risk") -> MagicMock:
        """Create a mock FastAPI Request."""
        request = MagicMock()
        request.url = MagicMock()
        request.url.path = path
        request.state = MagicMock()
        return request

    async def test_middleware_tracks_authenticated_request(self) -> None:
        """Middleware calls record_request when request.states.user_id is set."""
        from stockvaluefinder.middleware.usage_middleware import (
            set_usage_tracker,
            usage_tracking_middleware,
        )

        mock_tracker = AsyncMock(spec=UsageTracker)
        set_usage_tracker(mock_tracker)

        request = self._make_mock_request()
        request.state.user_id = "user123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        response = await usage_tracking_middleware(request, call_next)

        assert response == mock_response
        # record_request should have been called
        mock_tracker.record_request.assert_called_once_with(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=200,
        )

    async def test_middleware_skips_unauthenticated_request(self) -> None:
        """Middleware skips tracking when request.state has no user_id."""
        from stockvaluefinder.middleware.usage_middleware import (
            set_usage_tracker,
            usage_tracking_middleware,
        )

        mock_tracker = AsyncMock(spec=UsageTracker)
        set_usage_tracker(mock_tracker)

        request = self._make_mock_request()
        # No user_id attribute on request.state
        del request.state.user_id

        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        response = await usage_tracking_middleware(request, call_next)

        assert response == mock_response
        mock_tracker.record_request.assert_not_called()

    async def test_middleware_skips_non_api_paths(self) -> None:
        """Middleware skips tracking for non-/api/v1/ paths."""
        from stockvaluefinder.middleware.usage_middleware import (
            set_usage_tracker,
            usage_tracking_middleware,
        )

        mock_tracker = AsyncMock(spec=UsageTracker)
        set_usage_tracker(mock_tracker)

        request = self._make_mock_request(path="/health")
        request.state.user_id = "user123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        response = await usage_tracking_middleware(request, call_next)

        assert response == mock_response
        mock_tracker.record_request.assert_not_called()

    async def test_middleware_tracks_error_status(self) -> None:
        """Middleware passes error status_code to record_request."""
        from stockvaluefinder.middleware.usage_middleware import (
            set_usage_tracker,
            usage_tracking_middleware,
        )

        mock_tracker = AsyncMock(spec=UsageTracker)
        set_usage_tracker(mock_tracker)

        request = self._make_mock_request()
        request.state.user_id = "user123"

        mock_response = MagicMock()
        mock_response.status_code = 422
        call_next = AsyncMock(return_value=mock_response)

        response = await usage_tracking_middleware(request, call_next)

        assert response == mock_response
        mock_tracker.record_request.assert_called_once_with(
            user_id="user123",
            endpoint="/api/v1/analyze/risk",
            status_code=422,
        )

    async def test_middleware_no_tracker_set(self) -> None:
        """Middleware works when no tracker is set (graceful degradation)."""
        import stockvaluefinder.middleware.usage_middleware as mod
        from stockvaluefinder.middleware.usage_middleware import (
            usage_tracking_middleware,
        )

        # Save and clear tracker
        original = mod._usage_tracker
        mod._usage_tracker = None

        try:
            request = self._make_mock_request()
            request.state.user_id = "user123"

            mock_response = MagicMock()
            mock_response.status_code = 200
            call_next = AsyncMock(return_value=mock_response)

            response = await usage_tracking_middleware(request, call_next)
            assert response == mock_response
        finally:
            mod._usage_tracker = original


class TestInitUsageTracker:
    """Tests for init_usage_tracker dependency."""

    async def test_init_usage_tracker_creates_instance(self) -> None:
        """init_usage_tracker creates UsageTracker and stores it."""
        from stockvaluefinder.api.dependencies import init_usage_tracker

        mock_redis = AsyncMock()

        with patch("stockvaluefinder.api.dependencies._usage_tracker", None):
            tracker = init_usage_tracker(mock_redis)

        assert isinstance(tracker, UsageTracker)

    async def test_init_usage_tracker_sets_module_variable(self) -> None:
        """init_usage_tracker stores tracker in module-level variable."""
        import stockvaluefinder.api.dependencies as dep_mod
        from stockvaluefinder.api.dependencies import init_usage_tracker

        mock_redis = AsyncMock()
        original = dep_mod._usage_tracker

        try:
            tracker = init_usage_tracker(mock_redis)
            assert dep_mod._usage_tracker is tracker
        finally:
            dep_mod._usage_tracker = original


class TestTrackUsageDependency:
    """Tests for track_usage dependency."""

    async def test_track_usage_sets_user_id_on_request_state(self) -> None:
        """track_usage sets request.state.user_id from current_user dict."""
        from stockvaluefinder.api.dependencies import track_usage

        mock_request = MagicMock()
        mock_request.state = MagicMock()

        current_user = {
            "user_id": "abc-123",
            "email": "test@test.com",
            "role": "user",
            "is_active": True,
        }

        result = await track_usage(
            request=mock_request,
            current_user=current_user,
        )

        assert result == current_user
        assert mock_request.state.user_id == "abc-123"
