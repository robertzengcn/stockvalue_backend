"""Repository for Stock data access."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.stock import StockDB
from stockvaluefinder.models.stock import StockCreate, StockUpdate
from stockvaluefinder.repositories.base import BaseRepository


class StockRepository(BaseRepository[StockDB, StockCreate, StockUpdate]):
    """Repository for Stock data access with domain-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize StockRepository with StockDB model."""
        super().__init__(StockDB, session)

    async def get_by_ticker(self, ticker: str) -> StockDB | None:
        """Get stock by ticker symbol.

        Args:
            ticker: Stock ticker symbol (e.g., '600519.SH', '0700.HK')

        Returns:
            StockDB instance if found, None otherwise
        """
        result = await self.session.execute(
            select(StockDB).where(StockDB.ticker == ticker.upper())
        )
        return result.scalars().first()

    async def get_by_market(
        self,
        market: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StockDB]:
        """Get all stocks for a specific market.

        Args:
            market: Market enum value ('A_SHARE' or 'HK_SHARE')
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of StockDB instances
        """
        result = await self.session.execute(
            select(StockDB)
            .where(StockDB.market == market)
            .order_by(StockDB.ticker)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_industry(
        self,
        industry: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StockDB]:
        """Get all stocks in a specific industry.

        Args:
            industry: Industry sector name
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of StockDB instances
        """
        result = await self.session.execute(
            select(StockDB)
            .where(StockDB.industry == industry)
            .order_by(StockDB.ticker)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def ticker_exists(self, ticker: str) -> bool:
        """Check if a stock with the given ticker exists.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if stock exists, False otherwise
        """
        result = await self.session.execute(
            select(StockDB.ticker).where(StockDB.ticker == ticker.upper())
        )
        return result.first() is not None

    async def create(self, data: StockCreate) -> StockDB:
        """Create a new stock.

        Args:
            data: StockCreate Pydantic model with stock data

        Returns:
            Created StockDB instance
        """
        from datetime import datetime

        db_obj = StockDB(
            ticker=data.ticker,
            name=data.name,
            market=data.market.value,
            industry=data.industry,
            list_date=data.list_date,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def update(self, ticker: str, data: StockUpdate) -> StockDB | None:
        """Update an existing stock.

        Args:
            ticker: Stock ticker symbol
            data: StockUpdate Pydantic model with fields to update

        Returns:
            Updated StockDB instance if found, None otherwise
        """
        from datetime import datetime

        db_obj = await self.get_by_ticker(ticker)
        if db_obj is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db_obj.updated_at = datetime.utcnow()
        await self.session.flush()
        return db_obj
