"""Unit tests for PipelineTaskRepository with atomic state transitions."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from stockvaluefinder.pipeline.state import PipelineState
from stockvaluefinder.utils.errors import StateTransitionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_db(
    task_id: str | None = None,
    ticker: str = "600519.SH",
    business_key: str = "600519.SH:2023:annual",
    state: str = "pending",
    current_stage: str | None = None,
    retry_count: int = 0,
    max_retries: int = 3,
    error_message: str | None = None,
    result_summary: dict | None = None,
) -> MagicMock:
    """Create a mock PipelineTaskDB object."""
    task = MagicMock()
    task.task_id = task_id or str(uuid.uuid4())
    task.ticker = ticker
    task.business_key = business_key
    task.state = state
    task.current_stage = current_stage
    task.retry_count = retry_count
    task.max_retries = max_retries
    task.error_message = error_message
    task.result_summary = result_summary
    task.updated_at = datetime.now(timezone.utc)
    task.created_at = datetime.now(timezone.utc)
    return task


def _mock_session(return_scalars: list | None = None) -> AsyncMock:
    """Create a mock AsyncSession.

    Args:
        return_scalars: List of values to return from sequential
            scalar_one_or_none / scalars().all() calls.
    """
    session = AsyncMock()
    result_mock = MagicMock()

    # Default: no rows
    if return_scalars is None:
        return_scalars = []

    # Set up scalar_one_or_none / scalars chain
    scalar_idx = 0

    def _scalar_one_or_none():
        nonlocal scalar_idx
        if scalar_idx < len(return_scalars):
            val = return_scalars[scalar_idx]
            scalar_idx += 1
            return val
        return None

    result_mock.scalar_one_or_none = _scalar_one_or_none

    # scalars().all() returns a list
    scalars_mock = MagicMock()

    def _all():
        nonlocal scalar_idx
        remaining = return_scalars[scalar_idx:]
        scalar_idx = len(return_scalars)
        return remaining

    scalars_mock.all = _all
    result_mock.scalars.return_value = scalars_mock

    session.execute.return_value = result_mock
    return session


# ---------------------------------------------------------------------------
# create_task tests
# ---------------------------------------------------------------------------


class TestCreateTask:
    """Tests for PipelineTaskRepository.create_task."""

    @pytest.mark.asyncio
    async def test_create_task_with_defaults(self) -> None:
        """create_task creates PipelineTaskDB with state=pending and retry_count=0."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository
        from stockvaluefinder.db.models.pipeline_task import PipelineTaskDB

        session = _mock_session()
        repo = PipelineTaskRepository(session)

        # Mock flush + refresh (in-place updates)
        async def fake_flush():
            pass

        async def fake_refresh(obj):
            pass

        session.flush = AsyncMock(side_effect=fake_flush)
        session.refresh = AsyncMock(side_effect=fake_refresh)

        await repo.create_task(ticker="600519.SH", business_key="600519.SH:2023:annual")

        assert session.add.called
        added_obj = session.add.call_args[0][0]
        assert isinstance(added_obj, PipelineTaskDB)
        assert added_obj.ticker == "600519.SH"
        assert added_obj.business_key == "600519.SH:2023:annual"
        assert added_obj.state == "pending"
        assert added_obj.retry_count == 0
        assert added_obj.max_retries == 3
        assert added_obj.error_message is None

    @pytest.mark.asyncio
    async def test_create_task_custom_max_retries(self) -> None:
        """create_task uses custom max_retries value."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        session = _mock_session()
        repo = PipelineTaskRepository(session)
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        await repo.create_task(
            ticker="000001.SZ",
            business_key="000001.SZ:2023:annual",
            max_retries=5,
        )

        added_obj = session.add.call_args[0][0]
        assert added_obj.max_retries == 5

    @pytest.mark.asyncio
    async def test_create_task_duplicate_business_key_raises(self) -> None:
        """create_task raises ValueError when business_key already exists."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        session = _mock_session()
        repo = PipelineTaskRepository(session)

        # Mock flush to raise IntegrityError for unique constraint violation
        session.flush = AsyncMock(
            side_effect=IntegrityError(
                "duplicate key",
                params=None,
                orig=Exception("unique constraint"),
            )
        )

        with pytest.raises(ValueError, match="already exists"):
            await repo.create_task(
                ticker="600519.SH", business_key="600519.SH:2023:annual"
            )


# ---------------------------------------------------------------------------
# get_by_id tests
# ---------------------------------------------------------------------------


class TestGetById:
    """Tests for PipelineTaskRepository.get_by_id."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_task(self) -> None:
        """get_by_id returns task when found."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task_id = str(uuid.uuid4())
        expected = _make_task_db(task_id=task_id)
        session = _mock_session(return_scalars=[expected])
        repo = PipelineTaskRepository(session)

        result = await repo.get_by_id(task_id)

        assert result is expected
        assert result.task_id == task_id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self) -> None:
        """get_by_id returns None when no task matches."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        session = _mock_session(return_scalars=[None])
        repo = PipelineTaskRepository(session)

        result = await repo.get_by_id("nonexistent-id")

        assert result is None


# ---------------------------------------------------------------------------
# get_by_business_key tests
# ---------------------------------------------------------------------------


class TestGetByBusinessKey:
    """Tests for PipelineTaskRepository.get_by_business_key."""

    @pytest.mark.asyncio
    async def test_get_by_business_key_returns_task(self) -> None:
        """get_by_business_key returns task matching the unique business key."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        expected = _make_task_db(business_key="600519.SH:2023:annual")
        session = _mock_session(return_scalars=[expected])
        repo = PipelineTaskRepository(session)

        result = await repo.get_by_business_key("600519.SH:2023:annual")

        assert result is expected
        assert result.business_key == "600519.SH:2023:annual"

    @pytest.mark.asyncio
    async def test_get_by_business_key_returns_none(self) -> None:
        """get_by_business_key returns None when no task matches."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        session = _mock_session(return_scalars=[None])
        repo = PipelineTaskRepository(session)

        result = await repo.get_by_business_key("nonexistent:key")

        assert result is None


# ---------------------------------------------------------------------------
# transition_state tests
# ---------------------------------------------------------------------------


class TestTransitionState:
    """Tests for PipelineTaskRepository.transition_state."""

    @pytest.mark.asyncio
    async def test_valid_transition_updates_state(self) -> None:
        """transition_state(PENDING -> DOWNLOADING) updates state, updated_at, current_stage."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task_id = str(uuid.uuid4())
        task = _make_task_db(task_id=task_id, state="pending")
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        await repo.transition_state(
            task_id=task_id,
            target_state=PipelineState.DOWNLOADING,
            current_stage="downloading",
        )

        # Validate transition was called (no exception)
        assert task.state == PipelineState.DOWNLOADING
        assert task.current_stage == "downloading"
        assert session.flush.called
        assert session.refresh.called

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_error(self) -> None:
        """transition_state(PENDING -> PARSING) raises StateTransitionError and does NOT update."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task_id = str(uuid.uuid4())
        original_state = "pending"
        task = _make_task_db(task_id=task_id, state=original_state)
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        with pytest.raises(StateTransitionError):
            await repo.transition_state(
                task_id=task_id,
                target_state=PipelineState.PARSING,
            )

        # State should NOT have changed
        assert task.state == original_state
        # flush should NOT have been called
        assert not session.flush.called

    @pytest.mark.asyncio
    async def test_transition_to_failed_sets_error_message(self) -> None:
        """transition_state with error_message sets error_message and state=FAILED atomically."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task_id = str(uuid.uuid4())
        task = _make_task_db(task_id=task_id, state="downloading")
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        await repo.transition_state(
            task_id=task_id,
            target_state=PipelineState.FAILED,
            error_message="Download timed out",
        )

        assert task.state == PipelineState.FAILED
        assert task.error_message == "Download timed out"
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_transition_updates_timestamp(self) -> None:
        """transition_state updates updated_at to current time."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task_id = str(uuid.uuid4())
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        task = _make_task_db(task_id=task_id, state="pending")
        task.updated_at = old_time
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        await repo.transition_state(
            task_id=task_id,
            target_state=PipelineState.DOWNLOADING,
        )

        # updated_at should have been set to now (greater than old_time)
        assert task.updated_at > old_time

    @pytest.mark.asyncio
    async def test_transition_nonexistent_task_raises(self) -> None:
        """transition_state raises ValueError when task not found."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        session = _mock_session(return_scalars=[None])
        repo = PipelineTaskRepository(session)

        with pytest.raises(ValueError, match="not found"):
            await repo.transition_state(
                task_id="nonexistent-id",
                target_state=PipelineState.DOWNLOADING,
            )


# ---------------------------------------------------------------------------
# get_stuck_tasks tests
# ---------------------------------------------------------------------------


class TestGetStuckTasks:
    """Tests for PipelineTaskRepository.get_stuck_tasks."""

    @pytest.mark.asyncio
    async def test_returns_stuck_tasks(self) -> None:
        """get_stuck_tasks returns tasks in DOWNLOADING/PARSING/ANALYZING with old updated_at."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        stuck1 = _make_task_db(state="downloading")
        stuck2 = _make_task_db(state="parsing")
        session = _mock_session()
        # For get_stuck_tasks, scalars().all() is used
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [stuck1, stuck2]
        session.execute.return_value = result_mock
        repo = PipelineTaskRepository(session)

        result = await repo.get_stuck_tasks(timeout_minutes=30)

        assert len(result) == 2
        assert result[0] is stuck1
        assert result[1] is stuck2
        # Verify execute was called (query was run)
        assert session.execute.called

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_stuck_tasks(self) -> None:
        """get_stuck_tasks returns empty list when no tasks are stuck."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        session = _mock_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock
        repo = PipelineTaskRepository(session)

        result = await repo.get_stuck_tasks(timeout_minutes=30)

        assert result == []


# ---------------------------------------------------------------------------
# reset_task tests
# ---------------------------------------------------------------------------


class TestResetTask:
    """Tests for PipelineTaskRepository.reset_task."""

    @pytest.mark.asyncio
    async def test_reset_under_max_retries_increments_and_sets_pending(self) -> None:
        """reset_task increments retry_count and sets state=PENDING when retry_count < max_retries."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task = _make_task_db(state="downloading", retry_count=1, max_retries=3)
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        await repo.reset_task(task.task_id)

        assert task.state == PipelineState.PENDING
        assert task.retry_count == 2
        assert task.error_message is None
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_reset_at_max_retries_sets_failed(self) -> None:
        """reset_task sets state=FAILED when retry_count >= max_retries."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task = _make_task_db(state="downloading", retry_count=3, max_retries=3)
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        await repo.reset_task(task.task_id)

        assert task.state == PipelineState.FAILED
        assert "Exceeded max retries" in task.error_message
        assert session.flush.called

    @pytest.mark.asyncio
    async def test_reset_exceeds_max_retries_sets_failed(self) -> None:
        """reset_task sets FAILED when retry_count already exceeds max_retries."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        task = _make_task_db(state="analyzing", retry_count=5, max_retries=3)
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        await repo.reset_task(task.task_id)

        assert task.state == PipelineState.FAILED
        assert "Exceeded max retries" in task.error_message

    @pytest.mark.asyncio
    async def test_reset_nonexistent_task_returns_none(self) -> None:
        """reset_task returns None when task not found."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        session = _mock_session(return_scalars=[None])
        repo = PipelineTaskRepository(session)

        result = await repo.reset_task("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_reset_updates_timestamp(self) -> None:
        """reset_task updates updated_at."""
        from stockvaluefinder.pipeline.repo import PipelineTaskRepository

        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        task = _make_task_db(state="downloading", retry_count=0, max_retries=3)
        task.updated_at = old_time
        session = _mock_session(return_scalars=[task])
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        repo = PipelineTaskRepository(session)

        await repo.reset_task(task.task_id)

        assert task.updated_at > old_time
