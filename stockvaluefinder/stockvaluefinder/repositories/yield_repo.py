"""Repository for YieldGap data access."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.yield_gap import YieldGapDB
from stockvaluefinder.models.enums import YieldRecommendation
from stockvaluefinder.models.yield_gap import YieldGapCreate, YieldGapUpdate
from stockvaluefinder.repositories.base import BaseRepository


class YieldGapRepository(BaseRepository[YieldGapDB]):
    """Repository for YieldGap data access with domain-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with YieldGapDB model."""
        super().__init__(YieldGapDB, session)

    async def get_by_ticker(
        self,
        ticker: str,
        limit: int = 100,
    ) -> list[YieldGapDB]:
        """Get all yield gap analyses for a given ticker.

        Args:
            ticker: Stock code (e.g., '600519.SH')
            limit: Maximum number of records to return

        Returns:
            List of YieldGapDB objects ordered by calculated_at (most recent first)
        """
        stmt = (
            select(YieldGapDB)
            .where(
                YieldGapDB.ticker == ticker,
            )
            .order_by(
                YieldGapDB.calculated_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_analysis_id(
        self,
        analysis_id: UUID,
    ) -> YieldGapDB | None:
        """Get yield gap analysis by primary key.

        Args:
            analysis_id: Primary key UUID

        Returns:
            YieldGapDB if found, None otherwise
        """
        stmt = select(YieldGapDB).where(
            YieldGapDB.analysis_id == analysis_id,
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_ticker(
        self,
        ticker: str,
    ) -> YieldGapDB | None:
        """Get the latest yield gap analysis for a ticker.

        Args:
            ticker: Stock code

        Returns:
            Latest YieldGapDB if found, None otherwise
        """
        stmt = (
            select(YieldGapDB)
            .where(
                YieldGapDB.ticker == ticker,
            )
            .order_by(
                YieldGapDB.calculated_at.desc(),
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_recommendation(
        self,
        recommendation: YieldRecommendation,
        limit: int = 100,
    ) -> list[YieldGapDB]:
        """Get all yield gap analyses with a specific recommendation.

        Args:
            recommendation: Recommendation enum (ATTRACTIVE, NEUTRAL, UNATTRACTIVE)
            limit: Maximum number of records to return

        Returns:
            List of YieldGapDB objects ordered by calculated_at (most recent first)
        """
        stmt = (
            select(YieldGapDB)
            .where(
                YieldGapDB.recommendation == recommendation.value,
            )
            .order_by(
                YieldGapDB.calculated_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_attractive_stocks(
        self,
        limit: int = 100,
    ) -> list[YieldGapDB]:
        """Get stocks with ATTRACTIVE yield gap recommendation.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of YieldGapDB with ATTRACTIVE recommendation, ordered by yield_gap (highest first)
        """
        stmt = (
            select(YieldGapDB)
            .where(
                YieldGapDB.recommendation == YieldRecommendation.ATTRACTIVE.value,
            )
            .order_by(
                YieldGapDB.yield_gap.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> list[YieldGapDB]:
        """Get yield gap analyses calculated within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            limit: Maximum number of records to return

        Returns:
            List of YieldGapDB objects ordered by calculated_at (most recent first)
        """
        stmt = (
            select(YieldGapDB)
            .where(
                YieldGapDB.calculated_at >= start_date,
                YieldGapDB.calculated_at <= end_date,
            )
            .order_by(
                YieldGapDB.calculated_at.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        data: YieldGapCreate,
    ) -> YieldGapDB:
        """Create a new yield gap analysis record.

        Args:
            data: YieldGapCreate Pydantic model

        Returns:
            Created YieldGapDB instance
        """
        from decimal import Decimal

        db_obj = YieldGapDB(
            analysis_id=data.analysis_id,
            ticker=data.ticker,
            cost_basis=Decimal(str(data.cost_basis)),
            current_price=Decimal(str(data.current_price)),
            gross_dividend_yield=data.gross_dividend_yield,
            net_dividend_yield=data.net_dividend_yield,
            risk_free_bond_rate=data.risk_free_bond_rate,
            risk_free_deposit_rate=data.risk_free_deposit_rate,
            yield_gap=data.yield_gap,
            recommendation=data.recommendation.value,
            market=data.market.value,
            calculated_at=data.calculated_at,
        )

        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        analysis_id: UUID,
        data: YieldGapUpdate,
    ) -> YieldGapDB | None:
        """Update an existing yield gap analysis.

        Args:
            analysis_id: Primary key UUID
            data: YieldGapUpdate Pydantic model

        Returns:
            Updated YieldGapDB if found, None otherwise
        """
        from decimal import Decimal

        stmt = select(YieldGapDB).where(
            YieldGapDB.analysis_id == analysis_id,
        )
        result = await self._session.execute(stmt)
        db_obj = result.scalar_one_or_none()

        if db_obj is None:
            return None

        # Update fields if provided
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field in ("cost_basis", "current_price"):
                # Convert Decimal fields
                setattr(db_obj, field, Decimal(str(value)))
            elif field in ("recommendation", "market") and hasattr(value, "value"):
                # Convert enum to string
                setattr(db_obj, field, value.value)
            else:
                setattr(db_obj, field, value)

        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj
