"""PipelineTaskRepository with atomic state transitions.

Provides database operations for pipeline tasks including:
- Task creation with deduplication (business_key unique constraint)
- Atomic state transitions with row-level locking (SELECT FOR UPDATE)
- Stuck task detection based on state and updated_at threshold
- Task reset with retry count tracking and max_retries enforcement
- State aggregation counts for status endpoint
- Filtered task listing with pagination
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.pipeline_task import PipelineTaskDB
from stockvaluefinder.pipeline.state import PipelineState, validate_transition

logger = logging.getLogger(__name__)


class PipelineTaskRepository:
    """Repository for pipeline task database operations.

    Does NOT extend BaseRepository because pipeline tasks use task_id
    (not id) as primary key and have different query patterns.

    All state transitions are atomic: SELECT FOR UPDATE locks the row,
    validate_transition checks validity, then UPDATE writes the new state.
    The caller controls commit/rollback via the session lifecycle.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Async database session for all operations.
        """
        self._session = session
        self._model = PipelineTaskDB

    async def create_task(
        self,
        ticker: str,
        business_key: str,
        max_retries: int = 3,
    ) -> PipelineTaskDB:
        """Create a new pipeline task with state=pending.

        Args:
            ticker: Stock ticker (e.g., '600519.SH').
            business_key: Unique deduplication key (ticker:fiscal_year:report_type).
            max_retries: Maximum retry attempts before permanent failure.

        Returns:
            Created PipelineTaskDB instance.

        Raises:
            ValueError: If business_key already exists (unique constraint).
        """
        task = PipelineTaskDB(
            task_id=uuid4(),
            ticker=ticker,
            business_key=business_key,
            state="pending",
            retry_count=0,
            max_retries=max_retries,
        )
        self._session.add(task)
        try:
            await self._session.flush()
            await self._session.refresh(task)
        except IntegrityError as e:
            await self._session.rollback()
            raise ValueError(
                f"Task with business_key '{business_key}' already exists"
            ) from e

        logger.info(
            "Created pipeline task",
            extra={
                "task_id": str(task.task_id),
                "ticker": ticker,
                "business_key": business_key,
            },
        )
        return task

    async def get_by_id(self, task_id: str) -> PipelineTaskDB | None:
        """Get a pipeline task by its task_id.

        Args:
            task_id: UUID of the task.

        Returns:
            PipelineTaskDB instance or None if not found.
        """
        stmt = select(self._model).where(self._model.task_id == task_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_business_key(self, business_key: str) -> PipelineTaskDB | None:
        """Get a pipeline task by its unique business key.

        Args:
            business_key: Unique deduplication key.

        Returns:
            PipelineTaskDB instance or None if not found.
        """
        stmt = select(self._model).where(self._model.business_key == business_key)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def transition_state(
        self,
        task_id: str,
        target_state: PipelineState,
        error_message: str | None = None,
        current_stage: str | None = None,
    ) -> PipelineTaskDB:
        """Atomically transition a task's state with row-level locking.

        Steps:
        1. SELECT ... FOR UPDATE to lock the row
        2. Read current state
        3. Validate transition via validate_transition()
        4. UPDATE state, updated_at, error_message, current_stage
        5. Flush + refresh

        The caller controls commit/rollback via session lifecycle.

        Args:
            task_id: UUID of the task.
            target_state: Desired target state.
            error_message: Optional error message (typically for FAILED transitions).
            current_stage: Optional description of current processing stage.

        Returns:
            Updated PipelineTaskDB instance.

        Raises:
            ValueError: If task not found.
            StateTransitionError: If transition is invalid.
        """
        # Lock row for atomic update
        stmt = (
            select(self._model).where(self._model.task_id == task_id).with_for_update()
        )
        result = await self._session.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            raise ValueError(f"Task {task_id} not found")

        # Validate before writing
        current_state = PipelineState(task.state)
        validate_transition(current_state, target_state)

        # Apply transition
        task.state = target_state.value
        task.updated_at = datetime.now(timezone.utc)

        if error_message is not None:
            task.error_message = error_message
        elif target_state != PipelineState.FAILED:
            # Clear error on non-FAILED transitions
            task.error_message = None

        if current_stage is not None:
            task.current_stage = current_stage

        await self._session.flush()
        await self._session.refresh(task)

        logger.info(
            "Transitioned task state",
            extra={
                "task_id": str(task_id),
                "from": current_state.value,
                "to": target_state.value,
            },
        )
        return task

    async def get_stuck_tasks(self, timeout_minutes: int) -> list[PipelineTaskDB]:
        """Find tasks stuck in active states beyond the timeout threshold.

        Active states are DOWNLOADING, PARSING, and ANALYZING.
        A task is considered stuck if its updated_at is older than
        NOW() - timeout_minutes.

        Args:
            timeout_minutes: Minutes threshold for considering a task stuck.

        Returns:
            List of stuck PipelineTaskDB instances.
        """
        active_states = [
            PipelineState.DOWNLOADING.value,
            PipelineState.PARSING.value,
            PipelineState.ANALYZING.value,
        ]
        stmt = select(self._model).where(
            self._model.state.in_(active_states),
            self._model.updated_at
            < datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def reset_task(self, task_id: str) -> PipelineTaskDB | None:
        """Reset a stuck task: retry or permanently fail.

        If retry_count < max_retries: increment retry_count, set state=PENDING,
        clear error_message.
        If retry_count >= max_retries: set state=FAILED with error message.

        Uses SELECT FOR UPDATE for atomic operation.

        Args:
            task_id: UUID of the task to reset.

        Returns:
            Updated PipelineTaskDB or None if not found.
        """
        stmt = (
            select(self._model).where(self._model.task_id == task_id).with_for_update()
        )
        result = await self._session.execute(stmt)
        task = result.scalar_one_or_none()

        if task is None:
            return None

        if task.retry_count < task.max_retries:
            task.state = PipelineState.PENDING.value
            task.retry_count = task.retry_count + 1
            task.error_message = None
            task.updated_at = datetime.now(timezone.utc)
            logger.info(
                "Reset stuck task to PENDING",
                extra={
                    "task_id": str(task_id),
                    "retry_count": task.retry_count,
                    "max_retries": task.max_retries,
                },
            )
        else:
            task.state = PipelineState.FAILED.value
            task.error_message = "Exceeded max retries"
            task.updated_at = datetime.now(timezone.utc)
            logger.warning(
                "Permanently failed stuck task (exceeded max retries)",
                extra={
                    "task_id": str(task_id),
                    "retry_count": task.retry_count,
                    "max_retries": task.max_retries,
                },
            )

        await self._session.flush()
        await self._session.refresh(task)
        return task

    async def count_by_state(self) -> dict[str, int]:
        """Count tasks grouped by state.

        Returns a dict with all 6 PipelineState keys (pending, downloading,
        parsing, analyzing, done, failed) mapped to their counts. States
        with zero tasks are included with value 0.

        Returns:
            Dict mapping state name strings to integer counts.
        """
        stmt = select(self._model.state, func.count()).group_by(self._model.state)
        result = await self._session.execute(stmt)
        rows = result.all()
        counts: dict[str, int] = {row[0]: row[1] for row in rows}
        all_states = {s.value: 0 for s in PipelineState}
        all_states.update(counts)
        return all_states

    async def list_tasks(
        self,
        state: str | None = None,
        ticker: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[PipelineTaskDB], int]:
        """List tasks with optional filters and pagination.

        Returns tasks ordered by created_at descending. Applies optional
        filters for state, ticker, and date range. Returns both the task
        list and the total count for pagination metadata.

        Args:
            state: Filter by pipeline state (e.g., 'pending', 'done').
            ticker: Filter by stock ticker.
            created_after: Include tasks created at or after this datetime.
            created_before: Include tasks created at or before this datetime.
            offset: Number of tasks to skip (for pagination).
            limit: Maximum number of tasks to return.

        Returns:
            Tuple of (task list, total count before pagination).
        """
        stmt = select(self._model)
        count_stmt = select(func.count()).select_from(self._model)

        if state:
            stmt = stmt.where(self._model.state == state)
            count_stmt = count_stmt.where(self._model.state == state)
        if ticker:
            stmt = stmt.where(self._model.ticker == ticker)
            count_stmt = count_stmt.where(self._model.ticker == ticker)
        if created_after:
            stmt = stmt.where(self._model.created_at >= created_after)
            count_stmt = count_stmt.where(self._model.created_at >= created_after)
        if created_before:
            stmt = stmt.where(self._model.created_at <= created_before)
            count_stmt = count_stmt.where(self._model.created_at <= created_before)

        total = (await self._session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(self._model.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        tasks = list(result.scalars().all())
        return tasks, total


__all__ = ["PipelineTaskRepository"]
