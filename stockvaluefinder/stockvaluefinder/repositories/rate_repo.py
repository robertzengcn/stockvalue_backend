"""Repository for RateData data access."""

from datetime import date, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.rate import RateDataDB
from stockvaluefinder.models.rate import RateDataCreate, RateDataUpdate
from stockvaluefinder.repositories.base import BaseRepository


class RateRepository(BaseRepository[RateDataDB, RateDataCreate, RateDataUpdate]):
    """Repository for RateData data access with domain-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize RateRepository with RateDataDB model."""
        super().__init__(RateDataDB, session)

    async def get_by_rate_date(self, rate_date: date) -> RateDataDB | None:
        """Get rate data by date.

        Args:
            rate_date: Date of the rate data

        Returns:
            RateDataDB instance if found, None otherwise
        """
        result = await self.session.execute(
            select(RateDataDB).where(RateDataDB.rate_date == rate_date)
        )
        return result.scalars().first()

    async def get_latest_rate(self) -> RateDataDB | None:
        """Get the most recent rate data.

        Returns:
            Latest RateDataDB instance if any exist, None otherwise
        """
        result = await self.session.execute(
            select(RateDataDB).order_by(RateDataDB.rate_date.desc()).limit(1)
        )
        return result.scalars().first()

    async def get_rates_by_date_range(
        self,
        start_date: date,
        end_date: date,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RateDataDB]:
        """Get rate data for a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of RateDataDB instances ordered by date descending
        """
        result = await self.session.execute(
            select(RateDataDB)
            .where(RateDataDB.rate_date >= start_date)
            .where(RateDataDB.rate_date <= end_date)
            .order_by(RateDataDB.rate_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def rate_date_exists(self, rate_date: date) -> bool:
        """Check if rate data exists for the given date.

        Args:
            rate_date: Date to check

        Returns:
            True if rate data exists for the date, False otherwise
        """
        result = await self.session.execute(
            select(RateDataDB.rate_id).where(RateDataDB.rate_date == rate_date)
        )
        return result.first() is not None

    async def create(self, data: RateDataCreate) -> RateDataDB:
        """Create new rate data.

        Args:
            data: RateDataCreate Pydantic model with rate data

        Returns:
            Created RateDataDB instance
        """
        from datetime import datetime
        from uuid import uuid4

        db_obj = RateDataDB(
            rate_id=str(uuid4()),
            rate_date=data.rate_date,
            ten_year_treasury=data.ten_year_treasury,
            three_year_deposit=data.three_year_deposit,
            one_year_deposit=data.one_year_deposit,
            benchmark_rate=data.benchmark_rate,
            rate_source=data.rate_source,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def update(
        self,
        rate_id: str,
        data: RateDataUpdate,
    ) -> RateDataDB | None:
        """Update existing rate data.

        Args:
            rate_id: UUID of the rate data to update
            data: RateDataUpdate Pydantic model with fields to update

        Returns:
            Updated RateDataDB instance if found, None otherwise
        """
        db_obj = await self.get_by_id(rate_id)
        if db_obj is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        await self.session.flush()
        return db_obj

    async def delete_by_rate_date(self, rate_date: date) -> bool:
        """Delete rate data by date.

        Args:
            rate_date: Date of the rate data to delete

        Returns:
            True if deleted, False if not found
        """
        db_obj = await self.get_by_rate_date(rate_date)
        if db_obj is None:
            return False

        await self.session.delete(db_obj)
        await self.session.flush()
        return True
