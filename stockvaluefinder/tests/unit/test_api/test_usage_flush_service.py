"""Tests for UsageFlushService and ApiUsageRepository.

Tests the Redis-to-PostgreSQL flush pipeline, including atomic RENAME
operations, per-key error handling, and repository upsert/aggregation
queries.
"""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set DATABASE_URL before importing any app modules
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy"
)

from stockvaluefinder.repositories.usage_repo import ApiUsageRepository
from stockvaluefinder.services.usage_flush_service import UsageFlushService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis async client."""
    return AsyncMock()


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock DB session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    """Create a mock async_session_maker that yields mock_session."""
    factory = MagicMock()

    async def _session_ctx():
        yield mock_session

    factory.return_value = _session_ctx()
    return factory


@pytest.fixture
def flush_service(
    mock_redis: AsyncMock, mock_session_factory: MagicMock
) -> UsageFlushService:
    """Create a UsageFlushService with mocked dependencies."""
    return UsageFlushService(redis=mock_redis, session_factory=mock_session_factory)


@pytest.fixture
def usage_repo(mock_session: AsyncMock) -> ApiUsageRepository:
    """Create an ApiUsageRepository with mock session."""
    return ApiUsageRepository(session=mock_session)


# ---------------------------------------------------------------------------
# Test 1: flush_redis_to_db SCANs, reads hashes, upserts to DB
# ---------------------------------------------------------------------------


class TestFlushRedisToDb:
    """Tests for UsageFlushService.flush_redis_to_db."""

    async def test_flush_scans_usage_keys_and_upserts(
        self,
        flush_service: UsageFlushService,
        mock_redis: AsyncMock,
    ) -> None:
        """flush_redis_to_db SCANs for usage:* keys, reads hashes, upserts to DB."""

        # Mock scan_iter to yield two usage keys
        async def _scan(*, match):
            for key in [b"usage:user-1", b"usage:user-2"]:
                yield key

        mock_redis.scan_iter = _scan

        # Mock rename to succeed
        mock_redis.rename = AsyncMock()

        # Mock hgetall to return usage data
        hgetall_responses = {
            "usage_flush:user-1": {
                b"calls:/api/v1/analyze/risk": b"5",
                b"errors:/api/v1/analyze/risk": b"1",
                b"total_calls": b"10",
                b"total_errors": b"1",
            },
            "usage_flush:user-2": {
                b"calls:/api/v1/analyze/dcf": b"3",
                b"total_calls": b"3",
                b"total_errors": b"0",
            },
        }

        async def _hgetall(key):
            key_str = key.decode() if isinstance(key, bytes) else key
            return hgetall_responses.get(key_str, {})

        mock_redis.hgetall = _hgetall
        mock_redis.delete = AsyncMock()

        with patch.object(flush_service, "_upsert_hash_data", new_callable=AsyncMock):
            count = await flush_service.flush_redis_to_db()

        assert count == 2

    async def test_flush_uses_rename_for_atomic_swap(
        self,
        flush_service: UsageFlushService,
        mock_redis: AsyncMock,
    ) -> None:
        """flush_redis_to_db uses RENAME to atomically swap keys before reading."""

        async def _scan(*, match):
            yield b"usage:user-abc"

        mock_redis.scan_iter = _scan
        mock_redis.rename = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={b"total_calls": b"5"})
        mock_redis.delete = AsyncMock()

        with patch.object(flush_service, "_upsert_hash_data", new_callable=AsyncMock):
            await flush_service.flush_redis_to_db()

        # Verify rename was called: usage:user-abc -> usage_flush:user-abc
        mock_redis.rename.assert_called_once()
        args = mock_redis.rename.call_args[0]
        assert args[0] == b"usage:user-abc"
        assert args[1] == "usage_flush:user-abc"

    async def test_flush_deletes_flush_key_after_processing(
        self,
        flush_service: UsageFlushService,
        mock_redis: AsyncMock,
    ) -> None:
        """flush_redis_to_db deletes flush keys after successful upsert."""

        async def _scan(*, match):
            yield b"usage:user-1"

        mock_redis.scan_iter = _scan
        mock_redis.rename = AsyncMock()
        mock_redis.hgetall = AsyncMock(return_value={b"total_calls": b"1"})
        mock_redis.delete = AsyncMock()

        with patch.object(flush_service, "_upsert_hash_data", new_callable=AsyncMock):
            await flush_service.flush_redis_to_db()

        mock_redis.delete.assert_called_once_with("usage_flush:user-1")

    async def test_flush_handles_empty_redis_gracefully(
        self,
        flush_service: UsageFlushService,
        mock_redis: AsyncMock,
    ) -> None:
        """flush_redis_to_db handles empty Redis gracefully (no usage keys)."""

        async def _scan(*, match):
            return
            yield  # Make this an async generator that yields nothing

        mock_redis.scan_iter = _scan

        count = await flush_service.flush_redis_to_db()

        assert count == 0

    async def test_flush_skips_last_active_keys(
        self,
        flush_service: UsageFlushService,
        mock_redis: AsyncMock,
    ) -> None:
        """flush_redis_to_db skips usage:last_active:* keys."""

        async def _scan(*, match):
            yield b"usage:last_active:user-1"

        mock_redis.scan_iter = _scan
        mock_redis.rename = AsyncMock()

        count = await flush_service.flush_redis_to_db()

        assert count == 0
        mock_redis.rename.assert_not_called()

    async def test_flush_logs_warning_and_continues_on_key_failure(
        self,
        flush_service: UsageFlushService,
        mock_redis: AsyncMock,
    ) -> None:
        """flush_redis_to_db logs warning and continues on individual key failures."""

        async def _scan(*, match):
            for key in [b"usage:user-1", b"usage:user-2"]:
                yield key

        mock_redis.scan_iter = _scan

        # First rename succeeds, second fails
        call_count = 0

        async def _rename(src, dst):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True
            raise Exception("Redis rename error")

        mock_redis.rename = _rename
        mock_redis.hgetall = AsyncMock(return_value={b"total_calls": b"1"})
        mock_redis.delete = AsyncMock()

        with patch.object(flush_service, "_upsert_hash_data", new_callable=AsyncMock):
            count = await flush_service.flush_redis_to_db()

        # First key succeeds (count=1), second fails but is caught
        assert count == 1


# ---------------------------------------------------------------------------
# Test 5-6: ApiUsageRepository.upsert_usage
# ---------------------------------------------------------------------------


class TestApiUsageRepositoryUpsert:
    """Tests for ApiUsageRepository.upsert_usage."""

    async def test_upsert_usage_creates_new_record(
        self,
        usage_repo: ApiUsageRepository,
        mock_session: AsyncMock,
    ) -> None:
        """upsert_usage creates new record if none exists for user+endpoint+period."""
        # Mock query to return no existing record
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()

        now = datetime.now(tz=timezone.utc)
        await usage_repo.upsert_usage(
            user_id="user-1",
            endpoint="/api/v1/analyze/risk",
            call_count=5,
            error_count=1,
            period_start=now,
            period_end=now,
        )

        # Should have called session.add (new record created)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()

    async def test_upsert_usage_increments_existing_record(
        self,
        usage_repo: ApiUsageRepository,
        mock_session: AsyncMock,
    ) -> None:
        """upsert_usage increments existing record if one already exists."""
        # Mock existing record
        existing = MagicMock()
        existing.call_count = 10
        existing.error_count = 2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        now = datetime.now(tz=timezone.utc)
        await usage_repo.upsert_usage(
            user_id="user-1",
            endpoint="/api/v1/analyze/risk",
            call_count=5,
            error_count=1,
            period_start=now,
            period_end=now,
        )

        # Existing record should be incremented
        assert existing.call_count == 15  # 10 + 5
        assert existing.error_count == 3  # 2 + 1
        # Should NOT have called session.add (no new record)
        mock_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7: ApiUsageRepository.get_user_totals
# ---------------------------------------------------------------------------


class TestApiUsageRepositoryGetUserTotals:
    """Tests for ApiUsageRepository.get_user_totals."""

    async def test_get_user_totals_returns_aggregated_counts(
        self,
        usage_repo: ApiUsageRepository,
        mock_session: AsyncMock,
    ) -> None:
        """get_user_totals returns total call and error counts for a user."""
        mock_row = MagicMock()
        mock_row.total_calls = 42
        mock_row.total_errors = 3

        mock_result = MagicMock()
        mock_result.one_or_none.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await usage_repo.get_user_totals("user-1")

        assert result["total_calls"] == 42
        assert result["total_errors"] == 3

    async def test_get_user_totals_returns_zero_when_no_data(
        self,
        usage_repo: ApiUsageRepository,
        mock_session: AsyncMock,
    ) -> None:
        """get_user_totals returns zeros when user has no usage data."""
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await usage_repo.get_user_totals("nonexistent-user")

        assert result["total_calls"] == 0
        assert result["total_errors"] == 0


# ---------------------------------------------------------------------------
# Test 8: ApiUsageRepository.get_aggregate_stats
# ---------------------------------------------------------------------------


class TestApiUsageRepositoryGetAggregateStats:
    """Tests for ApiUsageRepository.get_aggregate_stats."""

    async def test_get_aggregate_stats_returns_totals_and_top_users(
        self,
        usage_repo: ApiUsageRepository,
        mock_session: AsyncMock,
    ) -> None:
        """get_aggregate_stats returns total_calls, total_errors, top users."""
        # Mock totals query
        totals_row = MagicMock()
        totals_row.total_calls = 1000
        totals_row.total_errors = 50

        # Mock top users query
        top_user_row = MagicMock()
        top_user_row.user_id = "user-1"
        top_user_row.total_calls = 500

        mock_result = MagicMock()
        # First call: totals; Second call: top_users
        mock_result.one.return_value = totals_row

        mock_result2 = MagicMock()
        mock_result2.all.return_value = [top_user_row]

        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_result2])

        result = await usage_repo.get_aggregate_stats(limit=10)

        assert result["total_calls"] == 1000
        assert result["total_errors"] == 50
        assert len(result["top_users"]) == 1
        assert result["top_users"][0]["user_id"] == "user-1"
        assert result["top_users"][0]["total_calls"] == 500

    async def test_get_aggregate_stats_handles_empty_db(
        self,
        usage_repo: ApiUsageRepository,
        mock_session: AsyncMock,
    ) -> None:
        """get_aggregate_stats handles empty database gracefully."""
        totals_row = MagicMock()
        totals_row.total_calls = 0
        totals_row.total_errors = 0

        mock_result = MagicMock()
        mock_result.one.return_value = totals_row

        mock_result2 = MagicMock()
        mock_result2.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_result2])

        result = await usage_repo.get_aggregate_stats()

        assert result["total_calls"] == 0
        assert result["total_errors"] == 0
        assert result["top_users"] == []
