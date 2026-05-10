"""Repository for UserStockAccess data access."""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.user_stock_access import UserStockAccessDB


class UserStockAccessRepository:
    """Repository for managing per-user stock access control entries.

    Each entry represents a ticker that a user is explicitly allowed to access.
    When no entries exist for a user, the user can access all stocks (ACCL-03).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Async database session
        """
        self._session = session

    async def get_accessible_tickers(self, user_id: str) -> list[str]:
        """Get all ticker strings accessible by a user.

        Args:
            user_id: User ID to look up access entries for

        Returns:
            List of ticker strings. Empty list means access to all stocks.
        """
        stmt = select(UserStockAccessDB.ticker).where(
            UserStockAccessDB.user_id == user_id
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return list(rows)

    async def add_access(self, user_id: str, ticker: str) -> UserStockAccessDB:
        """Add a stock access entry for a user.

        If a duplicate (user_id, ticker) entry already exists, returns the
        existing entry instead of raising an error.

        Args:
            user_id: User ID to grant access to
            ticker: Stock ticker to grant access for

        Returns:
            The created or existing UserStockAccessDB entry
        """
        entry = UserStockAccessDB(user_id=user_id, ticker=ticker)
        try:
            self._session.add(entry)
            await self._session.flush()
            await self._session.refresh(entry)
            return entry
        except IntegrityError:
            # Duplicate entry -- return existing
            await self._session.rollback()
            stmt = select(UserStockAccessDB).where(
                UserStockAccessDB.user_id == user_id,
                UserStockAccessDB.ticker == ticker,
            )
            result = await self._session.execute(stmt)
            existing = result.scalar_one()
            return existing

    async def remove_access(self, user_id: str, ticker: str) -> bool:
        """Remove a stock access entry for a user.

        Args:
            user_id: User ID to revoke access from
            ticker: Stock ticker to revoke access for

        Returns:
            True if an entry was deleted, False if not found
        """
        stmt = (
            delete(UserStockAccessDB)
            .where(UserStockAccessDB.user_id == user_id)
            .where(UserStockAccessDB.ticker == ticker)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0  # type: ignore[attr-defined]

    async def set_access(
        self, user_id: str, tickers: list[str]
    ) -> list[UserStockAccessDB]:
        """Replace all stock access entries for a user.

        Deletes all existing entries and inserts new ones in a single
        transactional operation.

        Args:
            user_id: User ID to set access for
            tickers: List of tickers to grant access to (replaces all existing)

        Returns:
            List of created UserStockAccessDB entries
        """
        # Delete all existing entries
        delete_stmt = delete(UserStockAccessDB).where(
            UserStockAccessDB.user_id == user_id
        )
        await self._session.execute(delete_stmt)

        # Bulk-insert new entries
        entries = [
            UserStockAccessDB(user_id=user_id, ticker=ticker) for ticker in tickers
        ]
        self._session.add_all(entries)
        await self._session.flush()

        # Refresh each entry to get DB-assigned values
        refreshed: list[UserStockAccessDB] = []
        for entry in entries:
            await self._session.refresh(entry)
            refreshed.append(entry)
        return refreshed

    async def get_all_for_user(self, user_id: str) -> list[UserStockAccessDB]:
        """Get all access entries for a user, ordered by ticker.

        Args:
            user_id: User ID to look up

        Returns:
            List of UserStockAccessDB entries ordered by ticker
        """
        stmt = (
            select(UserStockAccessDB)
            .where(UserStockAccessDB.user_id == user_id)
            .order_by(UserStockAccessDB.ticker)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def clear_access(self, user_id: str) -> int:
        """Delete all access entries for a user.

        Args:
            user_id: User ID to clear access for

        Returns:
            Number of entries deleted
        """
        stmt = delete(UserStockAccessDB).where(UserStockAccessDB.user_id == user_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[attr-defined]
