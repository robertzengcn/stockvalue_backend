"""WatchlistRepository for watchlist CRUD operations.

Provides database operations for the watchlist table including:
- Getting active tickers for watcher polling
- Adding and removing stocks from the watchlist
- Listing stocks with optional active-only filter
- Looking up individual stocks by ticker
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.watchlist import WatchlistDB

logger = logging.getLogger(__name__)


class WatchlistRepository:
    """Repository for watchlist database operations.

    Manages the user's watchlist of stocks to monitor for new
    financial report disclosures. The watchlist is empty by default
    and must be populated explicitly via API (D-14).

    Args:
        session: Async database session for all operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Async database session for all operations.
        """
        self._session = session

    async def get_active_tickers(self) -> list[str]:
        """Get list of ticker strings for all active watchlist entries.

        Returns:
            List of ticker strings (e.g., ['600519.SH', '000001.SZ']).
        """
        stmt = select(WatchlistDB.ticker).where(WatchlistDB.is_active.is_(True))
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return list(rows)

    async def add(self, ticker: str, name: str) -> WatchlistDB:
        """Add a stock to the watchlist.

        Args:
            ticker: Stock ticker (e.g., '600519.SH').
            name: Stock name or company name.

        Returns:
            Created WatchlistDB instance.
        """
        entry = WatchlistDB(
            ticker=ticker,
            name=name,
            added_at=datetime.now(timezone.utc),
            is_active=True,
        )
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        logger.info("Added stock to watchlist", extra={"ticker": ticker, "name": name})
        return entry

    async def remove(self, ticker: str) -> WatchlistDB | None:
        """Soft-remove a stock from the watchlist by setting is_active=False.

        Uses SELECT FOR UPDATE to lock the row during the operation.

        Args:
            ticker: Stock ticker to remove.

        Returns:
            Updated WatchlistDB or None if not found.
        """
        stmt = select(WatchlistDB).where(WatchlistDB.ticker == ticker).with_for_update()
        result = await self._session.execute(stmt)
        entry = result.scalar_one_or_none()

        if entry is None:
            return None

        entry.is_active = False
        await self._session.flush()
        await self._session.refresh(entry)
        logger.info("Removed stock from watchlist", extra={"ticker": ticker})
        return entry

    async def get_all(self, active_only: bool = True) -> list[WatchlistDB]:
        """Get all watchlist entries, optionally filtered by active status.

        Args:
            active_only: If True, return only active stocks.

        Returns:
            List of WatchlistDB instances.
        """
        stmt = select(WatchlistDB)
        if active_only:
            stmt = stmt.where(WatchlistDB.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticker(self, ticker: str) -> WatchlistDB | None:
        """Get a watchlist entry by ticker (primary key).

        Args:
            ticker: Stock ticker to look up.

        Returns:
            WatchlistDB instance or None if not found.
        """
        stmt = select(WatchlistDB).where(WatchlistDB.ticker == ticker)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


__all__ = ["WatchlistRepository"]
