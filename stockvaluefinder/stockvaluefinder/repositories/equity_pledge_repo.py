"""Repositories for equity pledge data access.

Provides two repository classes:
- PledgeSnapshotRepository: upsert snapshots by (ticker, latest_date, source)
- PledgeDetailRepository: replace and query detail records by ticker
"""

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.equity_pledge import (
    EquityPledgeDetailDB,
    EquityPledgeSnapshotDB,
)


class PledgeSnapshotRepository:
    """Repository for EquityPledgeSnapshotDB with custom upsert logic.

    Does NOT inherit from BaseRepository because the upsert-by-natural-key
    pattern differs from the generic CRUD operations.

    Args:
        session: Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with async session.

        Args:
            session: Async database session.
        """
        self._session = session

    async def upsert_by_ticker_date_source(
        self,
        ticker: str,
        latest_date: date,
        source: str,
        data: dict,
    ) -> EquityPledgeSnapshotDB:
        """Insert or update a pledge snapshot by (ticker, latest_date, source).

        If a snapshot already exists for the given natural key triplet, it is
        updated in place. Otherwise, a new record is created.

        Args:
            ticker: Stock code (e.g., '600519.SH').
            latest_date: Trade date of the pledge data.
            source: Data source identifier (e.g., 'akshare').
            data: Dict of field values to set on the snapshot.

        Returns:
            Created or updated EquityPledgeSnapshotDB instance.
        """
        stmt = select(EquityPledgeSnapshotDB).where(
            EquityPledgeSnapshotDB.ticker == ticker,
            EquityPledgeSnapshotDB.latest_date == latest_date,
            EquityPledgeSnapshotDB.source == source,
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            for field, value in data.items():
                setattr(existing, field, value)
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        db_obj = EquityPledgeSnapshotDB(**data)
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> list[EquityPledgeSnapshotDB]:
        """Get pledge snapshots for a ticker, most recent first.

        Args:
            ticker: Stock code.
            limit: Maximum number of records to return.

        Returns:
            List of EquityPledgeSnapshotDB ordered by latest_date desc.
        """
        stmt = (
            select(EquityPledgeSnapshotDB)
            .where(EquityPledgeSnapshotDB.ticker == ticker)
            .order_by(EquityPledgeSnapshotDB.latest_date.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PledgeDetailRepository:
    """Repository for EquityPledgeDetailDB with replace-and-query patterns.

    Uses a full-replace strategy: when fresh detail data arrives, all existing
    rows for that ticker are deleted and replaced with the new set.

    Args:
        session: Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with async session.

        Args:
            session: Async database session.
        """
        self._session = session

    async def replace_details_for_ticker(
        self,
        ticker: str,
        details_data: list[dict],
    ) -> list[EquityPledgeDetailDB]:
        """Delete existing details for ticker and insert fresh records.

        This is a destructive replace: all rows matching the ticker are
        removed first, then the new set is inserted. The operation is
        performed within the current session transaction.

        Args:
            ticker: Stock code to replace details for.
            details_data: List of dicts, each containing field values for
                one EquityPledgeDetailDB row.

        Returns:
            List of newly created EquityPledgeDetailDB instances.
        """
        # Delete all existing rows for this ticker
        await self._session.execute(
            delete(EquityPledgeDetailDB).where(
                EquityPledgeDetailDB.ticker == ticker,
            )
        )

        # Insert new records
        created: list[EquityPledgeDetailDB] = []
        for item in details_data:
            db_obj = EquityPledgeDetailDB(**item)
            self._session.add(db_obj)
            created.append(db_obj)

        await self._session.flush()

        # Refresh all to get server-generated values (e.g., created_at)
        for obj in created:
            await self._session.refresh(obj)

        return created

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> list[EquityPledgeDetailDB]:
        """Get pledge detail records for a ticker, most recent first.

        Args:
            ticker: Stock code.
            limit: Maximum number of records to return.

        Returns:
            List of EquityPledgeDetailDB ordered by announcement_date desc.
        """
        stmt = (
            select(EquityPledgeDetailDB)
            .where(EquityPledgeDetailDB.ticker == ticker)
            .order_by(EquityPledgeDetailDB.announcement_date.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
