"""Repository for DividendData data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.dividend import DividendDataDB
from stockvaluefinder.models.dividend import DividendCreate, DividendUpdate
from stockvaluefinder.repositories.base import BaseRepository


class DividendRepository(BaseRepository[DividendDataDB]):
    """Repository for DividendData data access with domain-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with DividendDataDB model."""
        super().__init__(DividendDataDB, session)

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> list[DividendDataDB]:
        """Get all dividend records for a given ticker.

        Args:
            ticker: Stock code (e.g., '600519.SH')
            limit: Maximum number of records to return

        Returns:
            List of DividendDataDB objects ordered by ex_dividend_date (most recent first)
        """
        stmt = select(DividendDataDB).where(
            DividendDataDB.ticker == ticker,
        ).order_by(
            DividendDataDB.ex_dividend_date.desc(),
        ).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticker_and_year(
        self,
        ticker: str,
        fiscal_year: int,
    ) -> list[DividendDataDB]:
        """Get all dividend records for a ticker in a given fiscal year.

        Args:
            ticker: Stock code
            fiscal_year: Fiscal year (e.g., 2023)

        Returns:
            List of DividendDataDB objects for the fiscal year
        """
        stmt = select(DividendDataDB).where(
            DividendDataDB.ticker == ticker,
            DividendDataDB.fiscal_year == fiscal_year,
        ).order_by(
            DividendDataDB.ex_dividend_date.desc(),
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_dividend(
        self,
        ticker: str,
    ) -> DividendDataDB | None:
        """Get the most recent dividend record for a ticker.

        Args:
            ticker: Stock code

        Returns:
            Latest DividendDataDB if found, None otherwise
        """
        stmt = select(DividendDataDB).where(
            DividendDataDB.ticker == ticker,
        ).order_by(
            DividendDataDB.ex_dividend_date.desc(),
        ).limit(1)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        data: DividendCreate,
    ) -> DividendDataDB:
        """Create a new dividend record.

        Args:
            data: DividendCreate Pydantic model

        Returns:
            Created DividendDataDB instance
        """
        from datetime import datetime

        db_obj = DividendDataDB(
            ticker=data.ticker,
            ex_dividend_date=data.ex_dividend_date,
            dividend_per_share=data.dividend_per_share,
            dividend_frequency=data.dividend_frequency.value,
            fiscal_year=data.fiscal_year,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        dividend_id: UUID,
        data: DividendUpdate,
    ) -> DividendDataDB | None:
        """Update an existing dividend record.

        Args:
            dividend_id: Primary key UUID
            data: DividendUpdate Pydantic model

        Returns:
            Updated DividendDataDB if found, None otherwise
        """
        from datetime import datetime

        stmt = select(DividendDataDB).where(
            DividendDataDB.dividend_id == dividend_id,
        )
        result = await self._session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj is None:
            return None

        # Update fields if provided
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "dividend_frequency" and isinstance(value, str):
                # Keep enum value as string
                setattr(db_obj, field, value)
            else:
                setattr(db_obj, field, value)

        db_obj.updated_at = datetime.utcnow()
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj
