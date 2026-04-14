"""Repository for ValuationResult data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stockvaluefinder.db.models.valuation import ValuationResultDB
from stockvaluefinder.models.enums import ValuationLevel
from stockvaluefinder.models.valuation import (
    ValuationResultCreate,
    ValuationResultUpdate,
)
from stockvaluefinder.repositories.base import BaseRepository


class ValuationRepository(
    BaseRepository[ValuationResultDB, ValuationResultCreate, ValuationResultUpdate]
):
    """Repository for ValuationResult data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with ValuationResultDB model."""
        super().__init__(ValuationResultDB, session)

    async def get_by_ticker(
        self, ticker: str, limit: int = 100
    ) -> list[ValuationResultDB]:
        """Get all valuations for a ticker."""
        stmt = (
            select(ValuationResultDB)
            .where(
                ValuationResultDB.ticker == ticker,
            )
            .order_by(
                ValuationResultDB.calculated_at.desc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_ticker(self, ticker: str) -> ValuationResultDB | None:
        """Get latest valuation for a ticker."""
        stmt = (
            select(ValuationResultDB)
            .where(
                ValuationResultDB.ticker == ticker,
            )
            .order_by(
                ValuationResultDB.calculated_at.desc(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_valuation_level(
        self, level: ValuationLevel, limit: int = 100
    ) -> list[ValuationResultDB]:
        """Get valuations by level."""
        stmt = (
            select(ValuationResultDB)
            .where(
                ValuationResultDB.valuation_level == level.value,
            )
            .order_by(
                ValuationResultDB.calculated_at.desc(),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_valuation_id(
        self, valuation_id: "UUID"
    ) -> ValuationResultDB | None:
        """Get a valuation result by its valuation_id (primary key).

        Args:
            valuation_id: UUID of the valuation result

        Returns:
            ValuationResultDB instance if found, None otherwise
        """
        stmt = select(ValuationResultDB).where(
            ValuationResultDB.valuation_id == valuation_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: ValuationResultCreate) -> ValuationResultDB:
        """Create valuation record."""
        from decimal import Decimal

        db_obj = ValuationResultDB(
            valuation_id=data.valuation_id,
            ticker=data.ticker,
            current_price=Decimal(str(data.current_price)),
            intrinsic_value=Decimal(str(data.intrinsic_value)),
            wacc=data.wacc,
            margin_of_safety=data.margin_of_safety,
            valuation_level=data.valuation_level.value,
            dcf_params=data.dcf_params.model_dump(),
            audit_trail=data.audit_trail,
            calculated_at=data.calculated_at,
            narrative=data.narrative,
        )
        self._session.add(db_obj)
        await self._session.flush()
        await self._session.refresh(db_obj)
        return db_obj
