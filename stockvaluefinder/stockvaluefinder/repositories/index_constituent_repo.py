"""Repository for IndexConstituent data access with sync and history tracking."""

from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.index_constituent import IndexConstituentDB
from stockvaluefinder.models.market_scanner import (
    IndexConstituentCreate,
    IndexConstituentUpdate,
)
from stockvaluefinder.repositories.base import BaseRepository


class IndexConstituentRepository(
    BaseRepository[IndexConstituentDB, IndexConstituentCreate, IndexConstituentUpdate]
):
    """Repository for IndexConstituent data access.

    Provides constituent sync operations with effective_date tracking,
    bulk upsert for index refreshes, and history management via
    deactivate_missing for removal tracking (IDX-01, IDX-02).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with IndexConstituentDB model.

        Args:
            session: Async database session
        """
        super().__init__(IndexConstituentDB, session)

    async def get_active_by_index(
        self,
        index_code: str,
    ) -> list[IndexConstituentDB]:
        """Get all active constituents for a given index code.

        Args:
            index_code: Index pool identifier (e.g., CSI300, CSI500)

        Returns:
            List of active IndexConstituentDB objects ordered by ticker
        """
        stmt = (
            select(IndexConstituentDB)
            .where(
                IndexConstituentDB.index_code == index_code,
                IndexConstituentDB.is_active.is_(True),
            )
            .order_by(IndexConstituentDB.ticker)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticker(
        self,
        ticker: str,
    ) -> list[IndexConstituentDB]:
        """Get all index memberships for a given ticker.

        Returns both active and inactive memberships, ordered by
        effective_date descending (most recent first).

        Args:
            ticker: Stock code (e.g., 600519.SH)

        Returns:
            List of IndexConstituentDB objects for the ticker
        """
        stmt = (
            select(IndexConstituentDB)
            .where(IndexConstituentDB.ticker == ticker)
            .order_by(IndexConstituentDB.effective_date.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_constituent_history(
        self,
        index_code: str,
        limit: int = 100,
    ) -> list[IndexConstituentDB]:
        """Get all constituent records for an index, ordered by effective_date.

        Includes both active and removed constituents for historical analysis.

        Args:
            index_code: Index pool identifier (e.g., CSI300, CSI500)
            limit: Maximum number of records to return

        Returns:
            List of IndexConstituentDB objects ordered by effective_date desc
        """
        stmt = (
            select(IndexConstituentDB)
            .where(IndexConstituentDB.index_code == index_code)
            .order_by(IndexConstituentDB.effective_date.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_constituent(
        self,
        data: IndexConstituentCreate,
    ) -> IndexConstituentDB:
        """Insert or update a constituent by (index_code, ticker, effective_date).

        If a constituent already exists for the given composite key, it is
        updated in place. Otherwise, a new record is created.

        This implements IDX-01: record effective_date from data source.

        Args:
            data: IndexConstituentCreate Pydantic model

        Returns:
            Created or updated IndexConstituentDB instance
        """
        stmt = select(IndexConstituentDB).where(
            IndexConstituentDB.index_code == data.index_code,
            IndexConstituentDB.ticker == data.ticker,
            IndexConstituentDB.effective_date == data.effective_date,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        field_values = dict(
            index_code=data.index_code,
            ticker=data.ticker,
            name=data.name,
            effective_date=data.effective_date,
            is_active=data.is_active,
            removed_date=data.removed_date,
            updated_at=datetime.now(timezone.utc),
        )

        if existing is not None:
            for field, value in field_values.items():
                setattr(existing, field, value)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        db_obj = IndexConstituentDB(
            constituent_id=data.constituent_id,
            **field_values,
        )
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def bulk_upsert_constituents(
        self,
        constituents: list[IndexConstituentCreate],
    ) -> list[IndexConstituentDB]:
        """Upsert multiple constituents in a single call.

        Calls upsert_constituent for each item, returning all results.
        If an exception occurs mid-way, previously active constituents
        remain unchanged because deactivate_missing is not called by
        this method (upsert-before-deactivate ordering is enforced
        at the service layer).

        Args:
            constituents: List of IndexConstituentCreate models

        Returns:
            List of upserted IndexConstituentDB instances
        """
        results: list[IndexConstituentDB] = []
        for constituent in constituents:
            result = await self.upsert_constituent(constituent)
            results.append(result)
        return results

    async def deactivate_missing(
        self,
        index_code: str,
        active_tickers: set[str],
        removed_date: date,
    ) -> int:
        """Mark constituents as inactive when they are no longer in the active set.

        This implements IDX-02: mark removed constituents with a removal date.
        Uses a bulk update statement for efficiency.

        Args:
            index_code: Index pool identifier (e.g., CSI300, CSI500)
            active_tickers: Set of tickers that are currently active in the index
            removed_date: Date to record as the removal date

        Returns:
            Number of constituents deactivated
        """
        if not active_tickers:
            return 0

        stmt = (
            update(IndexConstituentDB)
            .where(
                IndexConstituentDB.index_code == index_code,
                IndexConstituentDB.is_active.is_(True),
                IndexConstituentDB.ticker.notin_(active_tickers),
            )
            .values(is_active=False, removed_date=removed_date)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[attr-defined]

    async def create(
        self,
        data: IndexConstituentCreate,
    ) -> IndexConstituentDB:
        """Create a new index constituent record.

        Overrides base create to map Pydantic fields to ORM columns.

        Args:
            data: IndexConstituentCreate Pydantic model

        Returns:
            Created IndexConstituentDB instance
        """
        db_obj = IndexConstituentDB(
            constituent_id=data.constituent_id,
            index_code=data.index_code,
            ticker=data.ticker,
            name=data.name,
            effective_date=data.effective_date,
            is_active=data.is_active,
            removed_date=data.removed_date,
        )
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj
