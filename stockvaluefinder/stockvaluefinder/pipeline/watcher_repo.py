"""WatcherStateRepository for watcher_state table operations.

Provides database operations for the watcher_state table including:
- Getting the singleton watcher state row (creates if not exists)
- Updating state after each poll cycle with success flags and counters
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.watcher_state import WatcherStateDB

logger = logging.getLogger(__name__)


class WatcherStateRepository:
    """Repository for watcher state database operations.

    Manages the singleton watcher_state row that tracks the watcher's
    operational status: last poll time, data source success/failure flags,
    and cumulative poll/error counts. Updated each poll cycle (D-16).

    Args:
        session: Async database session for all operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Async database session for all operations.
        """
        self._session = session

    async def get_state(self) -> WatcherStateDB:
        """Get the watcher state row, creating it if it doesn't exist.

        Uses watcher_id='default' as the singleton key.

        Returns:
            WatcherStateDB instance (never None).
        """
        stmt = select(WatcherStateDB).where(WatcherStateDB.watcher_id == "default")
        result = await self._session.execute(stmt)
        state = result.scalar_one_or_none()

        if state is None:
            state = WatcherStateDB(
                watcher_id="default",
                last_poll_time=None,
                last_akshare_success=False,
                last_cninfo_fallback=False,
                polls_count=0,
                errors_count=0,
                updated_at=datetime.now(timezone.utc),
            )
            self._session.add(state)
            await self._session.flush()
            await self._session.refresh(state)
            logger.info("Created default watcher state")

        return state

    async def update_state(
        self,
        last_akshare_success: bool,
        last_cninfo_fallback: bool,
        is_error: bool = False,
    ) -> WatcherStateDB:
        """Update watcher state after a poll cycle.

        Increments polls_count (always) and errors_count (if is_error).
        Sets last_poll_time to current UTC time and updates success flags.

        Args:
            last_akshare_success: Whether the AKShare poll succeeded.
            last_cninfo_fallback: Whether CNInfo fallback was used.
            is_error: Whether this poll cycle encountered an error.

        Returns:
            Updated WatcherStateDB instance.
        """
        state = await self.get_state()

        state.last_poll_time = datetime.now(timezone.utc)
        state.last_akshare_success = last_akshare_success
        state.last_cninfo_fallback = last_cninfo_fallback
        state.polls_count = state.polls_count + 1
        if is_error:
            state.errors_count = state.errors_count + 1
        state.updated_at = datetime.now(timezone.utc)

        await self._session.flush()
        await self._session.refresh(state)
        logger.info(
            "Updated watcher state",
            extra={
                "polls_count": state.polls_count,
                "errors_count": state.errors_count,
                "akshare_success": last_akshare_success,
                "cninfo_fallback": last_cninfo_fallback,
            },
        )
        return state


__all__ = ["WatcherStateRepository"]
